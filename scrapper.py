# linkedin_scraper_with_auth.py
import os
import json
import time
import random
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse
from typing import Optional, List, Dict

import requests
import streamlit as st

# -------------------- USER CONFIG (TOP LINES) --------------------
# Paste your RapidAPI key here (replace the placeholder string)
# Keep the key here (or set via env var RAPIDAPI_PRIMARY_KEY) - do NOT commit real keys to public repos
RAPIDAPI_PRIMARY_KEY = "41f26fb2cdmsh8238befe9b85fe0p10a4cbjsn25675cbc4986"

# Change this password to whatever you want. Users must enter this to get 15 days access.
APP_PASSWORD = "2113"

# Token filename (keeps local token/expiry). If deploying to cloud, token will live in working dir.
TOKEN_FILE = ".linkedin_scraper_auth.json"
EXPIRY_DAYS = 15
# ----------------------------------------------------------------

# -------------------- API / APP CONFIG ---------------------------
HOST = "linkedin-scraper-api-real-time-fast-affordable.p.rapidapi.com"
BASE_URL = f"https://{HOST}/profile/detail?username={{slug}}"

def _val(name: str, default: str) -> str:
    return os.getenv(name) or default

# API keys list - keep first as placeholder above for convenience.
API_KEYS = [
    _val("RAPIDAPI_PRIMARY_KEY", RAPIDAPI_PRIMARY_KEY),
    _val("RAPIDAPI_BACKUP_KEY", ""),
    _val("RAPIDAPI_KEY_3", ""),
    _val("RAPIDAPI_KEY_4", ""),
]

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 18
MAX_RETRIES_PER_KEY = 2  # additional retries beyond the first attempt

TRANSIENT_STATUSES = {408, 425, 500, 502, 503, 504}
QUOTA_STATUSES = {429, 401, 403}

HEADERS_BASE = {
    "x-rapidapi-host": HOST,
    "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
    "User-Agent": "streamlit-linkedin-json-scraper/1.0",
}
# ----------------------------------------------------------------

# -------------------- AUTH TOKEN HELPERS -------------------------
def is_token_valid(token_file: str = TOKEN_FILE) -> bool:
    """Return True if a local token file exists and expiry is in future."""
    if not os.path.exists(token_file):
        return False
    try:
        with open(token_file, "r") as f:
            data = json.load(f)
        expiry_iso = data.get("expiry")
        if not expiry_iso:
            return False
        expiry = datetime.fromisoformat(expiry_iso)
        return datetime.now() < expiry
    except Exception:
        return False

def create_token(token_file: str = TOKEN_FILE, days: int = EXPIRY_DAYS) -> None:
    """Create/update token with expiry days from now."""
    expiry = datetime.now() + timedelta(days=days)
    payload = {"expiry": expiry.isoformat()}
    with open(token_file, "w") as f:
        json.dump(payload, f)

def clear_token(token_file: str = TOKEN_FILE) -> None:
    """Remove local token file to force re-authentication."""
    try:
        if os.path.exists(token_file):
            os.remove(token_file)
    except Exception:
        pass
# ----------------------------------------------------------------

# -------------------- UTILITY HELPERS ----------------------------
def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def normalize_slug(text: str) -> str:
    """Extract slug if full URL given, else return trimmed text."""
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

def call_api_once(slug: str, api_key: str) -> requests.Response:
    """Perform single GET request to RapidAPI endpoint using provided api_key."""
    headers = dict(HEADERS_BASE)
    headers["x-rapidapi-key"] = api_key
    url = BASE_URL.format(slug=quote_plus(slug))
    return requests.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

def try_fetch_with_key_rotation(slug: str, api_keys: List[str]) -> (Optional[Dict], List[str]):
    """
    Try to fetch profile JSON by rotating through provided keys.
    Returns (data or None, logs).
    """
    logs = []
    for key_index, api_key in enumerate(api_keys, start=1):
        if not api_key:
            logs.append(f"Key {key_index}: skipped (empty key).")
            continue

        attempt = 0
        while attempt <= MAX_RETRIES_PER_KEY:
            attempt += 1
            try:
                res = call_api_once(slug, api_key)
            except requests.RequestException as e:
                logs.append(f"Key {key_index} attempt {attempt}: RequestException - {e}")
                # wait a bit before retry
                time.sleep(0.5 + random.random())
                continue

            status = res.status_code
            text_snip = (res.text[:300] + "...") if len(res.text) > 300 else res.text

            if status == 200:
                try:
                    return res.json(), logs
                except Exception as e:
                    logs.append(f"Key {key_index} attempt {attempt}: JSON decode error - {e}")
                    return None, logs

            # handle transient vs quota vs permanent errors
            if status in TRANSIENT_STATUSES and attempt <= MAX_RETRIES_PER_KEY:
                logs.append(f"Key {key_index} attempt {attempt}: transient {status} - retrying")
                # exponential-ish backoff
                time.sleep(0.5 * attempt + random.random())
                continue
            elif status in QUOTA_STATUSES:
                logs.append(f"Key {key_index}: quota/unauthorized {status} - {text_snip}")
                # Stop using this key; break to next key.
                break
            else:
                logs.append(f"Key {key_index} attempt {attempt}: {status} - {text_snip}")
                # For other status codes, do not retry heavily.
                break
        # next key
    return None, logs
# ----------------------------------------------------------------

# -------------------- STREAMLIT UI -------------------------------
st.set_page_config(page_title="LinkedIn JSON Scraper (Auth)", layout="centered")
# Authentication gate
if not is_token_valid():
    st.title("🔒 Access required")
    st.markdown("This tool is password-protected. Enter the password to get **15 days** access.")
    pwd = st.text_input("Enter password:", type="password", key="pwd_input")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Submit"):
            if pwd == APP_PASSWORD:
                create_token()
                st.success(f"Access granted — valid for {EXPIRY_DAYS} days.")
                st.experimental_rerun()
            else:
                st.error("Incorrect password.")
    with col2:
        if st.button("Reset token (clear)"):
            clear_token()
            st.info("Token cleared (if existed).")
    st.caption("If you lose access, re-enter the password to renew the 15-day window.")
    st.stop()  # prevents the rest of the app from running until authenticated

# If we reach here, token is valid
st.title("LinkedIn JSON Scraper")
top_msg = st.empty()  # banner placeholder

# Provide a small logout/reset option
if st.button("🔐 Log out / Clear access token"):
    clear_token()
    st.success("Access token cleared. Please refresh to re-authenticate.")
    st.experimental_rerun()

st.markdown("Enter a LinkedIn profile URL or username (vanity handle). Example: `https://linkedin.com/in/neal-mohan` or `neal-mohan`.")

user_input = st.text_input(
    "LinkedIn vanity handle or profile URL",
    placeholder="e.g. vidhant-jain or https://linkedin.com/in/vidhant-jain/",
)

col_a, col_b = st.columns([3, 1])
with col_b:
    raw_toggle = st.checkbox("Show raw JSON", value=True)

if st.button("Submit") and user_input.strip():
    slug = normalize_slug(user_input)
    top_msg.info(f"Fetching LinkedIn data for **{slug}**... ⏳")

    data, logs = try_fetch_with_key_rotation(slug, API_KEYS)

    if data:
        top_msg.success("Profile data fetched successfully! ✅")

        # --- Display summary view (attempt to map common keys) ---
        # These keys may differ depending on API response. We try several common names.
        def first(*keys, d=data, default="N/A"):
            for k in keys:
                v = d.get(k)
                if v:
                    return v
            return default

        name = first("fullName", "name", "displayName")
        headline = first("headline", "title")
        location = first("location", "area", "locationName")
        about = first("about", "summary", "description")

        st.subheader("👤 Profile Summary")
        st.write(f"**Name:** {name}")
        st.write(f"**Headline:** {headline}")
        st.write(f"**Location:** {location}")
        st.write(f"**About:** {about}")

        # Experience
        st.markdown("### 💼 Experience")
        exp_list = data.get("experience") or data.get("experiences") or []
        if isinstance(exp_list, list) and exp_list:
            for idx, exp in enumerate(exp_list, start=1):
                title = exp.get("title") or exp.get("role") or ""
                company = exp.get("company") or exp.get("company_name") or exp.get("employer") or ""
                duration = exp.get("duration") or exp.get("date") or ""
                st.markdown(f"- **{title}**, {company} ({duration})")
        else:
            st.write("No experience data found.")

        # Education
        st.markdown("### 🎓 Education")
        edu_list = data.get("education") or []
        if isinstance(edu_list, list) and edu_list:
            for edu in edu_list:
                school = edu.get("school") or edu.get("institution") or ""
                degree = edu.get("degree") or edu.get("field") or ""
                st.markdown(f"- **{school}**, {degree}")
        else:
            st.write("No education data found.")

        # Show raw JSON if toggle enabled
        if raw_toggle:
            st.markdown("### 🧾 Full JSON Response")
            st.json(data)

        # Download JSON button
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            st.download_button(
                label="⬇️ Download JSON",
                data=json_str,
                file_name=f"{slug}_linkedin_profile.json",
                mime="application/json",
            )
        except Exception as e:
            st.warning(f"Could not enable download: {e}")

    else:
        top_msg.error("❌ Failed to fetch profile data. See logs below.")
        st.write("Logs:")
        for l in logs:
            st.write("-", l)

# End of app
