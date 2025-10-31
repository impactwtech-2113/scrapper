# app.py — concise single-file LinkedIn scraper (uses RapidAPI scraper)
import os
import time
import random
from urllib.parse import quote_plus, urlparse
import requests
import streamlit as st
import json

st.title("LinkedIn JSON Scraper (compact)")

# ---------- Config (same endpoint you used) ----------
HOST = "linkedin-scraper-api-real-time-fast-affordable.p.rapidapi.com"
BASE_URL = f"https://{HOST}/profile/detail?username={{slug}}"

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 18
MAX_RETRIES_PER_KEY = 1   # extra retries per key (1 means try twice per key)
TRANSIENT_STATUSES = {408, 425, 500, 502, 503, 504}
QUOTA_STATUSES = {429, 401, 403}

HEADERS_BASE = {
    "x-rapidapi-host": HOST,
    "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
    "User-Agent": "streamlit-linkedin-json-scraper/1.0",
}

# ---------- Keys: read from env RAPIDAPI_KEYS (comma-separated) ----------
def _get_api_keys():
    raw = os.getenv("RAPIDAPI_KEYS") or os.getenv("RAPIDAPI_KEY") or ""
    # Example: export RAPIDAPI_KEYS="key1,key2"
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    # Optional fallback (only for local quick testing — remove in production)
    API_KEYS_FALLBACK = []  # e.g. ["your_key_here"]
    return keys or API_KEYS_FALLBACK

# ---------- Small helpers ----------
def normalize_slug(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if t.startswith("http"):
        try:
            p = urlparse(t)
            segs = [s for s in p.path.split("/") if s]
            if segs:
                return segs[-1].strip("/")
        except Exception:
            pass
    return t

def _call_once(slug: str, api_key: str) -> requests.Response:
    headers = dict(HEADERS_BASE)
    headers["x-rapidapi-key"] = api_key
    url = BASE_URL.format(slug=quote_plus(slug))
    return requests.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

def fetch_profile(slug: str):
    keys = _get_api_keys()
    if not keys:
        raise RuntimeError("No API keys found. Set RAPIDAPI_KEYS or RAPIDAPI_KEY environment variable.")
    # keep primary and shuffle secondaries
    ordered = list(keys)
    if len(ordered) > 1:
        ordered = [ordered[0]] + random.sample(ordered[1:], len(ordered)-1)
    last_err = None
    for i, key in enumerate(ordered, start=1):
        tries = 0
        while tries <= MAX_RETRIES_PER_KEY:
            tries += 1
            try:
                resp = _call_once(slug, key)
            except requests.RequestException as e:
                last_err = f"Network error with key #{i}: {e}"
                time.sleep(0.5 * tries)
                continue
            status = resp.status_code
            if status == 200:
                try:
                    return resp.json()
                except ValueError:
                    raise RuntimeError("Invalid JSON returned by API.")
            if status in QUOTA_STATUSES:
                last_err = f"Quota/Unauthorized {status} with key #{i}"
                break  # move to next key
            if status in TRANSIENT_STATUSES:
                last_err = f"Transient {status} with key #{i}, retrying..."
                time.sleep(0.5 * tries)
                continue
            last_err = f"API error {status}: {resp.text[:200]}"
            break
    raise RuntimeError(f"All keys failed. Last error: {last_err}")

# ---------- UI ----------
user_input = st.text_input("Enter LinkedIn vanity handle or profile URL", placeholder="vidhant-jain or https://linkedin.com/in/vidhant-jain/")
if st.button("Submit") and user_input.strip():
    slug = normalize_slug(user_input)
    if not slug:
        st.error("Couldn't parse slug from input.")
    else:
        st.info(f"Fetching profile for: {slug}")
        try:
            data = fetch_profile(slug)
        except Exception as e:
            st.error(f"Fetch error: {e}")
        else:
            st.success("Fetched successfully.")
            st.subheader("Raw JSON")
            st.json(data)
            # quick simplified view
            def extract_simple(d: dict):
                name = d.get("name") or d.get("full_name") or (d.get("profile") or {}).get("name")
                headline = d.get("headline") or (d.get("profile") or {}).get("headline")
                location = d.get("location") or (d.get("profile") or {}).get("location")
                # pick top experience if present
                exp = None
                if isinstance(d.get("experience"), list) and d.get("experience"):
                    exp = d["experience"][0]
                else:
                    p = d.get("profile") or {}
                    if isinstance(p.get("experience"), list) and p.get("experience"):
                        exp = p["experience"][0]
                company = exp.get("company") if exp else None
                title = exp.get("title") if exp else None
                return {"name": name, "headline": headline, "location": location, "current_company": company, "current_title": title, "profile_slug": slug}
            try:
                summary = extract_simple(data)
                st.table([summary])
            except Exception:
                st.write("Could not produce summary.")
            # small download
            st.download_button("Download JSON", data=json.dumps(data, indent=2), file_name=f"{slug}.json", mime="application/json")

st.markdown("---")
st.markdown("**Notes:** Set `RAPIDAPI_KEYS` env var (comma-separated) or `RAPIDAPI_KEY`. Do NOT commit secrets to GitHub.")
