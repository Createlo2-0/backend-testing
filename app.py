from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Important to allow sessions with React

app.secret_key = "irshadali"  # For session management

GEMINI_API_KEY = "AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY"  # Your API key

# ======================== ROUTES ========================

@app.route('/submit', methods=['POST'])
def submit():
    # Get data from the POST request
    data = request.get_json()

    # Log the received data to check if it's coming in correctly
    print("Received Data:", data)

    business_url = data.get('business_url')
    business_email = data.get('business_email')
    business_phone = data.get('business_phone')

    # Check if the required fields are missing
    if not (business_url and business_email and business_phone):
        return jsonify({"error": "Missing required fields"}), 400

    # Save user data (this can be expanded to save in a database if needed)
    save_user_data(business_url, business_email, business_phone)

    # Build prompt to send to Gemini API
    prompt = build_prompt(business_url, business_email, business_phone)

    # Send the prompt to Gemini API and retrieve the result
    report_data = send_to_gemini(prompt)

    # If there was an error with the Gemini API, return error
    if isinstance(report_data, str) and report_data.startswith("Error"):
        return jsonify({"error": report_data}), 500  # In case of Gemini API failure

    # Save report data in session
    session['report_data'] = report_data

    # Log to verify if we are returning the correct response
    print("Redirecting to result page...")

    # Return the redirect URL to the frontend
    return jsonify({"redirect_url": "/result"})  # This is correct for React to handle redirection

@app.route('/result')
def result():
    # Get the report data from the session
    report_data = session.get('report_data')

    # If no report data is found, show an error
    if report_data is None:
        return "No report found. Please submit the form first.", 400

    # Render the result page with the report data
    return render_template('result.html', report=report_data)

# ======================== HELPER FUNCTIONS ========================

def save_user_data(url, email, phone):
    # Save the user data into a file (this can be replaced with a database)
    data = {"url": url, "email": email, "phone": phone}
    with open('user_data.json', 'a') as f:
        f.write(json.dumps(data) + "\n")

def build_prompt(business_url, business_email, business_phone):
    # Build the prompt for the Gemini API based on the user's input
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
    "<Generate several practical and actionable tips derived DIRECTLY from the generated 'insights'. Each tip should identify a specific area for improvement or opportunity related to their online presence (as inferred from the website) and suggest a relevant action. FRAME these tips to naturally lead into recommending a Createlo service (like booking a call, requesting an audit/quote, starting a test campaign) as the solution or next step. Maintain a professional, encouraging, yet action-oriented tone.>",
    "<Tip 2>",
    "<Tip 3>"
  ]
}}};

**Guidance for Generating 'tips':**

* **Link to Insights:** Each tip *must* clearly relate to one of the generated `insights`.
* **Incorporate CTAs:** Blend the recommendation with a relevant Createlo call to action.
* **Maintain Tone:** Be professional, helpful, and action-oriented. Avoid overly aggressive language like "afraid" or "scared," but convey opportunity.

**Examples of desired blended tip style:**
* "Insight suggests website lacks clear calls-to-action. Tip: Consider optimizing your website CTAs to boost lead generation - let's schedule a quick call in the next 24 hours to discuss how?"
* "Based on the insight about potential competitor strategies, Tip: Request a competitive social media audit to uncover hidden growth opportunities before rivals capitalize on them."
* "Insight noted potential for visual content. Tip: Why not run a small test campaign showcasing your [product/service] visually on Instagram? Request a quote for a targeted campaign today."
* "Insight identified opportunity for [Specific Tactic]. Tip: Let's explore implementing [Specific Tactic] together - book a consultation this week to identify quick wins."

**CRITICAL REQUIREMENTS (Remain the Same):**
1. Use Business URL: Analyze {business_url} for `client`, `businessoverview`, and `insights`.
2. Estimate Social Sections: Generate plausible ESTIMATIONS for social summaries and scores based on business type. Note assumptions.
3. Score Constraint: Ensure `instagramScore` and `facebookScore` are numbers >= 60. `overallScore` is the average.
4. Insights: Provide practical insights based on website analysis.
5. Tips Generation: Generate tips based on insights, integrating Createlo CTAs as guided above.
"""
    return prompt

def send_to_gemini(prompt):
    # Send the prompt to the Gemini API to get the result
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
    response = requests.post(url, headers=headers, json=payload)

    # If the response status is not 200, return an error
    if response.status_code != 200:
        return "Error: Gemini API call failed"

    # Extract and return the response content
    result = response.json()
    text_response = result['candidates'][0]['content']['parts'][0]['text']
    return text_response

# ======================== MAIN ========================

if __name__ == '__main__':
    app.run(debug=True)
