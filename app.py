import os
import re
import json
import logging
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from datetime import timedelta
from urllib.parse import urlparse
import requests

app = Flask(__name__)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Secret key
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config.update(
    SESSION_COOKIE_NAME='createlo_session',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_REFRESH_EACH_REQUEST=True
)

# CORS setup
allowed_origins = [
    "https://audit.createlo.in",
    "http://localhost:3000"
]

CORS(app, supports_credentials=True, resources={r"/*": {"origins": allowed_origins}})

# Gemini key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

@app.route('/')
def home():
    return jsonify({"status": "active", "service": "Createlo Audit API"})

@app.route('/submit', methods=['POST', 'OPTIONS'])
def submit():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()

    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        logger.info(f"Received data: {data}")

        if not data:
            return jsonify({"error": "No data received"}), 400

        # Validate required fields
        required_fields = ['website', 'email', 'contactNumber']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return jsonify({"error": "Missing required fields", "missing": missing_fields}), 400

        business_url = data['website']
        if not is_valid_url(business_url):
            return jsonify({"error": "Invalid business URL"}), 400

        prompt = build_createlo_prompt(
            business_url,
            data.get('email'),
            data.get('contactNumber'),
            data.get('businessCategory'),
            data.get('categoryHint'),
            data.get('ownerName'),
            data.get('instagram'),
            data.get('facebook')
        )

        if not GEMINI_API_KEY:
            return jsonify({"error": "API service unavailable"}), 503

        logger.info("Sending prompt to Gemini")
        gemini_response = send_to_gemini(prompt)

        if isinstance(gemini_response, str) and gemini_response.startswith("Error"):
            return jsonify({"error": gemini_response}), 502

        report_data = extract_report_data(gemini_response)
        if not report_data:
            return jsonify({"error": "Could not parse audit report"}), 500

        session['report_data'] = report_data
        return _corsify_actual_response(jsonify({"status": "success", "data": report_data}))

    except Exception as e:
        logger.exception("Unhandled error in /submit")
        return jsonify({"error": "Internal server error"}), 500

# Helper Functions

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def build_createlo_prompt(url, email, phone, category=None, category_hint=None, owner_name=None, instagram=None, facebook=None):
    additional_info = []
    if category: additional_info.append(f"Business Category: {category}")
    if category_hint: additional_info.append(f"Category Hint: {category_hint}")
    if owner_name: additional_info.append(f"Owner Name: {owner_name}")
    if instagram: additional_info.append(f"Instagram Handle: {instagram}")
    if facebook: additional_info.append(f"Facebook Page: {facebook}")

    return f"""
You are a digital marketing audit expert working for the Createlo brand. Your goal is to analyze a business's website and provide insights and actionable next steps that highlight opportunities and encourage engagement with Createlo's services.

I have the following business data:
Business URL: {url}
Business Email: {email}
Business Phone: {phone}
{'\n'.join(additional_info)}

Based *only* on analyzing the content of the Business URL provided ({url}):

Return the data strictly as a single JavaScript constant object declaration named `reportData`. Follow this exact structure precisely:

const reportData = {{
  client: "<Business Name>",
  businessoverview: "<Overview>",
  instagramSummary: "<Estimated Instagram summary>",
  facebookSummary: "<Estimated Facebook summary>",
  instagramScore: 65,
  facebookScore: 70,
  overallScore: 67.5,
  businesssummary: "<Combined summary>",
  insights: [
    "<Insight 1>",
    "<Insight 2>",
    "<Insight 3>"
  ],
  tips: [
    "<Tip 1>",
    "<Tip 2>",
    "<Tip 3>"
  ]
}};
"""

def send_to_gemini(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}],
            "generationConfig": {"temperature": 0.7, "topP": 0.9, "topK": 40}
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error calling Gemini API: {str(e)}"

def extract_report_data(response_text):
    try:
        start = response_text.find("const reportData = {")
        if start == -1:
            return None
        obj_str = response_text[start:].split("const reportData = ")[1].strip().rstrip(";")
        # Replace JS-style keys and remove trailing commas
        obj_str = re.sub(r'(\w+):', r'"\1":', obj_str)
        obj_str = re.sub(r",\s*([}\]])", r"\1", obj_str)
        return json.loads(obj_str)
    except Exception as e:
        logger.error(f"Failed to extract JSON: {e}")
        return None

def _build_cors_preflight_response():
    origin = request.headers.get('Origin')
    if origin not in allowed_origins:
        return jsonify({"error": "Origin not allowed"}), 403
    response = jsonify({"message": "CORS preflight"})
    response.headers.update({
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    })
    return response

def _corsify_actual_response(response):
    origin = request.headers.get('Origin')
    if origin in allowed_origins:
        response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)
