import os
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import requests
import json
from datetime import timedelta
import logging
from urllib.parse import urlparse

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App configuration
app.secret_key = os.environ.get('SECRET_KEY', 'irshadali')
app.config.update(
    SESSION_COOKIE_NAME='createlo_session',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Enhanced CORS configuration
CORS(app,
     supports_credentials=True,
     resources={
         r"/*": {
             "origins": ["https://audit.createlo.in", "http://localhost:3000","http://localhost:3000/audit-form","http://localhost:3000/business-summary"
 ],
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Content-Type"],
             "max_age": 600
         }
     })

# API Keys
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY')

@app.route('/')
def home():
    return jsonify({"status": "active", "service": "Createlo Audit API"})

@app.route('/submit', methods=['POST', 'OPTIONS'])
def submit():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    try:
        data = request.get_json()
        logger.info(f"Received request with data: {data}")
        
        if not data:
            return jsonify({"error": "No data received"}), 400

        required_fields = ['business_url', 'business_email', 'business_phone']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "error": "Missing required fields",
                "missing": missing_fields
            }), 400

        # Build the exact prompt as specified
        prompt = build_createlo_prompt(
            data['business_url'],
            data.get('business_email', ''),
            data.get('business_phone', '')
        )
        
        logger.info("Sending request to Gemini API")
        gemini_response = send_to_gemini(prompt)
        
        if isinstance(gemini_response, str) and gemini_response.startswith("Error"):
            logger.error(f"Gemini API error: {gemini_response}")
            return jsonify({"error": gemini_response}), 502

        # Extract the reportData object from the response
        report_data = extract_report_data(gemini_response)
        if not report_data:
            return jsonify({"error": "Could not parse audit report"}), 500

        session['report_data'] = report_data
        logger.info("Successfully generated audit report")

        return _corsify_actual_response(jsonify({
            "status": "success",
            "data": report_data
        }))

    except Exception as e:
        logger.error(f"Error in submit: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

def build_createlo_prompt(url, email, phone):
    """Build the exact prompt as specified in requirements"""
    return f"""
You are a digital marketing audit expert working for the Createlo brand. Your goal is to analyze a business's website and provide insights and actionable next steps that highlight opportunities and encourage engagement with Createlo's services.

I have the following business data:
Business URL: {url}
Business Email: {email}
Business Phone: {phone}

Based *only* on analyzing the content of the Business URL provided ({url}):

Return the data strictly as a single JavaScript constant object declaration named `reportData`. Follow this exact structure precisely:

const reportData = {{
  client: "<Business Name or Brand inferred from URL or contact info>",
  businessoverview: "<1-2 sentence overview of the business based ONLY on the website content>",
  instagramSummary: "<1-2 sentence ESTIMATION of a typical Instagram presence for this TYPE of business. State clearly if this is an assumption.>",
  facebookSummary: "<1-2 sentence ESTIMATION of a typical Facebook presence for this TYPE of business. State clearly if this is an assumption.>",
  instagramScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60, based on assumptions about typical social strategy for this business type>,
  facebookScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60, based on assumptions about typical social strategy for this business type>,
  overallScore: <Calculate the average of instagramScore and facebookScore>,
  businesssummary: "<2-sentence summary combining the website overview and the ESTIMATED social performance potential>",
  insights: [
    "<Generate several practical and insightful digital marketing feedback points relevant to this TYPE of business, derived from the website analysis>",
    "<Insight 2>",
    "<Insight 3>"
  ],
  tips: [
    "<Generate several practical and actionable tips derived DIRECTLY from the generated 'insights'. Each tip should identify a specific area for improvement or opportunity related to their online presence and suggest a relevant Createlo service as the solution.>",
    "<Tip 2>",
    "<Tip 3>"
  ]
}};
"""

def extract_report_data(gemini_response):
    """Extract the reportData object from the Gemini response"""
    try:
        # Find the reportData declaration
        start = gemini_response.find("const reportData = {")
        if start == -1:
            logger.error("Could not find reportData in response")
            return None
        
        # Extract the object part
        obj_start = gemini_response.find("{", start)
        obj_end = gemini_response.rfind("}") + 1
        json_str = gemini_response[obj_start:obj_end]
        
        # Parse the JSON
        report_data = json.loads(json_str)
        
        # Validate required fields
        required_fields = [
            'client', 'businessoverview', 'instagramSummary', 
            'facebookSummary', 'instagramScore', 'facebookScore',
            'overallScore', 'businesssummary', 'insights', 'tips'
        ]
        
        for field in required_fields:
            if field not in report_data:
                logger.error(f"Missing required field in report: {field}")
                return None
                
        return report_data
        
    except Exception as e:
        logger.error(f"Error extracting report data: {str(e)}")
        return None

def send_to_gemini(prompt):
    """Send request to Gemini API"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "topK": 40
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error calling Gemini API: {str(e)}"

def _build_cors_preflight_response():
    response = jsonify({"message": "CORS preflight"})
    response.headers.add("Access-Control-Allow-Origin", "https://audit.createlo.in")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "https://audit.createlo.in")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
