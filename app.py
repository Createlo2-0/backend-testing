import os
import json
import logging
import re
from urllib.parse import urlparse
from datetime import timedelta

import requests
import json5
from flask import Flask, request, jsonify, session
from flask_cors import CORS

# ─── App & Logging Setup ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("createlo-audit")

# ─── Session Settings ───────────────────────────────────────────────────
app.config.update(
    SESSION_COOKIE_NAME="createlo_session",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
)

# ─── CORS ───────────────────────────────────────────────────────────────
CORS(
    app,
    supports_credentials=True,
    origins=["https://audit.createlo.in", "http://localhost:3000"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"],
)

# ─── Gemini Key ─────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Ensure this key is correctly set in env
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set; /submit will return 503.")

# ─── Utility Validators ─────────────────────────────────────────────────
def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return bool(p.scheme and p.netloc)
    except:
        return False

# ─── Prompt Builder ─────────────────────────────────────────────────────
def build_prompt(data: dict) -> str:
    lines = [
        f"Business URL: {data['website']}",
        f"Contact Email: {data['email']}",
        f"Contact Phone: {data['contactNumber']}"
    ]
    for k in ("businessCategory", "categoryHint", "ownerName", "instagram", "facebook"):
        if data.get(k):
            pretty = k.replace("business", "Business ").title()
            lines.append(f"{pretty}: {data[k]}")

    additional_info_str = "\n".join(lines)
    url = data['website']
    email = data['email']
    phone = data['contactNumber']

    return f"""
You are a digital‐marketing audit expert for Createlo.
Use ONLY the info below—no guesses—to produce a single JS constant `reportData`.
You are a digital marketing audit expert working for the Createlo brand. Your goal is to analyze a business's website and provide insights and actionable next steps that highlight opportunities and encourage engagement with Createlo's services.

I have the following business data:
Business URL: {url}
Business Email: {email}
Business Phone: {phone}
{additional_info_str}

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

# ─── Gemini Caller ──────────────────────────────────────────────────────
def call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.9, "topK": 40},
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    response = r.json()
    raw_text = response["candidates"][0]["content"]["parts"][0]["text"]
    logger.debug("Raw Gemini response:\n%s", raw_text)
    return raw_text

# ─── Extractor ──────────────────────────────────────────────────────────
def parse_report(js: str) -> dict:
    match = re.search(r"const reportData\s*=\s*({.*?});?", js, re.DOTALL)
    if not match:
        raise ValueError("reportData object not found in response")
    obj_str = match.group(1)
    return json5.loads(obj_str)

# ─── Routes ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "service": "createlo‐audit"}), 200

@app.route("/submit", methods=["OPTIONS", "POST"])
def submit():
    if request.method == "OPTIONS":
        return jsonify({}), 204

    if not request.is_json:
        return jsonify(error="Request must be JSON"), 400
    data = request.get_json()
    logger.info("→ Received: %s", data)

    required = ["website", "email", "contactNumber"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify(error="Missing fields", missing=missing), 400

    if not is_valid_url(data["website"]):
        return jsonify(error="Invalid website URL"), 400

    if not GEMINI_API_KEY:
        return jsonify(error="Service unavailable"), 503

    prompt = build_prompt(data)
    try:
        raw = call_gemini(prompt)
        report = parse_report(raw)
    except Exception as e:
        logger.exception("Gemini failure")
        return jsonify(error="Audit generation failed", detail=str(e)), 502

    session["report"] = report
    logger.info("← Success")
    return jsonify(status="success", data=report), 200

# ─── Run Server ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
