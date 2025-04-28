import os
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import requests
import json
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configure CORS for your React app's domains
CORS(app,
     supports_credentials=True,
     resources={
         r"/*": {
             "origins": ["https://universal-auditor-frontend.onrender.com", "http://localhost:3000"],
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Content-Type"],
             "max_age": 600
         }
     })

# Enhanced session configuration
app.config.update(
    SESSION_COOKIE_NAME='createlo_session',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_REFRESH_EACH_REQUEST=True
)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

@app.route('/')
def home():
    return "Flask Backend Running - Connected to React Frontend"

@app.route('/submit', methods=['POST', 'OPTIONS'])
def submit():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    try:
        data = request.get_json()
        print("Received data:", data)
        
        if not data:
            return jsonify({"error": "No data received"}), 400

        required_fields = ['business_url', 'business_email', 'business_phone']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        prompt = build_prompt(data['business_url'], data['business_email'], data['business_phone'])
        gemini_response = send_to_gemini(prompt)
        
        if isinstance(gemini_response, str) and gemini_response.startswith("Error"):
            return jsonify({"error": gemini_response}), 500

        report_data = parse_js_object(gemini_response)
        session['report_data'] = report_data
        print("Session data stored:", report_data)

        response = jsonify({
            "redirect_url": "/result",
            "message": "Analysis complete"
        })
        return _corsify_actual_response(response)

    except Exception as e:
        print("Error in submit:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/result')
def result():
    try:
        report_data = session.get('report_data')
        print("Session data retrieved:", report_data)
        
        if not report_data:
            return render_template('error.html', 
                                message="Session expired or no data found. Please submit the form again.")
            
        return render_template('result.html', report_data=report_data)
    except Exception as e:
        print("Error in result:", str(e))
        return render_template('error.html', message=str(e))

def _build_cors_preflight_response():
    response = jsonify({"message": "CORS preflight"})
    response.headers.add("Access-Control-Allow-Origin", "https://universal-auditor-frontend.onrender.com")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "https://universal-auditor-frontend.onrender.com")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

def build_prompt(url, email, phone):
    return f"""
    [Your existing prompt template...]
    """

def send_to_gemini(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        response = requests.post(url, json={
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        })
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error calling Gemini API: {str(e)}"

def parse_js_object(js_string):
    try:
        start = js_string.find('{')
        end = js_string.rfind('}') + 1
        json_str = js_string[start:end]
        return json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Failed to parse response: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
