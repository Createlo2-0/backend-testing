from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
CORS(app, 
     supports_credentials=True,
     resources={
         r"/submit": {"origins": "*"},
         r"/result": {"origins": "*"}
     })

app.secret_key = os.environ.get("SECRET_KEY", "irshadali")  # Change this for production
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

GEMINI_API_KEY = os.environ.get("AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY")  # Set this in your environment variables

@app.route('/')
def index():
    return "Flask Backend is Running"

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        business_url = data.get('business_url')
        business_email = data.get('business_email')
        business_phone = data.get('business_phone')

        if not (business_url and business_email and business_phone):
            return jsonify({"error": "Missing required fields"}), 400

        save_user_data(business_url, business_email, business_phone)
        prompt = build_prompt(business_url, business_email, business_phone)
        report_data = send_to_gemini(prompt)

        if isinstance(report_data, str) and report_data.startswith("Error"):
            return jsonify({"error": report_data}), 500

        # Parse the JavaScript object string to Python dict
        report_dict = parse_js_object(report_data)
        session['report_data'] = report_dict

        return jsonify({"redirect_url": "/result"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/result')
def result():
    report_data = session.get('report_data')
    if not report_data:
        return jsonify({"error": "No report found. Please submit the form first."}), 400
    
    return render_template('result.html', report_data=report_data)

def save_user_data(url, email, phone):
    data = {"url": url, "email": email, "phone": phone}
    with open('user_data.json', 'a') as f:
        f.write(json.dumps(data) + "\n")

def build_prompt(business_url, business_email, business_phone):
    prompt = f"""
You are a digital marketing audit expert working for the Createlo brand...
(Business URL: {business_url})
(Business Email: {business_email})
(Business Phone: {business_phone})
Based *only* on analyzing the content of the Business URL provided ({business_url}):
Return the data strictly as a single JavaScript constant object declaration named `reportData`. Follow this exact structure precisely:
const reportData = {{
  client: "<Business Name or Brand inferred from URL or contact info>",
  businessoverview: "<1-2 sentence overview of the business based ONLY on the website content>",
  instagramSummary: "<1-2 sentence ESTIMATION of a typical Instagram presence for this TYPE of business. State clearly if this is an assumption.>",
  facebookSummary: "<1-2 sentence ESTIMATION of a typical Facebook presence for this TYPE of business. State clearly if this is an assumption.>",
  instagramScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60>,
  facebookScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60>,
  overallScore: <Calculate the average of instagramScore and facebookScore>,
  businesssummary: "<2-sentence summary combining the website overview and the ESTIMATED social performance potential>",
  insights: [
    "<Generate several practical and insightful digital marketing feedback points relevant to this TYPE of business, derived from the website analysis>",
    "<Insight 2>",
    "<Insight 3>"
  ],
  tips: [ 
    "<Generate several practical and actionable tips derived DIRECTLY from the generated 'insights'>",
    "<Tip 2>",
    "<Tip 3>"
  ]
}};
"""
    return prompt

def send_to_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    params = {"key": GEMINI_API_KEY}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    try:
        response = requests.post(url, params=params, json=payload)
        response.raise_for_status()
        text_response = response.json()['candidates'][0]['content']['parts'][0]['text']
        return text_response
    except Exception as e:
        return f"Error: {str(e)}"

def parse_js_object(js_string):
    """Parse the JavaScript object string to Python dictionary"""
    try:
        # Extract the object part from the JS string
        start = js_string.find('{')
        end = js_string.rfind('}') + 1
        json_str = js_string[start:end]
        
        # Convert JS object to valid JSON
        json_str = json_str.replace("const reportData = ", "")
        json_str = json_str.replace(";", "")
        
        # Parse JSON to Python dict
        return json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Failed to parse JavaScript object: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)
