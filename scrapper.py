import os
import json
import time
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st

# 🔑 Paste your RapidAPI key below (Line 7)
RAPIDAPI_KEY = "PASTE_YOUR_RAPIDAPI_KEY_HERE"

# 🚀 Base config
HOST = "linkedin-scraper-api-real-time-fast-affordable.p.rapidapi.com"
BASE_URL = f"https://{HOST}/profile/detail?username={{slug}}"

HEADERS = {
    "x-rapidapi-host": HOST,
    "x-rapidapi-key": RAPIDAPI_KEY,
    "Accept": "application/json",
    "User-Agent": "streamlit-linkedin-json-scraper/1.0",
}

# Streamlit UI setup
st.set_page_config(page_title="LinkedIn JSON Scraper", page_icon="🔍", layout="centered")
st.title("🔍 LinkedIn JSON Scraper")
st.markdown("Enter a LinkedIn profile URL or username to get structured JSON data.")

user_input = st.text_input(
    "Enter LinkedIn profile URL or username:",
    placeholder="e.g. https://linkedin.com/in/neal-mohan or neal-mohan",
)

def normalize_slug(text: str) -> str:
    """Extract slug from full LinkedIn URL or return username directly."""
    t = text.strip()
    if t.startswith("http"):
        try:
            p = urlparse(t)
            segs = [s for s in p.path.split("/") if s]
            if segs:
                return segs[-1].strip("/")
        except Exception:
            pass
    return t

def fetch_profile(slug: str):
    """Call RapidAPI LinkedIn scraper and return JSON data."""
    url = BASE_URL.format(slug=quote_plus(slug))
    response = requests.get(url, headers=HEADERS, timeout=(10, 20))
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"API Error: {response.status_code} - {response.text}")
        return None

if st.button("Submit") and user_input.strip():
    slug = normalize_slug(user_input)
    st.info(f"Fetching LinkedIn data for **{slug}**... ⏳")

    data = fetch_profile(slug)

    if data:
        st.success("Profile data fetched successfully! ✅")

        # --- Extracting key fields for summary ---
        name = data.get("fullName") or data.get("name") or "N/A"
        headline = data.get("headline") or "N/A"
        location = data.get("location") or "N/A"
        about = data.get("about") or "N/A"
        exp_list = data.get("experience", [])
        edu_list = data.get("education", [])

        # --- Display formatted summary ---
        st.subheader("👤 Profile Summary")
        st.write(f"**Name:** {name}")
        st.write(f"**Headline:** {headline}")
        st.write(f"**Location:** {location}")
        st.write(f"**About:** {about}")

        st.markdown("### 💼 Experience")
        if exp_list:
            for exp in exp_list:
                st.markdown(f"- **{exp.get('title', '')}**, {exp.get('company', '')} ({exp.get('duration', '')})")
        else:
            st.write("No experience data found.")

        st.markdown("### 🎓 Education")
        if edu_list:
            for edu in edu_list:
                st.markdown(f"- **{edu.get('school', '')}**, {edu.get('degree', '')}")
        else:
            st.write("No education data found.")

        # --- Raw JSON Output ---
        st.markdown("### 🧾 Full JSON Response")
        st.json(data)
