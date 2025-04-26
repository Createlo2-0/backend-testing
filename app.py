from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests
import json

app = Flask(__name__)

GEMINI_API_KEY = "AIzaSyDLrIPX8L-dH1WWiXs7wCB_nKufkKJxGiY"

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form  # Assuming your form sends as form-data (not JSON)
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

    # Store report data in session (or pass to result route via query parameters if it's small enough)
    # For simplicity, I will use session to pass data here
    from flask import session
    session['report_data'] = report_data

    # Redirect to result page
    return redirect(url_for('result'))

@app.route('/result')
def result():
    # Fetch the report data from session
    from flask import session
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
(rest of your prompt here)
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
