from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Allow cross-origin requests from the frontend

app.secret_key = "irshadali"  # For session management

GEMINI_API_KEY = "AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY"  # Your Gemini API key

# ======================== ROUTES ========================

@app.route('/submit', methods=['POST'])
def submit():
    # Print the incoming data for debugging
    data = request.get_json()
    print("Received data:", data)  # This will print the received JSON data in the server logs

    # Extract required fields from the received data
    business_url = data.get('business_url')
    business_email = data.get('business_email')
    business_phone = data.get('business_phone')

    # Check if any required field is missing
    if not (business_url and business_email and business_phone):
        return jsonify({"error": "Missing required fields"}), 400

    # Save user data (this can be expanded to save in a database if needed)
    save_user_data(business_url, business_email, business_phone)

    # Build the prompt based on the received data
    prompt = build_prompt(business_url, business_email, business_phone)

    # Send the prompt to the Gemini API and retrieve the result
    report_data = send_to_gemini(prompt)

    if isinstance(report_data, str) and report_data.startswith("Error"):
        return jsonify({"error": report_data}), 500  # In case of Gemini API failure

    # Save the report data in session
    session['report_data'] = report_data

    # Return redirect_url to the frontend (React handles the actual redirect)
    return jsonify({"redirect_url": "/result"})

@app.route('/result')
def result():
    # Fetch the report data from session
    report_data = session.get('report_data')

    if report_data is None:
        return jsonify({"error": "No report found. Please submit the form first."}), 400

    # Directly return the report data to be used in React (for rendering the result page)
    return jsonify({"report": report_data})

# ======================== HELPER FUNCTIONS ========================

def save_user_data(url, email, phone):
    # Save the data to a JSON file (can be expanded to a database in a real-world scenario)
    data = {"url": url, "email": email, "phone": phone}
    with open('user_data.json', 'a') as f:
        f.write(json.dumps(data) + "\n")

def build_prompt(business_url, business_email, business_phone):
    # Build the prompt for Gemini API based on received data
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
    # Send the prompt to Gemini API and get the result
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            return "Error: Gemini API call failed"

        result = response.json()
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        return text_response
    except Exception as e:
        return f"Error: {str(e)}"

# ======================== MAIN ========================

if __name__ == '__main__':
    app.run(debug=True)
