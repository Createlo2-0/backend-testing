from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains (or customize as needed)

app.secret_key = "irshadali"  # Required for sessions

GEMINI_API_KEY = "AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY"

@app.route('/submit', methods=['POST'])
def submit():
    # Get the JSON data from the request
    data = request.get_json()  # This reads JSON data from the request body

    business_url = data.get('business_url')
    business_email = data.get('business_email')
    business_phone = data.get('business_phone')

    if not (business_url and business_email and business_phone):
        return jsonify({"error": "Missing required fields"}), 400

    # Save user data
    save_user_data(business_url, business_email, business_phone)

    # Build Gemini Prompt
    prompt = build_prompt(business_url, business_email, business_phone)

    # Send to Gemini
    report_data = send_to_gemini(prompt)

    # Store report data in session
    session['report_data'] = report_data

    # Redirect to result page
    return redirect(url_for('result'))

@app.route('/result')
def result():
    # Fetch the report data from session
    report_data = session.get('report_data', None)
    
    if report_data is None:
        return "No report found. Please submit the form first.", 400
    
    # Render result.html and pass the report_data
    return render_template('result.html', report=report_data)

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
  instagramScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60, based on assumptions about typical social strategy for this business type>,
  facebookScore: <Estimate a score out of 100, ensuring it is NOT LESS THAN 60, based on assumptions about typical social strategy for this business type>,
  overallScore: <Calculate the average of instagramScore and facebookScore>,
  businesssummary: "<2-sentence summary combining the website overview and the ESTIMATED social performance potential>",
  insights: [
    "<Generate several practical and insightful digital marketing feedback points relevant to this TYPE of business, derived from the website analysis>",
    "<Insight 2>",
    "<Insight 3>"
    // Do not limit the number of insights
  ],
  tips: [ 
    // **CRITICAL: Generate tips based on insights, integrating Createlo CTAs.**
    "<Generate several practical and actionable tips derived DIRECTLY from the generated 'insights'. Each tip should identify a specific area for improvement or opportunity related to their online presence (as inferred from the website) and suggest a relevant action. FRAME these tips to naturally lead into recommending a Createlo service (like booking a call, requesting an audit/quote, starting a test campaign) as the solution or next step. Maintain a professional, encouraging, yet action-oriented tone. See examples below.>",
    "<Tip 2>",
    "<Tip 3>"
    // Do not limit the number of tips. Ensure tips directly relate to the insights.
  ]
}};

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
    result = response.json()
    text_response = result['candidates'][0]['content']['parts'][0]['text']
    return text_response

if __name__ == '__main__':
    app.run(debug=True)
