import os
import json
import time
import random
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st

st.title("LinkedIn JSON Scraper")
top_msg = st.empty()  # banner placeholder

HOST = "linkedin-scraper-api-real-time-fast-affordable.p.rapidapi.com"
BASE_URL = f"https://{HOST}/profile/detail?username={{slug}}"

def _val(name: str, default: str) -> str:
    return os.getenv(name) or default

API_KEYS = [
    _val("RAPIDAPI_PRIMARY_KEY", "41f26fb2cdmsh8238befe9b85fe0p10a4cbjsn25675cbc4986"),
    _val("RAPIDAPI_BACKUP_KEY", ""),
    _val("RAPIDAPI_KEY_3", ""),
    _val("RAPIDAPI_KEY_4", ""),
]

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 18
MAX_RETRIES_PER_KEY = 2

TRANSIENT_STATUSES = {408, 425, 500, 502, 503, 504}
QUOTA_STATUSES = {429, 401, 403}

HEADERS_BASE = {
    "x-rapidapi-host": HOST,
    "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
    "User-Agent": "streamlit-linkedin-json-scraper/1.0",
}

def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def normalize_slug(text: str) -> str:
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

def call_api(slug: str, api_key: str) -> requests.Response:
    headers = dict(HEADERS_BASE)
    headers["x-rapidapi-key"] = api_key
    url = BASE_URL.format(slug=quote_plus(slug))
    return requests.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

user_input = st.text_input(
    "Enter LinkedIn vanity handle or profile URL",
    placeholder="Sadhana or https://linkedin.com/in/sadhanab13/",
)

if st.button("Submit") and user_input.strip():
    try:
        slug = normalize_slug(user_input)
        success = False
        logs = []

        for i, api_key in enumerate(API_KEYS, start=1):
            try:
                res = call_api(slug, api_key)
                if res.status_code == 200:
                    data = res.json()
                    st.success("✅ Profile fetched successfully!")
                    st.json(data)
                    success = True
                    break
                else:
                    logs.append(f"Key {i}: {res.status_code} - {res.text}")
            except Exception as e:
                logs.append(f"Key {i}: {type(e).__name__} - {e}")

        if not success:
            st.error("❌ All API keys failed. Check logs or subscription.")
            st.write(logs)

    except Exception as e:
        st.error(f"Unexpected error: {type(e).__name__} - {e}")
