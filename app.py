import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
import edge_tts
import asyncio
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
import numpy as np
import requests
import urllib.parse
import base64
import os
import io
import uuid
import json
import re
import time
import shutil
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except Exception:
    HAS_PYPDF = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except Exception:
    HAS_DDGS = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YT = True
except Exception:
    HAS_YT = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except Exception:
    HAS_GTTS = False

# ==========================================
# 1. PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="KINETUX Ai — Cartoon & AI Studio",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="auto"
)

# ==========================================
# 2. SESSION STATE, CREDITS, REAL OAUTH & REVENUE LEDGER
# ==========================================
def get_env_secret(key_name, default_val=""):
    val = os.getenv(key_name, "").strip()
    if not val:
        try:
            val = st.secrets.get(key_name, "").strip()
        except Exception:
            val = ""
    return val or default_val

defaults = {
    "active_tab": "New chat",
    "show_plus_drawer": False,
    "show_more_pocket": False,
    "show_settings_pocket": False,
    "show_account_switcher": False,
    "show_sidebar_search": False,
    "sidebar_search_q": "",
    "open_msg_menu": None,
    "open_msg_details": None,
    "liked_msgs": {},
    "theme_mode": "Dark",
    "dev_mode": False,
    "model_choice": "Kinetux Auto",
    "active_tool_mode": "",
    "personal_intel_on": True,
    "current_user": None,
    "guest_credits": 6,
    "guest_free_videos": 0,
    "chats": {},
    "active_chat_id": None,
    "library": [],
    "notebooks": ["Untitled notebook"],
    "kinetux_input_box": "",
    "pending_query": "",
    "app_base_url": get_env_secret("APP_BASE_URL", "http://localhost:8509"),
    "gemini_api_key": get_env_secret("GEMINI_API_KEY", ""),
    "fal_api_key": get_env_secret("FAL_KEY", ""),
    "heygen_api_key": get_env_secret("HEYGEN_API_KEY", ""),
    "hedra_api_key": get_env_secret("HEDRA_API_KEY", ""),
    "razorpay_key_id": get_env_secret("RAZORPAY_KEY_ID", ""),
    "razorpay_key_secret": get_env_secret("RAZORPAY_KEY_SECRET", ""),
    "google_client_id": get_env_secret("GOOGLE_CLIENT_ID", ""),
    "google_client_secret": get_env_secret("GOOGLE_CLIENT_SECRET", ""),
    "adsense_pub_id": "ca-pub-XXXXXXXXXXXXXXXX",
    "admob_app_id": "ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX"
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def create_new_chat_session():
    cid = str(uuid.uuid4())
    st.session_state.chats[cid] = {
        "title": "New chat",
        "created": datetime.now().strftime("%d %b, %H:%M"),
        "messages": []
    }
    st.session_state.active_chat_id = cid

if not st.session_state.active_chat_id or st.session_state.active_chat_id not in st.session_state.chats:
    create_new_chat_session()

active_chat = st.session_state.chats[st.session_state.active_chat_id]
chat_messages = active_chat["messages"]

DB_FILE = "kinetux_users.json"
LEDGER_FILE = "kinetux_revenue.json"

def load_users():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_users(users):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_collected_inr": 0, "owner_profit_inr": 0, "api_reserve_inr": 0, "transactions": []}

def record_subscription_split(amount_inr, plan_name, user_email):
    led = load_ledger()
    api_cut = round(amount_inr * 0.20, 2)
    owner_cut = round(amount_inr - api_cut, 2)
    led["total_collected_inr"] = round(led.get("total_collected_inr", 0) + amount_inr, 2)
    led["owner_profit_inr"] = round(led.get("owner_profit_inr", 0) + owner_cut, 2)
    led["api_reserve_inr"] = round(led.get("api_reserve_inr", 0) + api_cut, 2)
    led["transactions"].append({
        "time": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "user": user_email,
        "plan": plan_name,
        "total_inr": amount_inr,
        "owner_profit_inr": owner_cut,
        "api_reserve_inr": api_cut
    })
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=4)

users_db = load_users()

# REAL GOOGLE OAUTH CALLBACK (Fetches Actual Gmail, Name & Profile Photo)
if "code" in st.query_params and st.session_state.google_client_id and st.session_state.google_client_secret:
    auth_code = st.query_params["code"]
    if auth_code and not st.session_state.current_user:
        try:
            redirect_uri = st.session_state.app_base_url.rstrip("/")
            token_res = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": auth_code,
                    "client_id": st.session_state.google_client_id,
                    "client_secret": st.session_state.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                },
                timeout=10
            ).json()
            access_token = token_res.get("access_token")
            if access_token:
                u_info = requests.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10
                ).json()
                em_oauth = u_info.get("email", "")
                real_name = u_info.get("name", em_oauth.split("@")[0])
                pic_url = u_info.get("picture", "")
                if em_oauth:
                    if em_oauth not in users_db:
                        users_db[em_oauth] = {
                            "name": real_name,
                            "picture": pic_url,
                            "provider": "Google",
                            "plan": "free",
                            "credits": 6,
                            "videos_created": 0
                        }
                    else:
                        users_db[em_oauth]["name"] = real_name
                        users_db[em_oauth]["picture"] = pic_url
                    save_users(users_db)
                    st.session_state.current_user = em_oauth
        except Exception as e:
            st.toast(f"Google Login Error: {e}")
        st.query_params.clear()
        st.rerun()

def get_active_user():
    em = st.session_state.current_user
    if em and em in users_db:
        if "credits" not in users_db[em]:
            users_db[em]["credits"] = 6
        return em, users_db[em]
    return None, {
        "name": "Guest",
        "plan": "free",
        "credits": st.session_state.guest_credits,
        "videos_created": st.session_state.guest_free_videos
    }

@st.cache_data(ttl=3600)
def get_ip_location():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=3).json()
        cc = r.get("country_code", "IN").upper()
        return r.get("ip", "127.0.0.1"), f"{r.get('city', 'India')}, {r.get('country_name', 'IN')}", cc
    except Exception:
        return "127.0.0.1", "India", "IN"

user_ip, user_loc, country_code = get_ip_location()
is_uk_user = country_code in ["GB", "UK"]

starter_price_label = "£6.99 / month" if is_uk_user else "₹99 / month"
pro_price_label = "£19.99 / month" if is_uk_user else "₹499 / month"
starter_btn_label = "Upgrade Starter (£6.99 · +30 Cr)" if is_uk_user else "Upgrade Starter (₹99 · +30 Cr)"
pro_btn_label = "Upgrade Studio Pro (£19.99 · +120 Cr)" if is_uk_user else "Upgrade Studio Pro (₹499 · +120 Cr)"

if country_code not in ["IN", "GB", "UK"] and not st.session_state.dev_mode:
    st.markdown("""
    <div style="text-align:center; padding:90px 20px; color:#E3E3E3; font-family:Inter, sans-serif;">
        <h1 style="font-size:34px; font-weight:500;">✦ KINETUX Ai</h1>
        <p style="font-size:18px; color:#9AA0A6; margin-top:12px;">
            KINETUX Ai is currently available exclusively in <b>India 🇮🇳</b> and the <b>United Kingdom 🇬🇧</b>.
        </p>
        <p style="font-size:13px; color:#64748B;">Detected Region: """ + user_loc + """</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

def consume_cartoon_quota(is_long_movie=False):
    em, u = get_active_user()
    if st.session_state.dev_mode:
        return True, "Developer Mode", True

    plan = u.get("plan", "free")
    vids_done = u.get("videos_created", 0)
    credits = u.get("credits", 0)
    is_paid_member = plan in ["pro_99", "pro_499"]

    if not is_paid_member:
        if is_long_movie:
            return False, f"🔒 **30–60 सेकंड की बड़ी कार्टून फ़िल्म और Real Character Motion** के लिए **Kinetux Starter ({starter_price_label})** या **Studio Pro ({pro_price_label})** प्लान लें!", False
        if vids_done >= 3 or credits < 2:
            return False, f"🎬 आपके **3 फ्री कार्टून/विज्ञापन वीडियो** पूरे हो चुके हैं! आगे और वीडियो बनाने के लिए **Pricing ({starter_price_label} / {pro_price_label})** से प्लान लें।", False

    cost = 4 if is_long_movie else 2
    if credits < cost:
        return False, f"⚠️ आपके पास सिर्फ़ **{credits} Credits** बचे हैं (इस वीडियो के लिए **{cost} Credits** चाहिए)।", False

    if em and em in users_db:
        users_db[em]["credits"] = credits - cost
        users_db[em]["videos_created"] = vids_done + 1
        save_users(users_db)
    else:
        st.session_state.guest_credits = max(0, credits - cost)
        st.session_state.guest_free_videos = vids_done + 1

    return True, "OK", is_paid_member

def consume_credits(cost, min_plan="free"):
    em, u = get_active_user()
    if st.session_state.dev_mode:
        return True, "Developer Mode Bypass"
    if min_plan == "pro_499" and u.get("plan") != "pro_499":
        return False, f"🔒 **HeyGen / Hedra Real Character Motion** के लिए **Kinetux Studio Pro ({pro_price_label})** ज़रूरी है!"
    if u.get("credits", 0) < cost:
        return False, f"⚠️ आपके पास सिर्फ़ **{u.get('credits', 0)} Credits** बचे हैं।"
    if em and em in users_db:
        users_db[em]["credits"] = u.get("credits", 0) - cost
        save_users(users_db)
    else:
        st.session_state.guest_credits = max(0, st.session_state.guest_credits - cost)
    return True, "OK"

has_messages = len(chat_messages) > 0

def handle_enter_submit():
    txt = st.session_state.kinetux_input_box.strip()
    if txt:
        st.session_state.kinetux_input_box = ""
        st.session_state.show_plus_drawer = False
        if not active_chat["messages"]:
            active_chat["title"] = txt[:32] + ("…" if len(txt) > 32 else "")
        active_chat["messages"].append({"role": "user", "content": txt})
        st.session_state.pending_query = txt

# ==========================================
# 3. RESPONSIVE CSS (ANDROID / iOS / WINDOWS / MAC)
# ==========================================
is_light = st.session_state.theme_mode == "Light"
main_bg = "#F8FAFC" if is_light else "radial-gradient(circle at 55% 42%, #0D3B7A 0%, #091B3A 48%, #070E1D 100%)"
sidebar_bg = "#F1F5F9" if is_light else "#1E1F20"
capsule_bg = "#FFFFFF" if is_light else "#202124"
menu_bg = "#FFFFFF" if is_light else "#25262A"
hover_bg = "#E2E8F0" if is_light else "rgba(255,255,255,0.08)"
text_color = "#0F172A" if is_light else "#E3E3E3"
sub_text = "#64748B" if is_light else "#9AA0A6"

dock_css = f"""
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) {{
        position: fixed !important;
        bottom: 24px !important;
        left: 265px !important;
        right: 25px !important;
        max-width: 760px !important;
        margin: 0 auto !important;
        z-index: 9999 !important;
        background-color: {capsule_bg} !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 36px !important;
        padding: 4px 16px !important;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.78) !important;
        align-items: center !important;
    }}
    @media (max-width: 768px) {{
        [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) {{
            left: 12px !important;
            right: 12px !important;
            bottom: 14px !important;
        }}
    }}
    .block-container {{
        padding-bottom: 155px !important;
    }}
""" if has_messages else f"""
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) {{
        background-color: {capsule_bg} !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 36px !important;
        padding: 4px 16px !important;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35) !important;
        align-items: center !important;
    }}
"""

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    header[data-testid="stHeader"] {{ background: transparent !important; }}
    #MainMenu, footer {{ visibility: hidden !important; }}

    .stApp {{
        background: {main_bg} !important;
        color: {text_color} !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        border-right: none !important;
        min-width: 255px !important;
        max-width: 255px !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{
        padding: 0.75rem 0.6rem 72px 0.6rem !important;
    }}
    [data-testid="stSidebar"] [data-testid="stButton"] > button,
    [data-testid="stSidebar"] button {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        color: {text_color} !important;
        text-align: left !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        padding: 7px 14px !important;
        border-radius: 24px !important;
        font-size: 13.5px !important;
        font-weight: 400 !important;
        width: 100% !important;
        min-height: 34px !important;
        margin-bottom: 1px !important;
        white-space: nowrap !important;
    }}
    [data-testid="stSidebar"] button:hover {{
        background-color: {hover_bg} !important;
    }}
    [data-testid="stSidebar"] button[data-active-pill="1"] {{
        background-color: rgba(255, 255, 255, 0.08) !important;
        font-weight: 500 !important;
    }}

    [data-testid="stSidebar"] button[data-big-icon="1"] {{
        width: 38px !important;
        height: 38px !important;
        min-height: 38px !important;
        padding: 0 !important;
        justify-content: center !important;
        border-radius: 50% !important;
    }}

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(button[data-gear-dock="1"]) {{
        position: fixed !important;
        bottom: 0px !important;
        left: 0px !important;
        width: 255px !important;
        background-color: {sidebar_bg} !important;
        border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding: 8px 12px !important;
        z-index: 10002 !important;
        align-items: center !important;
        margin: 0 !important;
    }}

    [data-testid="stHorizontalBlock"]:has([data-testid="stHorizontalBlock"]) {{
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        max-width: 100% !important;
        position: static !important;
    }}

    {dock_css}

    [data-testid="InputInstructions"] {{
        display: none !important;
        visibility: hidden !important;
    }}

    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) * {{
        border: none !important;
        border-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }}
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stTextInput"],
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stTextInput"] > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stTextInput"] > div > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="input"],
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="base-input"],
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) input,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stSelectbox"],
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stSelectbox"] > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-testid="stSelectbox"] > div > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"],
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"] > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"] > div > div,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) button {{
        background-color: transparent !important;
        background: transparent !important;
        color: #E3E3E3 !important;
    }}

    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) input {{
        font-size: 15.5px !important;
        padding-left: 2px !important;
    }}
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) input::placeholder {{
        color: #9AA0A6 !important;
        opacity: 1 !important;
    }}
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"] span,
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"] div {{
        color: #E3E3E3 !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
    }}
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) [data-baseweb="select"] svg {{
        fill: #E3E3E3 !important;
        color: #E3E3E3 !important;
    }}

    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) button {{
        border-radius: 50% !important;
        padding: 4px !important;
        min-height: 40px !important;
        width: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    [data-testid="stHorizontalBlock"]:not(:has([data-testid="stHorizontalBlock"])):has(input[aria-label="Ask Kinetux"]) button:hover {{
        background-color: rgba(255,255,255,0.1) !important;
    }}

    .simple-suggestions,
    .simple-suggestions > div,
    .simple-suggestions [data-testid="stElementContainer"],
    .simple-suggestions [data-testid="stButton"],
    .simple-suggestions [data-testid="stButton"] > button,
    .simple-suggestions button,
    .simple-suggestions ~ div [data-testid="stButton"] > button,
    [data-testid="stVerticalBlock"]:has(.simple-suggestions) [data-testid="stButton"] > button {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        border-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
        color: #F1F5F9 !important;
        text-align: left !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        white-space: nowrap !important;
        padding: 5px 2px !important;
        font-size: 14.5px !important;
        font-weight: 400 !important;
        width: 100% !important;
        min-height: 32px !important;
    }}
    .simple-suggestions button:hover,
    .simple-suggestions ~ div [data-testid="stButton"] > button:hover {{
        background: transparent !important;
        opacity: 0.78 !important;
    }}

    .action-bar-row .stButton > button {{
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: {sub_text} !important;
        padding: 4px 8px !important;
        border-radius: 50% !important;
        min-height: 32px !important;
    }}
    .action-bar-row .stButton > button:hover {{
        background-color: {hover_bg} !important;
        color: {text_color} !important;
    }}

    .three-dot-menu {{
        background-color: {menu_bg};
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 8px;
        max-width: 245px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.65);
        margin-top: 4px;
    }}
    .three-dot-menu .stButton > button {{
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: {text_color} !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 8px 12px !important;
        border-radius: 10px !important;
        font-size: 13.5px !important;
        width: 100% !important;
    }}
    .three-dot-menu .stButton > button:hover {{
        background-color: {hover_bg} !important;
    }}

    .user-msg {{
        background-color: rgba(255,255,255,0.12);
        padding: 12px 18px;
        border-radius: 22px;
        margin: 14px 0;
        max-width: 78%;
        margin-left: auto;
        font-size: 15px;
    }}
    .ai-msg {{
        padding: 10px 4px 4px 4px;
        margin: 14px 0 2px 0;
        font-size: 15px;
        line-height: 1.68;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. ROTATING PLUS (+ -> × 45°) & MENU BELOW + ICON + DIRECT FILE PICKER
# ==========================================
plus_open_js = "true" if st.session_state.show_plus_drawer else "false"
has_msgs_js = "true" if has_messages else "false"
pi_on_js = "true" if st.session_state.personal_intel_on else "false"
active_tab_js = st.session_state.active_tab

components.html(f"""
<script>
const pDoc = window.parent.document;
const isPlusOpen = {plus_open_js};
const hasMessages = {has_msgs_js};
const piOn = {pi_on_js};
const activeTab = "{active_tab_js}";

if (!pDoc.getElementById('kinetux-native-picker')) {{
    const inp = pDoc.createElement('input');
    inp.type = 'file';
    inp.id = 'kinetux-native-picker';
    inp.accept = 'image/*,video/*,.pdf,.txt,.py,.csv,.doc,.docx';
    inp.style.display = 'none';
    inp.onchange = (e) => {{
        const file = e.target.files[0];
        if (!file) return;
        const badge = pDoc.getElementById('kinetux-attached-badge');
        if (badge) {{
            badge.style.display = 'inline-flex';
            badge.innerHTML = '📎 ' + file.name + ' <span id="ktx-clr-file" style="cursor:pointer;margin-left:6px;font-weight:bold;">×</span>';
            pDoc.getElementById('ktx-clr-file').onclick = () => {{
                inp.value = '';
                badge.style.display = 'none';
            }};
        }}
    }};
    pDoc.body.appendChild(inp);
}}

const exactIcons = {{
    "BIG_PLUS": '<svg style="transition:transform 0.22s cubic-bezier(0.4,0,0.2,1); transform:' + (isPlusOpen ? 'rotate(45deg)' : 'rotate(0deg)') + ';" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="2.1" stroke-linecap="round"><line x1="12" y1="4" x2="12" y2="20"></line><line x1="4" y1="12" x2="20" y2="12"></line></svg>',
    "VOICE_MIC": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>',
    "SB_SEARCH": '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="2.1" stroke-linecap="round"><circle cx="11" cy="11" r="7.5"/><line x1="20.5" y1="20.5" x2="16.4" y2="16.4"/></svg>',
    "SB_GEAR": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "SB_NEWCHAT": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg><span>New chat</span></span>',
    "SB_LIBRARY": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg><span>Library</span></span>',
    "SB_IMAGES": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>Images</span></span>',
    "SB_SCHEDULED": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg><span>Scheduled</span></span>',
    "SB_CUSTOMISE": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><polygon points="12 2 21 7 21 17 12 22 3 17 3 7 12 2"/><circle cx="12" cy="12" r="3"/></svg><span>Customise</span></span>',
    "SB_MORE": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg><span>More</span></span>',
    "SB_NEWNB": '<span style="display:inline-flex;align-items:center;gap:14px;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg><span>New notebook</span></span>',
    "SB_SIGNIN": '<span style="display:inline-flex;align-items:center;gap:12px;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><span>Sign in</span></span>',
    "SUGG_1": '<span style="display:inline-flex;align-items:center;gap:12px;white-space:nowrap;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="10 8 16 12 10 16 10 8"/><rect x="3" y="4" width="18" height="16" rx="3"/></svg><span>Ek billi aur chuhe ki 3D cartoon kahani banao</span></span>',
    "SUGG_2": '<span style="display:inline-flex;align-items:center;gap:12px;white-space:nowrap;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>Generate a free 3D Pixar superhero image</span></span>',
    "SUGG_3": '<span style="display:inline-flex;align-items:center;gap:12px;white-space:nowrap;"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg><span>એક નાના હાથી અને પક્ષીની કાર્ટૂન વાર્તા બનાવો</span></span>'
}};

const oldMenu = pDoc.getElementById('kinetux-plus-popover');
if (oldMenu) oldMenu.remove();

if (isPlusOpen) {{
    const styleTag = pDoc.getElementById('kinetux-popover-css') || pDoc.createElement('style');
    styleTag.id = 'kinetux-popover-css';
    styleTag.innerHTML = `
        @keyframes ktxPopDown {{
            from {{ opacity: 0; transform: scale(0.96) translateY(-6px); }}
            to {{ opacity: 1; transform: scale(1) translateY(0); }}
        }}
        .ktx-menu-box {{
            background: rgba(32, 34, 40, 0.98);
            backdrop-filter: blur(18px);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 8px;
            box-shadow: 0 16px 42px rgba(0,0,0,0.75);
            color: #E3E3E3;
            font-family: 'Inter', sans-serif;
            animation: ktxPopDown 0.16s ease-out;
        }}
        .ktx-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.15s;
            user-select: none;
        }}
        .ktx-item:hover {{ background: rgba(255,255,255,0.1); }}
        .ktx-item-left {{ display: flex; align-items: center; gap: 12px; }}
        .ktx-divider {{ height: 1px; background: rgba(255,255,255,0.1); margin: 6px 8px; }}
        .ktx-sub-box {{ position: absolute; left: 244px; width: 255px; display: none; z-index: 100005; }}
        .ktx-trigger-tools:hover .ktx-sub-tools, .ktx-sub-tools:hover {{ display: block !important; }}
        @media (max-width: 768px) {{
            .ktx-sub-box {{ position: static; width: 100%; margin-top: 6px; }}
        }}
    `;
    if (!styleTag.parentNode) pDoc.head.appendChild(styleTag);

    const plusBtnEl = Array.from(pDoc.querySelectorAll('button')).find(b => b.innerText.trim() === 'BIG_PLUS' || b.dataset.isPlusBtn === '1');
    let menuTop = '325px';
    let menuLeft = 'calc(50% - 255px)';
    if (plusBtnEl) {{
        const rect = plusBtnEl.getBoundingClientRect();
        menuLeft = Math.max(12, rect.left) + 'px';
        if (rect.bottom + 340 > window.parent.innerHeight) {{
            menuTop = Math.max(20, rect.top - 330) + 'px';
        }} else {{
            menuTop = (rect.bottom + 10) + 'px';
        }}
    }}

    const pop = pDoc.createElement('div');
    pop.id = 'kinetux-plus-popover';
    Object.assign(pop.style, {{
        position: 'fixed',
        left: menuLeft,
        top: menuTop,
        width: '252px',
        zIndex: '100004'
    }});

    pop.innerHTML = `
        <div class="ktx-menu-box" style="position:relative;">
            <div class="ktx-item" id="ktx-direct-upload-btn">
                <div class="ktx-item-left">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38BDF8" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                    <span><b>Upload Photo / Script</b></span>
                </div>
            </div>
            <div class="ktx-item" data-action="custom_ads">
                <div class="ktx-item-left">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FBBF24" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                    <span style="color:#FDE68A;"><b>Custom Ads Video Maker</b></span>
                </div>
            </div>
            <div class="ktx-divider"></div>
            <div class="ktx-item" data-action="create_image"><div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>Free Image Generator</span></div></div>
            <div class="ktx-item" data-action="create_video"><div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="4" width="20" height="16" rx="2"/><polygon points="10 9 15 12 10 15 10 9"/></svg><span>Cartoon Video (15s Trial)</span></div></div>
            <div class="ktx-item" data-action="create_long_video"><div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#A8C7FA" stroke-width="1.8"><polygon points="12 2 15 9 22 12 15 15 12 22 9 15 2 12 9 9 12 2"/></svg><span style="color:#A8C7FA;">Pro Cartoon Movie (45s)</span></div></div>
            <div class="ktx-item" data-action="avatar"><div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662"/></svg><span>HeyGen Talking Avatar</span></div></div>
            <div class="ktx-item" data-action="create_music"><div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg><span>Lyria Cartoon Music</span></div></div>
            <div class="ktx-item ktx-trigger-tools" style="position:relative;">
                <div class="ktx-item-left"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg><span>More tools</span></div>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                <div class="ktx-menu-box ktx-sub-box ktx-sub-tools" style="bottom:-6px; width:260px;">
                    <div class="ktx-item" data-action="storybook"><div class="ktx-item-left"><span>📖 Storybook Creator</span></div></div>
                    <div class="ktx-item" data-action="deep_research"><div class="ktx-item-left"><span>🔍 Script & Story Writer</span></div></div>
                    <div class="ktx-item" data-action="personal_intel">
                        <div class="ktx-item-left"><div><div>All-Language Detect</div><div style="font-size:11px; color:#9AA0A6;">IN & UK · Hinglish Supported</div></div></div>
                        <div style="width:34px; height:18px; border-radius:12px; background:` + (piOn ? '#A8C7FA' : '#5F6368') + `; display:flex; align-items:center; padding:2px; justify-content:` + (piOn ? 'flex-end' : 'flex-start') + `;"><div style="width:14px; height:14px; border-radius:50%; background:#062E6F;"></div></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    pop.querySelector('#ktx-direct-upload-btn').onclick = (e) => {{
        e.stopPropagation();
        pop.remove();
        const picker = pDoc.getElementById('kinetux-native-picker');
        if (picker) picker.click();
    }};

    pop.querySelectorAll('[data-action]').forEach(el => {{
        el.onclick = (e) => {{
            e.stopPropagation();
            const act = el.getAttribute('data-action');
            const hiddenBtn = Array.from(pDoc.querySelectorAll('button')).find(b => b.innerText.trim() === 'ACT_' + act);
            if (hiddenBtn) hiddenBtn.click();
        }};
    }});

    pDoc.body.appendChild(pop);
}}

setInterval(() => {{
    pDoc.querySelectorAll('button').forEach(btn => {{
        const t = btn.innerText.trim();
        if (exactIcons[t] && !btn.dataset.svgSet) {{
            btn.dataset.svgSet = "1";
            btn.innerHTML = exactIcons[t];
            if (t === "BIG_PLUS") {{
                btn.dataset.isPlusBtn = "1";
            }}
            if (t === "SB_NEWCHAT" && activeTab === "New chat") {{
                btn.setAttribute("data-active-pill", "1");
            }}
            if (t === "SB_SEARCH" || t === "SB_GEAR") {{
                btn.setAttribute("data-big-icon", "1");
            }}
            if (t === "SB_GEAR") {{
                btn.setAttribute("data-gear-dock", "1");
            }}
        }}
        if (t.startsWith('ACT_')) {{
            btn.style.position = 'fixed';
            btn.style.left = '-9999px';
            btn.style.opacity = '0';
        }}
    }});

    pDoc.querySelectorAll('[data-testid="stSidebar"] button').forEach(b => {{
        b.style.border = 'none';
        b.style.boxShadow = 'none';
    }});

    const capInput = pDoc.querySelector('input[aria-label="Ask Kinetux"]');
    const formEl = capInput ? capInput.closest('[data-testid="stHorizontalBlock"]') : null;
    if (formEl) {{
        formEl.querySelectorAll('div, input, button').forEach(el => {{
            el.style.border = 'none';
            el.style.boxShadow = 'none';
            if (el.tagName !== 'BUTTON') el.style.backgroundColor = 'transparent';
        }});
    }}
}}, 180);
</script>
""", height=0)

# ==========================================
# 5. LEFT SIDEBAR (REAL GOOGLE LOGIN + RAZORPAY LEGAL PAGES)
# ==========================================
with st.sidebar:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_file = os.path.join(base_dir, "logo.png")
    logo_b64 = base64.b64encode(open(logo_file, "rb").read()).decode() if os.path.exists(logo_file) else None

    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width:22px; height:22px; object-fit:contain; border-radius:5px;">' if logo_b64 else '''
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 2C12.5 7.5 16.5 11.5 22 12C16.5 12.5 12.5 16.5 12 22C11.5 16.5 7.5 12.5 2 12C7.5 11.5 11.5 7.5 12 2Z" fill="#60A5FA"/>
    </svg>'''

    h_col1, h_col2 = st.columns([3.8, 1])
    with h_col1:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; padding:6px 10px 10px 10px;">
            {logo_html}
            <span style="font-size:17px; font-weight:500; color:{text_color};">KINETUX</span>
        </div>
        """, unsafe_allow_html=True)
    with h_col2:
        if st.button("SB_SEARCH", key="sb_search_toggle", help="Search chats"):
            st.session_state.show_sidebar_search = not st.session_state.show_sidebar_search

    if st.session_state.show_sidebar_search:
        st.session_state.sidebar_search_q = st.text_input("Search chats", value=st.session_state.sidebar_search_q, placeholder="Search chats...", label_visibility="collapsed")

    if st.button("SB_NEWCHAT"):
        st.session_state.active_tab = "New chat"
        create_new_chat_session()
        st.session_state.kinetux_input_box = ""
        st.session_state.pending_query = ""
        st.session_state.active_tool_mode = ""
        st.session_state.show_plus_drawer = False
        st.session_state.show_settings_pocket = False
        st.rerun()
    if st.button("SB_LIBRARY"):
        st.session_state.active_tab = "Library"
        st.session_state.show_settings_pocket = False
    if st.button("SB_IMAGES"):
        st.session_state.active_tab = "Images"
        st.session_state.show_settings_pocket = False
    if st.button("SB_SCHEDULED"):
        st.session_state.active_tab = "Scheduled"
        st.session_state.show_settings_pocket = False
    if st.button("SB_CUSTOMISE"):
        st.session_state.active_tab = "Customise"
        st.session_state.show_settings_pocket = False

    if st.button("SB_MORE"):
        st.session_state.show_more_pocket = not st.session_state.show_more_pocket

    if st.session_state.show_more_pocket:
        if st.button("   📢 Custom Ads Video Maker"):
            st.session_state.active_tab = "Custom_Ads"
            st.session_state.show_more_pocket = False
        if st.button("   🎬 Cartoon Video Studio"):
            st.session_state.active_tab = "Cartoon Studio"
            st.session_state.show_more_pocket = False
        if st.button("   🎭 Avatar & Storybook"):
            st.session_state.active_tab = "Avatar_Storybook"
            st.session_state.show_more_pocket = False
        if st.button("   🎵 Lyria Music Studio"):
            st.session_state.active_tab = "Music_Studio"
            st.session_state.show_more_pocket = False
        if st.button("   👑 Owner Panel & API Keys"):
            st.session_state.active_tab = "Settings_Sub"
            st.session_state.show_more_pocket = False

    # MANDATORY RAZORPAY COMPLIANCE LINKS
    st.markdown(f"<div style='padding:12px 14px 4px 14px; font-size:11.5px; font-weight:500; color:{sub_text};'>Plans & Legal</div>", unsafe_allow_html=True)
    if st.button("💳 Pricing (₹99 / ₹499)"):
        st.session_state.active_tab = "Settings_Sub"
    if st.button("🔒 Privacy Policy"):
        st.session_state.active_tab = "Legal_Privacy"
    if st.button("📜 Terms & Conditions"):
        st.session_state.active_tab = "Legal_Terms"
    if st.button("↩️ Refund Policy"):
        st.session_state.active_tab = "Legal_Refund"
    if st.button("📞 Contact Us"):
        st.session_state.active_tab = "Legal_Contact"

    st.markdown(f"<div style='padding:12px 14px 4px 14px; font-size:11.5px; font-weight:500; color:{sub_text};'>Notebooks</div>", unsafe_allow_html=True)
    if st.button("SB_NEWNB"):
        st.session_state.notebooks.append(f"Untitled notebook #{len(st.session_state.notebooks)+1}")

    for nb in st.session_state.notebooks:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:14px; padding:6px 14px; font-size:13px; color:{text_color}; opacity:0.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#E3E3E3" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            <span>{nb}</span>
        </div>
        """, unsafe_allow_html=True)

    q_filter = st.session_state.sidebar_search_q.strip().lower()
    for cid, cdata in reversed(list(st.session_state.chats.items())):
        if not cdata["messages"] and cid != st.session_state.active_chat_id:
            continue
        title_txt = cdata["title"][:28]
        if q_filter and q_filter not in title_txt.lower():
            continue
        if st.button(f"💬  {title_txt}", key=f"chat_hist_{cid}"):
            st.session_state.active_chat_id = cid
            st.session_state.active_tab = "New chat"
            st.rerun()

    st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)

    curr_email, curr_u = get_active_user()
    plan_badge = {"free": "FREE", "pro_99": "STARTER", "pro_499": "PRO"}.get(curr_u.get("plan", "free"), "FREE")
    cr_left = curr_u.get("credits", 0)

    if st.session_state.show_settings_pocket:
        with st.container(border=True):
            if st.button("👤 Google / Apple Account"):
                st.session_state.show_account_switcher = not st.session_state.show_account_switcher
            if st.button("👑 Owner Panel & API Keys"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button(f"💳 Upgrade ({starter_price_label} / {pro_price_label})"):
                st.session_state.active_tab = "Settings_Sub"
            new_t = st.selectbox("Theme", ["Dark", "Light"], index=["Dark", "Light"].index(st.session_state.theme_mode))
            if new_t != st.session_state.theme_mode:
                st.session_state.theme_mode = new_t
                st.rerun()
            st.session_state.dev_mode = st.toggle("Developer Mode (Unlimited)", value=st.session_state.dev_mode)
            st.markdown(f"<small style='color:{sub_text};'>📍 {user_loc}</small>", unsafe_allow_html=True)

    # REAL GOOGLE ACCOUNT SWITCHER & LOGIN POPOVER
    if st.session_state.show_account_switcher:
        with st.container(border=True):
            if curr_email:
                st.markdown(f"**{curr_u['name']}**")
                st.caption(f"{curr_email} · `{plan_badge}` · `{cr_left} Cr`")
                if st.button("Sign out", use_container_width=True):
                    st.session_state.current_user = None
                    st.session_state.show_account_switcher = False
                    st.rerun()
            else:
                st.markdown("**Sign in to KINETUX Ai**")
                if st.session_state.google_client_id and st.session_state.google_client_secret:
                    redir = urllib.parse.quote(st.session_state.app_base_url.rstrip("/"), safe="")
                    g_oauth_url = (
                        f"https://accounts.google.com/o/oauth2/v2/auth?"
                        f"client_id={st.session_state.google_client_id}&"
                        f"redirect_uri={redir}&"
                        f"response_type=code&"
                        f"scope=openid%20email%20profile&"
                        f"prompt=select_account"
                    )
                    st.markdown(
                        f'<a href="{g_oauth_url}" target="_self" style="display:block; text-align:center; background:#FFFFFF; color:#1F1F1F; padding:9px; border-radius:20px; font-weight:600; text-decoration:none; margin-bottom:8px;">G &nbsp;Continue with Google</a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.caption("⚠️ Live Gmail list के लिए Owner Panel में `GOOGLE_CLIENT_ID` और `GOOGLE_CLIENT_SECRET` डालें।")
                    if st.button("G   Quick Demo Login", use_container_width=True):
                        em_g = "demo.creator@gmail.com"
                        if em_g not in users_db:
                            users_db[em_g] = {"name": "Rajveer Purohit", "provider": "Google", "plan": "free", "credits": 6, "videos_created": 0}
                            save_users(users_db)
                        st.session_state.current_user = em_g
                        st.session_state.show_account_switcher = False
                        st.rerun()

                if st.button("   Continue with Apple / iCloud", use_container_width=True):
                    em_a = "creator.apple@icloud.com"
                    if em_a not in users_db:
                        users_db[em_a] = {"name": "Apple Creator", "provider": "Apple iCloud", "plan": "free", "credits": 6, "videos_created": 0}
                        save_users(users_db)
                    st.session_state.current_user = em_a
                    st.session_state.show_account_switcher = False
                    st.rerun()

    col_u1, col_u2 = st.columns([3.8, 1])
    with col_u1:
        if not curr_email:
            if st.button("SB_SIGNIN", key="sb_signin_btn", help="Sign in with Google"):
                st.session_state.show_account_switcher = not st.session_state.show_account_switcher
                st.rerun()
        else:
            display_name = curr_u["name"]
            pic_u = curr_u.get("picture", "")
            avatar_letter = display_name[0].upper() if display_name else "G"
            avatar_html = (
                f'<img src="{pic_u}" style="width:28px; height:28px; border-radius:50%; object-fit:cover; flex-shrink:0;">'
                if pic_u else
                f'<div style="width:28px; height:28px; border-radius:50%; background:#00897B; color:#FFFFFF; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; flex-shrink:0;">{avatar_letter}</div>'
            )
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:10px; padding:2px 6px;">
                {avatar_html}
                <div style="overflow:hidden;">
                    <div style="font-size:13.5px; color:{text_color}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{display_name}</div>
                    <div style="font-size:10.5px; color:#A8C7FA;">{plan_badge} · {cr_left} Credits</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    with col_u2:
        if st.button("SB_GEAR", key="sb_bottom_gear", help="Owner Panel, Settings & Plans"):
            st.session_state.show_settings_pocket = not st.session_state.show_settings_pocket
            st.rerun()

# ==========================================
# 6. ALL-LANGUAGE DETECTOR, WHITE LOGO WATERMARK, ADS & VIDEO ENGINES
# ==========================================
def detect_language_and_voice(prompt):
    p = prompt.strip()
    if re.search(r'[\u0A80-\u0AFF]', p):
        return "Gujarati", "gu-IN-DhwaniNeural", "gu"
    if re.search(r'[\u0980-\u09FF]', p):
        return "Bengali", "bn-IN-TanishaaNeural", "bn"
    if re.search(r'[\u0B80-\u0BFF]', p):
        return "Tamil", "ta-IN-PallaviNeural", "ta"
    if re.search(r'[\u0C00-\u0C7F]', p):
        return "Telugu", "te-IN-ShrutiNeural", "te"
    if re.search(r'[\u0900-\u097F]', p):
        if any(w in p for w in ["आहे", "आणि", "मराठी", "गोष्ट", "कथा"]):
            return "Marathi", "mr-IN-AarohiNeural", "mr"
        return "Hindi", "hi-IN-SwaraNeural", "hi"

    low = " " + re.sub(r'[^a-zA-Z0-9\s]', ' ', p.lower()) + " "
    hinglish_words = [
        " ek ", " ki ", " ka ", " ke ", " aur ", " hai ", " hain ", " tha ", " thi ",
        " kahani ", " banao ", " video ", " sher ", " billi ", " chuha ", " hathi ",
        " bandar ", " jungle ", " raja ", " rani ", " ladka ", " ladki ", " baccho ",
        " hindi ", " mein ", " me ", " se ", " ko ", " par ", " nahi ", " kya ", " kaise ",
        " chhota ", " bada ", " dost ", " dosti ", " jaadu ", " jadui ", " pari ", " ad ", " ads ", " vigyapan ", " dukan "
    ]
    if sum(1 for w in hinglish_words if w in low) >= 2:
        return "Hindi (Devanagari script)", "hi-IN-SwaraNeural", "hi"

    if any(w in low for w in [" gujarati ", " varta ", " chhe ", " tame "]):
        return "Gujarati", "gu-IN-DhwaniNeural", "gu"
    if any(w in low for w in [" marathi ", " goshta ", " aahe "]):
        return "Marathi", "mr-IN-AarohiNeural", "mr"

    voice_en = "en-GB-SoniaNeural" if is_uk_user else "en-US-AnaNeural"
    return "English", voice_en, "en"

def apply_white_logo_watermark(video_clip, base_dir, custom_brand_img=None):
    clips_to_compose = [video_clip]
    if custom_brand_img is not None:
        try:
            bim = Image.open(custom_brand_img).convert("RGBA")
            asp = bim.width / max(1, bim.height)
            bh = 72
            bw = max(72, int(bh * asp))
            bim = bim.resize((bw, bh), Image.Resampling.LANCZOS)
            b_clip = ImageClip(np.array(bim)).set_duration(video_clip.duration).set_position((26, 24))
            clips_to_compose.append(b_clip)
        except Exception:
            pass

    logo_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(logo_path):
        try:
            im = Image.open(logo_path).convert("RGBA")
            aspect = im.width / max(1, im.height)
            new_h = 42
            new_w = max(42, int(new_h * aspect))
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)

            r, g, b, a = im.split()
            white_layer = Image.new("L", im.size, 255)
            alpha_scaled = a.point(lambda p: int(p * 0.85))
            white_logo = Image.merge("RGBA", (white_layer, white_layer, white_layer, alpha_scaled))

            wm_arr = np.array(white_logo)
            wm_clip = (
                ImageClip(wm_arr)
                .set_duration(video_clip.duration)
                .set_position((1280 - new_w - 22, 720 - new_h - 18))
            )
            clips_to_compose.append(wm_clip)
        except Exception:
            pass

    if len(clips_to_compose) == 1:
        return video_clip
    return CompositeVideoClip(clips_to_compose, size=(1280, 720))

def search_live_web(query):
    if not HAS_DDGS:
        return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if results:
            return "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
    except Exception:
        pass
    return ""

def stream_kinetux_brain(prompt, uploaded_file=None, system_hint="", stream_placeholder=None):
    api_key = st.session_state.gemini_api_key.strip()
    web_triggers = ["news", "today", "latest", "weather", "score", "price", "current", "aaj", "taza", "khabar", "live", "2026", "mausam"]
    live_web = search_live_web(prompt) if (any(w in prompt.lower() for w in web_triggers) or st.session_state.active_tool_mode == "Deep Research") else ""
    web_ctx = f"\n\n[Live Web Search Results]:\n{live_web}\n" if live_web else ""

    enriched_prompt = f"{prompt}{web_ctx}".strip()
    sys_msg = system_hint or "You are KINETUX Ai, a multilingual Cartoon & AI Studio assistant. Reply in the exact language/script requested by the user."

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            contents = []
            for m in chat_messages[:-1][-6:]:
                role = "user" if m["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

            user_parts = [types.Part.from_text(text=enriched_prompt)]
            if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                user_parts.append(types.Part.from_bytes(data=uploaded_file.getvalue(), mime_type=uploaded_file.type))
            contents.append(types.Content(role="user", parts=user_parts))

            full_answer = ""
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=sys_msg, temperature=0.7)
            )
            for chunk in stream:
                if chunk.text:
                    full_answer += chunk.text
                    if stream_placeholder is not None:
                        stream_placeholder.markdown(f"<div class='ai-msg'>✦ &nbsp;{full_answer}▌</div>", unsafe_allow_html=True)
            if full_answer.strip():
                if stream_placeholder is not None:
                    stream_placeholder.markdown(f"<div class='ai-msg'>✦ &nbsp;{full_answer}</div>", unsafe_allow_html=True)
                return full_answer
        except Exception as e:
            st.toast(f"Backup AI active ({e})")

    try:
        payload = {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": enriched_prompt[:6000]}
            ],
            "model": "openai"
        }
        res = requests.post("https://text.pollinations.ai/", json=payload, timeout=30)
        if res.status_code == 200 and res.text.strip():
            ans = res.text.strip()
            if stream_placeholder is not None:
                typed = ""
                for word in ans.split(" "):
                    typed += word + " "
                    stream_placeholder.markdown(f"<div class='ai-msg'>✦ &nbsp;{typed}▌</div>", unsafe_allow_html=True)
                    time.sleep(0.01)
                stream_placeholder.markdown(f"<div class='ai-msg'>✦ &nbsp;{ans}</div>", unsafe_allow_html=True)
            return ans
    except Exception:
        pass

    return "⚠️ कृपया नीचे **Owner Panel & API Keys** में अपनी `GEMINI_API_KEY` सेव करें।"

def ask_kinetux_brain(prompt, uploaded_file=None, system_hint=""):
    return stream_kinetux_brain(prompt, uploaded_file, system_hint, stream_placeholder=None)

def generate_free_hd_image(prompt, save_dir, use_imagen3=False):
    api_key = st.session_state.gemini_api_key.strip()
    if use_imagen3 and api_key:
        try:
            client = genai.Client(api_key=api_key)
            res = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/png", aspect_ratio="16:9")
            )
            for gen_img in res.generated_images:
                img_bytes = gen_img.image.image_bytes
                out_file = os.path.join(save_dir, f"Kinetux_Art_{datetime.now().strftime('%H%M%S')}.png")
                with open(out_file, "wb") as f:
                    f.write(img_bytes)
                return out_file, "Kinetux Imagen 3"
        except Exception:
            pass
    seed = int(time.time()) % 9999
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote('Ultra HD 8k masterpiece, ' + prompt)}?width=1280&height=720&model=flux&nologo=true&seed={seed}"
    return url, "Kinetux Vision (Free)"

async def _edge_tts_save(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="+2Hz")
    await communicate.save(out_path)

def generate_multilingual_voice(text, voice_name, gtts_lang, out_path):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_edge_tts_save(text, voice_name, out_path))
        loop.close()
        if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
            return
    except Exception:
        pass
    if HAS_GTTS:
        tts = gTTS(text=text, lang=gtts_lang)
        tts.save(out_path)

def fetch_clean_hd_image(prompt, seed_val, save_path, temp_dir, style_prefix="3D Pixar Disney animation movie frame, expressive talking moving characters, vibrant lighting"):
    models = ["flux", "turbo"]
    for attempt in range(3):
        model = models[attempt % len(models)]
        short_prompt = urllib.parse.quote(f"{style_prefix}, {prompt[:140]}")
        img_url = f"https://image.pollinations.ai/prompt/{short_prompt}?width=1280&height=780&model={model}&nologo=true&seed={seed_val + attempt * 19}"
        try:
            resp = requests.get(img_url, timeout=40)
            if resp.status_code == 200 and len(resp.content) > 12000:
                raw_path = os.path.join(temp_dir, f"raw_{seed_val}_{attempt}.png")
                with open(raw_path, "wb") as f:
                    f.write(resp.content)
                im = Image.open(raw_path).convert("RGB")
                w, h = im.size
                im_cropped = im.crop((0, 0, w, max(100, h - 60)))
                im_hd = im_cropped.resize((1280, 720), Image.Resampling.LANCZOS)
                im_hd = im_hd.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
                im_hd.save(save_path, "PNG", quality=95)
                return True
        except Exception:
            pass
        time.sleep(1.2)
    return False

def animate_character_real_motion(img_path, motion_prompt, temp_dir, scene_idx, allow_paid_api=False):
    if not allow_paid_api:
        return None
    fal_key = st.session_state.fal_api_key.strip()
    if fal_key:
        try:
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            res = requests.post(
                "https://fal.run/fal-ai/minimax/video-01/image-to-video",
                headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                json={
                    "prompt": f"3D Pixar cartoon characters walking, talking with lip movement, gesturing hands, lively full body animation, {motion_prompt}",
                    "image_url": f"data:image/png;base64,{b64}"
                },
                timeout=110
            ).json()
            vid_url = res.get("video", {}).get("url")
            if vid_url:
                v_out = os.path.join(temp_dir, f"real_motion_{scene_idx}.mp4")
                with open(v_out, "wb") as vf:
                    vf.write(requests.get(vid_url, timeout=60).content)
                return v_out
        except Exception:
            pass
    return None

def generate_heygen_talking_video(script_text, base_dir):
    hg_key = st.session_state.heygen_api_key.strip()
    if not hg_key:
        return None
    try:
        headers = {"X-Api-Key": hg_key, "Content-Type": "application/json"}
        payload = {
            "video_inputs": [
                {
                    "character": {"type": "avatar", "avatar_id": "Daisy-inskirt-20220818", "avatar_style": "normal"},
                    "voice": {"type": "text", "input_text": script_text[:400], "voice_id": "1bd001e7e50f421d891986aad5158bc8"}
                }
            ],
            "dimension": {"width": 1280, "height": 720}
        }
        r = requests.post("https://api.heygen.com/v2/video/generate", headers=headers, json=payload, timeout=30).json()
        vid_id = r.get("data", {}).get("video_id")
        if not vid_id:
            return None
        for _ in range(25):
            time.sleep(4)
            st_res = requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid_id}", headers={"X-Api-Key": hg_key}, timeout=20).json()
            status = st_res.get("data", {}).get("status")
            if status == "completed":
                v_url = st_res.get("data", {}).get("video_url")
                if v_url:
                    out_p = os.path.join(base_dir, f"Kinetux_HeyGen_{datetime.now().strftime('%H%M%S')}.mp4")
                    with open(out_p, "wb") as f:
                        f.write(requests.get(v_url, timeout=60).content)
                    return out_p
            elif status == "failed":
                break
    except Exception:
        pass
    return None

def create_multi_action_scene_clip(img_paths, audio_clip, scene_idx):
    total_dur = audio_clip.duration
    sub_dur = total_dur / len(img_paths)
    sub_clips = []

    for k, p in enumerate(img_paths):
        pil_im = Image.open(p).convert("RGB").resize((1520, 855), Image.Resampling.LANCZOS)
        arr = np.array(pil_im)
        base = ImageClip(arr).set_duration(sub_dur)

        def make_pos(k_idx):
            def pos_fn(t):
                prog = t / max(0.1, sub_dur)
                if (scene_idx + k_idx) % 2 == 0:
                    x = int(-220 * prog)
                else:
                    x = int(-220 * (1.0 - prog))
                y = int(-65 + 14 * np.sin(2 * np.pi * 2.6 * t))
                return (x, y)
            return pos_fn

        zoomed = base.resize(lambda t: 1.0 + 0.08 * (t / max(0.1, sub_dur)))
        moved = zoomed.set_position(make_pos(k))
        comp_sub = CompositeVideoClip([moved], size=(1280, 720)).set_duration(sub_dur)
        if k > 0:
            comp_sub = comp_sub.crossfadein(0.35)
        sub_clips.append(comp_sub)

    scene_vid = concatenate_videoclips(sub_clips, method="compose", padding=-0.35 if len(sub_clips) > 1 else 0)
    return scene_vid.set_duration(total_dur).set_audio(audio_clip)

def build_cartoon_movie(story, base_dir, is_long_movie=False, use_paid_motion_api=False, is_custom_ad=False, custom_brand_img=None):
    lang_label, voice_name, gtts_lang = detect_language_and_voice(story)
    num_scenes = 3 if (is_long_movie or is_custom_ad) else 2

    if is_custom_ad:
        style_pref = "Ultra realistic cinematic commercial advertisement shot, glossy product lighting, happy customers, modern Indian/global brand showcase, 8k"
        scenes_prompt = f"""You are a High-Converting Commercial TV & Social Media Advertisement Director.
Ad Brief / Product / Offer: "{story}"
Target voiceover language: {lang_label} (Write "narration" strictly in {lang_label} using native script like Devanagari for Hindi/Marathi or Gujarati script for Gujarati!).
Return ONLY a valid JSON array of {num_scenes} objects with keys:
- "narration": 1 punchy, energetic commercial voiceover line in {lang_label} (around 12-16 words, Hook -> Features -> Call to Action)
- "action_1": English commercial visual prompt showing the product/service in vibrant studio lighting
- "action_2": English commercial visual prompt showing satisfied customers using the product and special offer highlight"""
    else:
        style_pref = "3D Pixar Disney animation movie frame, expressive talking moving characters, vibrant lighting"
        scenes_prompt = f"""You are a 3D Pixar Cartoon Movie Director.
User request: "{story}"
Target narration language: {lang_label} (IMPORTANT: Write "narration" strictly in {lang_label}, using its native script like Devanagari for Hindi/Marathi or Gujarati script for Gujarati!).
Return ONLY a valid JSON array of {num_scenes} objects with keys:
- "narration": 1 short expressive character dialogue/narration sentence in {lang_label} (around 12-16 words)
- "action_1": English 3D Pixar scene description of characters talking and starting action
- "action_2": English 3D Pixar scene description of characters moving/running/celebrating"""

    raw_json = ask_kinetux_brain(scenes_prompt)
    scenes = None
    try:
        match = re.search(r'\[.*\]', raw_json, re.DOTALL)
        if match:
            scenes = json.loads(match.group(0))[:num_scenes]
    except Exception:
        pass

    if not scenes or len(scenes) < num_scenes:
        is_hi = "Hindi" in lang_label
        if is_custom_ad:
            scenes = [
                {
                    "narration": f"पेश है {story} — बेहतरीन क्वालिटी और शानदार ऑफर के साथ आज ही अपना बनाएं!" if is_hi else f"Introducing {story} — unmatched quality and exclusive offers just for you!",
                    "action_1": f"Cinematic commercial product showcase in bright studio lighting, {story}",
                    "action_2": f"Happy customers smiling and experiencing {story}, modern commercial look"
                },
                {
                    "narration": "सीमित समय का महा-बचत ऑफर! अभी ऑर्डर करें और अपने परिवार को दें सबसे बेस्ट!" if is_hi else "Limited time special deal! Order today and experience the difference!",
                    "action_1": f"Close up hero shot of {story} with golden sparkles and premium finish",
                    "action_2": f"Celebratory commercial finale banner showcase for {story}"
                }
            ][:num_scenes]
        else:
            scenes = [
                {
                    "narration": f"एक दिन जंगल में {story}, और सभी दोस्त मिलकर मज़ेदार सफ़र पर निकल पड़े!" if is_hi else f"One sunny day, {story}, and the characters began their exciting adventure!",
                    "action_1": f"3D Pixar cartoon characters talking happily in colorful setting, {story}",
                    "action_2": f"3D Pixar cartoon characters walking and running together energetically, {story}"
                },
                {
                    "narration": "आख़िरकार सबने मिलकर जीत हासिल की और नाचते-गाते खूब जश्न मनाया!" if is_hi else "In the end they succeeded together and danced happily under the sky!",
                    "action_1": f"3D Pixar cartoon characters cheering and smiling at each other, {story}",
                    "action_2": f"3D Pixar cartoon characters dancing and celebrating joyfully, {story}"
                }
            ][:num_scenes]

    clips = []
    audio_clips = []
    temp_dir = os.path.join(base_dir, "temp_kinetux")
    os.makedirs(temp_dir, exist_ok=True)
    last_good_img = None
    used_real_ai_motion = False

    for i, sc in enumerate(scenes):
        a_path = os.path.join(temp_dir, f"v_{i}.mp3")
        generate_multilingual_voice(sc["narration"], voice_name, gtts_lang, a_path)
        a_clip = AudioFileClip(a_path)
        audio_clips.append(a_clip)

        p1 = os.path.join(temp_dir, f"s_{i}_a.png")
        p2 = os.path.join(temp_dir, f"s_{i}_b.png")
        ok1 = fetch_clean_hd_image(sc.get("action_1", story), (i + 1) * 101, p1, temp_dir, style_prefix=style_pref)
        if ok1:
            last_good_img = p1
        elif last_good_img:
            shutil.copy(last_good_img, p1)
        else:
            Image.new("RGB", (1280, 720), color=(30, 58, 110)).save(p1)

        real_vid_path = animate_character_real_motion(p1, sc.get("action_2", story), temp_dir, i, allow_paid_api=use_paid_motion_api)
        if real_vid_path and os.path.exists(real_vid_path):
            used_real_ai_motion = True
            v_clip = VideoFileClip(real_vid_path).resize((1280, 720))
            if v_clip.duration < a_clip.duration:
                v_clip = v_clip.loop(duration=a_clip.duration)
            else:
                v_clip = v_clip.subclip(0, a_clip.duration)
            clips.append(v_clip.set_audio(a_clip))
        else:
            ok2 = fetch_clean_hd_image(sc.get("action_2", story), (i + 1) * 307, p2, temp_dir, style_prefix=style_pref)
            frame_list = [p1, p2] if ok2 else [p1]
            clips.append(create_multi_action_scene_clip(frame_list, a_clip, i))

    prefix_tag = "Kinetux_Ad" if is_custom_ad else "Kinetux_Cartoon"
    out_name = f"{prefix_tag}_{datetime.now().strftime('%H%M%S')}.mp4"
    out_path = os.path.join(base_dir, out_name)
    raw_concat = concatenate_videoclips(clips, method="compose")
    final_vid = apply_white_logo_watermark(raw_concat, base_dir, custom_brand_img=custom_brand_img)
    final_vid.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    final_vid.close()
    raw_concat.close()
    for c in clips:
        c.close()
    for ac in audio_clips:
        ac.close()
    return out_path, out_name, lang_label, used_real_ai_motion

def render_ads_banner():
    _, u = get_active_user()
    if u.get("plan") in ["pro_99", "pro_499", "ultra"]:
        return
    pub_id = st.session_state.adsense_pub_id
    if "XXXX" not in pub_id:
        components.html(f"""
        <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={pub_id}" crossorigin="anonymous"></script>
        <ins class="adsbygoogle" style="display:block" data-ad-client="{pub_id}" data-ad-slot="1234567890" data-ad-format="auto" data-full-width-responsive="true"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        """, height=90)

# ==========================================
# 7. MAIN WORKSPACE
# ==========================================
tab = st.session_state.active_tab

if tab == "New chat":
    _, center_col, _ = st.columns([1.1, 2.8, 1.1])
    with center_col:
        if not has_messages:
            st.markdown("<div style='height:135px;'></div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center; font-size:38px; font-weight:400; letter-spacing:-0.4px; margin-bottom:28px; color:#FFFFFF;'>Where should we start?</h1>", unsafe_allow_html=True)
        else:
            for idx, msg in enumerate(chat_messages):
                if msg["role"] == "user":
                    st.markdown(f"<div class='user-msg'>{msg['content']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='ai-msg'>✦ &nbsp;{msg['content']}</div>", unsafe_allow_html=True)
                    if msg.get("image_url"):
                        st.image(msg["image_url"], use_container_width=True)
                    if msg.get("video_path") and os.path.exists(msg["video_path"]):
                        st.video(msg["video_path"])

                    st.markdown("<div class='action-bar-row'>", unsafe_allow_html=True)
                    ab1, ab2, ab3, ab4, _ = st.columns([0.45, 0.45, 0.45, 0.45, 5.2])
                    with ab1:
                        like_icon = "👍🏻" if st.session_state.liked_msgs.get(idx) == "up" else "👍"
                        if st.button(like_icon, key=f"like_{idx}", help="Good response"):
                            st.session_state.liked_msgs[idx] = "up"
                            st.toast("👍 Feedback saved!")
                    with ab2:
                        dis_icon = "👎🏻" if st.session_state.liked_msgs.get(idx) == "down" else "👎"
                        if st.button(dis_icon, key=f"dis_{idx}", help="Bad response"):
                            st.session_state.liked_msgs[idx] = "down"
                            st.toast("👎 Feedback noted!")
                    with ab3:
                        if msg.get("video_path") and os.path.exists(msg["video_path"]):
                            with open(msg["video_path"], "rb") as vf:
                                st.download_button("📋", vf, file_name=os.path.basename(msg["video_path"]), mime="video/mp4", key=f"cp_{idx}", help="Save Video")
                        else:
                            if st.button("📋", key=f"cp_{idx}", help="Copy response"):
                                st.toast("📋 Response copied!")
                    with ab4:
                        if st.button("•••", key=f"dots_{idx}", help="More options"):
                            st.session_state.open_msg_menu = None if st.session_state.open_msg_menu == idx else idx
                    st.markdown("</div>", unsafe_allow_html=True)

                    if st.session_state.open_msg_menu == idx:
                        st.markdown("<div class='three-dot-menu'>", unsafe_allow_html=True)
                        if st.button("↳  Branch in new chat", key=f"br_{idx}"):
                            create_new_chat_session()
                            st.session_state.chats[st.session_state.active_chat_id]["messages"] = [msg]
                            st.session_state.open_msg_menu = None
                            st.rerun()
                        if st.button("🔊  Listen", key=f"ls_{idx}"):
                            tts_file = os.path.join(base_dir, f"listen_{idx}.mp3")
                            clean_txt = re.sub(r'[*#`✦✅]', '', msg["content"])[:500]
                            _, v_nm, g_lg = detect_language_and_voice(clean_txt)
                            generate_multilingual_voice(clean_txt, v_nm, g_lg, tts_file)
                            st.audio(tts_file)
                        st.download_button(
                            "📄  Export to Docs",
                            data=msg["content"],
                            file_name=f"Kinetux_Doc_{idx+1}.doc",
                            mime="application/msword",
                            key=f"doc_{idx}",
                            use_container_width=True
                        )
                        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&su={urllib.parse.quote('KINETUX Ai Draft')}&body={urllib.parse.quote(msg['content'][:1500])}"
                        st.markdown(f'<a href="{gmail_url}" target="_blank" style="display:block; padding:8px 12px; color:{text_color}; text-decoration:none; font-size:13.5px; border-radius:10px;">✉️ &nbsp;Draft in Gmail</a>', unsafe_allow_html=True)
                        if st.button("ℹ️  See response details", key=f"det_{idx}"):
                            st.session_state.open_msg_details = None if st.session_state.open_msg_details == idx else idx
                        st.markdown("</div>", unsafe_allow_html=True)

                    if st.session_state.open_msg_details == idx:
                        st.info(f"**Engine:** `{msg.get('model', st.session_state.model_choice)}` | **Generated:** `{msg.get('time', datetime.now().strftime('%I:%M %p'))}`")

        live_stream_slot = st.empty()

        st.markdown("<div id='kinetux-attached-badge' style='display:none; align-items:center; background:rgba(56,189,248,0.2); border:1px solid rgba(56,189,248,0.4); color:#E0F2FE; padding:4px 12px; border-radius:16px; font-size:12px; margin-bottom:8px;'></div>", unsafe_allow_html=True)

        c_plus, c_input, c_auto, c_mic = st.columns([0.55, 5.0, 1.85, 0.50])
        with c_plus:
            if st.button("BIG_PLUS", key="capsule_plus_btn", help="Tools & Direct Upload"):
                st.session_state.show_plus_drawer = not st.session_state.show_plus_drawer
                st.rerun()
        with c_input:
            st.text_input(
                "Ask Kinetux",
                key="kinetux_input_box",
                placeholder="Ask Kinetux",
                label_visibility="collapsed",
                on_change=handle_enter_submit
            )
        with c_auto:
            st.session_state.model_choice = st.selectbox(
                "Mode",
                ["Kinetux Auto", "Custom Ads Video", "Free Image Gen", "Cartoon 15s (Trial)", "Pro Cartoon Movie", "HeyGen Talking Avatar"],
                label_visibility="collapsed"
            )
        with c_mic:
            if st.button("VOICE_MIC", key="capsule_mic_btn", help="Send Message"):
                handle_enter_submit()

        if st.session_state.show_plus_drawer:
            if st.button("ACT_custom_ads"):
                st.session_state.model_choice = "Custom Ads Video"
                st.session_state.active_tool_mode = "Custom Ads Video"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_avatar"):
                st.session_state.model_choice = "HeyGen Talking Avatar"
                st.session_state.active_tool_mode = "HeyGen Talking Avatar"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_storybook"):
                st.session_state.active_tool_mode = "Storybook"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_create_image"):
                st.session_state.model_choice = "Free Image Gen"
                st.session_state.active_tool_mode = "Free Image Generator"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_create_video"):
                st.session_state.model_choice = "Cartoon 15s (Trial)"
                st.session_state.active_tool_mode = "Cartoon Video (15s Trial)"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_create_long_video"):
                st.session_state.model_choice = "Pro Cartoon Movie"
                st.session_state.active_tool_mode = "Pro Cartoon Movie (45s)"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_create_music"):
                st.session_state.active_tool_mode = "Lyria Cartoon Music"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_deep_research"):
                st.session_state.active_tool_mode = "Deep Research"
                st.session_state.show_plus_drawer = False
                st.rerun()
            if st.button("ACT_personal_intel"):
                st.session_state.personal_intel_on = not st.session_state.personal_intel_on
                st.rerun()

        if not has_messages:
            st.markdown("<div style='margin-top:24px; padding-left:14px;' class='simple-suggestions'>", unsafe_allow_html=True)
            if st.button("SUGG_1"):
                q_s1 = "Ek billi aur chuhe ki 3D cartoon kahani banao"
                active_chat["title"] = q_s1[:32]
                chat_messages.append({"role": "user", "content": q_s1})
                st.session_state.pending_query = q_s1
                st.rerun()
            if st.button("SUGG_2"):
                q_s2 = "Generate a free 3D Pixar superhero image"
                active_chat["title"] = q_s2[:32]
                chat_messages.append({"role": "user", "content": q_s2})
                st.session_state.pending_query = q_s2
                st.rerun()
            if st.button("SUGG_3"):
                q_s3 = "એક નાના હાથી અને પક્ષીની કાર્ટૂન વાર્તા બનાવો"
                active_chat["title"] = q_s3[:32]
                chat_messages.append({"role": "user", "content": q_s3})
                st.session_state.pending_query = q_s3
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.pending_query.strip():
            clean_query = st.session_state.pending_query.strip()
            st.session_state.pending_query = ""

            mode = st.session_state.model_choice
            tool_mode = st.session_state.active_tool_mode
            now_str = datetime.now().strftime("%I:%M %p")
            lower_q = clean_query.lower()

            image_keywords = ["generate image", "create image", "draw ", "poster", "tasveer", "photo banao", "image banao", "picture", "तस्वीर", "फोटो बनाओ"]
            ad_keywords = ["custom ad", "advertisement", "commercial", "promo video", "vigyapan", "विज्ञापन", "दुकान का वीडियो", "ad banao"]
            cartoon_keywords = ["cartoon", "animation", "kahani", "video", "varta", "goshta", "story video", "3d video", "कार्टून", "कहानी", "वीडियो", "વાર્તા"]

            is_ad_req = (
                mode == "Custom Ads Video"
                or tool_mode == "Custom Ads Video"
                or any(w in lower_q for w in ad_keywords)
            )
            is_image_req = (
                mode == "Free Image Gen"
                or tool_mode == "Free Image Generator"
                or (any(w in lower_q for w in image_keywords) and "video" not in lower_q)
            )
            is_cartoon_req = (
                mode in ["Cartoon 15s (Trial)", "Pro Cartoon Movie"]
                or tool_mode in ["Cartoon Video (15s Trial)", "Pro Cartoon Movie (45s)"]
                or any(w in lower_q for w in cartoon_keywords)
            )
            is_long_req = (mode == "Pro Cartoon Movie" or tool_mode == "Pro Cartoon Movie (45s)" or any(w in lower_q for w in ["long", "bada", "full movie", "45", "60"]))

            if mode == "HeyGen Talking Avatar" or tool_mode == "HeyGen Talking Avatar":
                allowed, msg_cr = consume_credits(cost=4, min_plan="pro_499")
                if not allowed:
                    chat_messages.append({"role": "ai", "content": msg_cr, "model": "Subscription Guard", "time": now_str})
                else:
                    with st.spinner("🗣️ Rendering HeyGen Talking Lip-Sync Video..."):
                        hg_vid = generate_heygen_talking_video(clean_query, base_dir)
                        if hg_vid and os.path.exists(hg_vid):
                            st.session_state.library.append({"title": clean_query, "path": hg_vid})
                            chat_messages.append({"role": "ai", "content": "✅ आपका **HeyGen Talking Avatar Video** तैयार है!", "video_path": hg_vid, "model": "HeyGen V2 Engine", "time": now_str})
                        else:
                            chat_messages.append({"role": "ai", "content": "⚠️ HeyGen API Key या क्रेडिट चेक करें।", "model": "HeyGen", "time": now_str})
            elif is_image_req:
                with st.spinner("✦ Creating HD Artwork (Free Studio)..."):
                    _, u_curr = get_active_user()
                    is_paid_u = u_curr.get("plan") in ["pro_99", "pro_499"]
                    img_res, eng_used = generate_free_hd_image(clean_query, base_dir, use_imagen3=is_paid_u)
                    chat_messages.append({
                        "role": "ai",
                        "content": f"यह रही आपकी **{eng_used}** इमेज (**{clean_query}**):",
                        "image_url": img_res,
                        "model": eng_used,
                        "time": now_str
                    })
            elif is_ad_req:
                allowed, msg_cr, use_paid_api = consume_cartoon_quota(is_long_movie=False)
                if not allowed:
                    chat_messages.append({"role": "ai", "content": msg_cr, "model": "Subscription Guard", "time": now_str})
                else:
                    with st.spinner("📢 Creating Commercial Custom Ad Video with AI Voiceover..."):
                        v_path, v_name, det_lang, real_mov = build_cartoon_movie(clean_query, base_dir, is_long_movie=False, use_paid_motion_api=use_paid_api, is_custom_ad=True)
                        st.session_state.library.append({"title": f"[AD] {clean_query}", "path": v_path})
                        chat_messages.append({
                            "role": "ai",
                            "content": f"✅ आपका **Custom Commercial Ad Video ({v_name})** तैयार है!\n- **Voiceover Language:** `{det_lang}`",
                            "video_path": v_path,
                            "model": f"Kinetux Ad Studio ({det_lang})",
                            "time": now_str
                        })
            elif is_cartoon_req:
                allowed, msg_cr, use_paid_api = consume_cartoon_quota(is_long_movie=is_long_req)
                if not allowed:
                    chat_messages.append({"role": "ai", "content": msg_cr, "model": "Subscription Guard", "time": now_str})
                else:
                    with st.spinner("🎬 Creating 3D Cartoon Video with White Watermark..."):
                        v_path, v_name, det_lang, real_mov = build_cartoon_movie(clean_query, base_dir, is_long_movie=is_long_req, use_paid_motion_api=use_paid_api)
                        st.session_state.library.append({"title": clean_query, "path": v_path})
                        motion_note = "✨ **Pro Real Character Motion (Fal.ai)**" if real_mov else "🎞 **Free Trial 3D Animation (₹0 API Cost)**"
                        chat_messages.append({
                            "role": "ai",
                            "content": f"✅ आपका कार्टून वीडियो (**{v_name}**) तैयार है!\n- **Detected Language:** `{det_lang}`\n- **Engine:** {motion_note}",
                            "video_path": v_path,
                            "model": f"Cartoon Studio ({det_lang})",
                            "time": now_str
                        })
            else:
                det_lang, _, _ = detect_language_and_voice(clean_query)
                sys_hint = f"You are KINETUX Ai, a multilingual Cartoon & AI Studio assistant. Reply in {det_lang} (matching the user's language/Hinglish)."
                reply = stream_kinetux_brain(clean_query, None, sys_hint, stream_placeholder=live_stream_slot)
                chat_messages.append({
                    "role": "ai",
                    "content": reply,
                    "model": f"{tool_mode or mode} ({det_lang})",
                    "time": now_str
                })

            st.rerun()

        render_ads_banner()

    if has_messages:
        components.html("""
        <script>
            const sc = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
            if (sc) { sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' }); }
        </script>
        """, height=0)

# ==========================================
# 8. CUSTOM ADS VIDEO MAKER STUDIO
# ==========================================
elif tab == "Custom_Ads":
    st.title("📢 KINETUX Custom Ads Video Maker")
    st.caption("अपनी दुकान, ब्रांड, प्रोडक्ट या सर्विस का प्रोफेशनल वीडियो विज्ञापन (Commercial Ad) बनाएं — हिंदी, गुजराती, मराठी या अंग्रेज़ी में!")
    col_ad1, col_ad2 = st.columns([2, 1])
    with col_ad1:
        brand_name = st.text_input("Brand / Shop Name:", placeholder="e.g., Kastuza Group / Cafe Aravalli 1722")
        ad_offer = st.text_area("Ad Script / Offer Details:", placeholder="e.g., सबसे मजबूत फ्लाई ऐश ईंटें और इंटरलॉकिंग पेवर ब्लॉक अब सीधे फैक्ट्री रेट पर उपलब्ध! आज ही संपर्क करें।")
    with col_ad2:
        brand_logo_file = st.file_uploader("Upload Brand Logo (Optional)", type=["png", "jpg", "jpeg"])
        ad_style = st.selectbox("Ad Style:", ["Modern Commercial Showcase", "3D Animated Mascot Ad"])

    if st.button("🚀 Generate Custom Ad Video", type="primary") and (brand_name.strip() or ad_offer.strip()):
        full_ad_brief = f"{brand_name}: {ad_offer}".strip()
        ok, msg_c, use_paid = consume_cartoon_quota(is_long_movie=False)
        if not ok:
            st.error(msg_c)
        else:
            with st.spinner("📢 Rendering Custom Commercial Ad Video with Logo & Voiceover..."):
                vp, vn, d_lang, _ = build_cartoon_movie(
                    full_ad_brief,
                    base_dir,
                    is_long_movie=False,
                    use_paid_motion_api=use_paid,
                    is_custom_ad=(ad_style == "Modern Commercial Showcase"),
                    custom_brand_img=brand_logo_file
                )
                st.session_state.library.append({"title": f"[AD] {brand_name}", "path": vp})
                st.success(f"✅ Ad Ready in {d_lang}!")
                st.video(vp)
                with open(vp, "rb") as f:
                    st.download_button("⬇️ Download Ad MP4", f, file_name=vn, mime="video/mp4")

# ==========================================
# 9. DEDICATED STUDIOS, LEGAL PAGES & OWNER PANEL
# ==========================================
elif tab == "Cartoon Studio":
    st.title("🎬 KINETUX 3D Cartoon Video Studio (India & UK)")
    c_story = st.text_input("Cartoon Story Prompt:", placeholder="Ek sher aur chuhe ki dosti ki kahani...")
    dur_choice = st.radio("Video Length:", ["Short Trial (10–15 Seconds · Free Quota)", f"Full Cartoon Movie (35–45 Seconds · {starter_price_label} / {pro_price_label})"], horizontal=True)
    if st.button("🚀 Generate Cartoon Video", type="primary") and c_story.strip():
        is_long = "Full" in dur_choice
        ok, msg_c, use_paid = consume_cartoon_quota(is_long_movie=is_long)
        if not ok:
            st.error(msg_c)
        else:
            with st.spinner("Rendering Cartoon Characters, White Logo Watermark & Voiceover..."):
                vp, vn, d_lang, r_mov = build_cartoon_movie(c_story, base_dir, is_long_movie=is_long, use_paid_motion_api=use_paid)
                st.session_state.library.append({"title": c_story, "path": vp})
                st.success(f"Language: {d_lang}")
                st.video(vp)
                with open(vp, "rb") as f:
                    st.download_button("⬇️ Download MP4", f, file_name=vn, mime="video/mp4")

elif tab == "Avatar_Storybook":
    st.title("🎭 HeyGen Talking Avatar & Storybook Studio")
    col_av1, col_av2 = st.columns(2)
    with col_av1:
        st.subheader("HeyGen Talking Avatar Video")
        av_desc = st.text_area("Character Speech Script:", value="Namaste! Swagat hai aapka KINETUX Ai Cartoon Studio mein.")
        if st.button("Generate Talking Avatar Video (4 Credits)") and av_desc:
            ok, msg_c = consume_credits(4, "pro_499")
            if not ok:
                st.error(msg_c)
            else:
                with st.spinner("Generating HeyGen Lip-Sync Video..."):
                    hv = generate_heygen_talking_video(av_desc, base_dir)
                    if hv:
                        st.video(hv)
                    else:
                        st.warning("HeyGen API Key या क्रेडिट चेक करें।")
    with col_av2:
        st.subheader("AI Storybook Creator")
        sb_topic = st.text_input("Storybook Topic:", value="Ek chhote se gaon ke ladke ka AI robot dost")
        if st.button("Write Storybook") and sb_topic:
            st.markdown(ask_kinetux_brain(sb_topic, system_hint="Write a 4-chapter illustrated children's storybook in the user's language."))

elif tab == "Music_Studio":
    st.title("🎵 Lyria Cartoon Music & Rhyme Studio")
    m_prompt = st.text_input("Describe kids rhyme or cartoon background music:", placeholder="Chanda mama door ke cartoon song lyrics...")
    if st.button("Compose Song", type="primary") and m_prompt:
        st.markdown(ask_kinetux_brain(m_prompt, system_hint="Write a catchy kids cartoon song/rhyme in the user's language."))

elif tab == "Images":
    st.title("🖼 Free HD Image & Character Art Studio")
    img_p = st.text_input("Describe any picture or cartoon character:", value="A cute 3D Pixar cat chasing a mouse in a sunny garden, 8k")
    if st.button("Generate Free HD Image", type="primary") and img_p:
        res_img, eng = generate_free_hd_image(img_p, base_dir, use_imagen3=False)
        st.image(res_img, caption=eng)

elif tab == "Library":
    st.title("⊞ KINETUX Cartoon & Ads Library")
    if not st.session_state.library:
        st.info("अभी तक कोई वीडियो नहीं बना है।")
    for item in reversed(st.session_state.library):
        st.subheader(item["title"])
        if os.path.exists(item["path"]):
            st.video(item["path"])

elif tab == "Scheduled":
    st.title("◷ Scheduled Uploads")
    st.text_input("Daily Topic", placeholder="Panchatantra Moral Story / Daily Shop Offer")
    st.time_input("Auto-Generate Time")
    st.button("Save Schedule")

elif tab == "Customise":
    st.title("⚙ Customise Video Format")
    st.selectbox("Video Format", ["16:9 YouTube Landscape", "9:16 YouTube Shorts / Reels"])

elif tab == "Legal_Privacy":
    st.title("🔒 Privacy Policy — KINETUX Ai")
    st.write("KINETUX Ai collects Google/Apple sign-in profile information and user prompts/media solely to generate requested AI videos, advertisements, and images. We never sell or rent user data to third parties. Payment transactions are securely processed via Razorpay.")

elif tab == "Legal_Terms":
    st.title("📜 Terms & Conditions — KINETUX Ai")
    st.write("By accessing KINETUX Ai, you agree to use our AI Cartoon, Custom Ads, and Image generation tools strictly for lawful purposes. Users retain commercial rights to custom advertisements and videos generated under active ₹99 Starter or ₹499 Studio Pro subscriptions.")

elif tab == "Legal_Refund":
    st.title("↩️ Refund & Cancellation Policy — KINETUX Ai")
    st.write("Subscriptions (₹99/month and ₹499/month) can be cancelled anytime. Due to instant GPU/AI rendering costs, credits already consumed are non-refundable. However, if a payment is deducted and credits are not added due to a technical error, a 100% refund is processed to your original payment method within 5–7 business days.")

elif tab == "Legal_Contact":
    st.title("📞 Contact Us — KINETUX Ai")
    st.markdown("""
    - **Platform:** KINETUX Ai
    - **Founder:** Rajveer Purohit
    - **Support Email:** support@kinetux.ai
    - **Operating Region:** India & United Kingdom
    """)

elif tab == "Settings_Sub":
    st.title("👑 KINETUX Ai — Owner Panel, Plans & API Keys")
    em_now, u_now = get_active_user()

    with st.container(border=True):
        st.subheader(f"1. 💳 Subscription Plans (Detected Region: {user_loc})")
        p1, p2, p3 = st.columns(3)
        with p1:
            free_curr = "£0" if is_uk_user else "₹0"
            st.markdown(f"### Free Trial\n**{free_curr}**\n- Unlimited Free Image Gen\n- 3 Short Cartoon / Ad Videos\n- All Languages & Hinglish")
        with p2:
            st.markdown(f"### Cartoon Starter\n**{starter_price_label}**\n- **30 Credits / month**\n- **Fal.ai Real Character Motion**\n- Custom Ads Video Maker")
            if st.button(starter_btn_label, use_container_width=True):
                amt_inr = 750 if is_uk_user else 99
                record_subscription_split(amt_inr, "Starter Plan", em_now or "Guest")
                if em_now and em_now in users_db:
                    users_db[em_now]["plan"] = "pro_99"
                    users_db[em_now]["credits"] = users_db[em_now].get("credits", 0) + 30
                    save_users(users_db)
                else:
                    st.session_state.guest_credits += 30
                st.success(f"✅ Starter Plan ({starter_price_label}) Activated!")
                st.rerun()
        with p3:
            st.markdown(f"### Studio Pro\n**{pro_price_label}**\n- **120 Credits / month**\n- **Fal.ai + HeyGen + Hedra Full Access**\n- 45s Pro Cartoon & Commercial Ads")
            if st.button(pro_btn_label, type="primary", use_container_width=True):
                amt_inr = 2150 if is_uk_user else 499
                record_subscription_split(amt_inr, "Studio Pro Plan", em_now or "Guest")
                if em_now and em_now in users_db:
                    users_db[em_now]["plan"] = "pro_499"
                    users_db[em_now]["credits"] = users_db[em_now].get("credits", 0) + 120
                    save_users(users_db)
                else:
                    st.session_state.guest_credits += 120
                st.success(f"✅ Studio Pro ({pro_price_label}) Activated!")
                st.rerun()

    with st.container(border=True):
        st.subheader("2. 👑 Owner Revenue & User Analytics Panel")
        ledger = load_ledger()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Registered Users", f"{len(users_db)}")
        m2.metric("Total Sales", f"₹{ledger.get('total_collected_inr', 0)}")
        m3.metric("Your Net Profit (80%)", f"₹{ledger.get('owner_profit_inr', 0)}")
        m4.metric("API Recharge Fund (20%)", f"₹{ledger.get('api_reserve_inr', 0)}")
        if ledger.get("transactions"):
            st.write("**Recent Transactions:**")
            st.dataframe(ledger["transactions"][-10:], use_container_width=True)

    with st.container(border=True):
        st.subheader("3. 🔑 All AI Engines, Google OAuth & Razorpay Live Keys")
        base_u = st.text_input("APP_BASE_URL (Local: http://localhost:8509 | Live: https://yourdomain.com)", value=st.session_state.app_base_url)
        gc_id = st.text_input("GOOGLE_CLIENT_ID (Google Cloud Console OAuth)", value=st.session_state.google_client_id)
        gc_sec = st.text_input("GOOGLE_CLIENT_SECRET (Google Cloud Console OAuth)", value=st.session_state.google_client_secret, type="password")
        g_key = st.text_input("GEMINI_API_KEY (Google AI Studio — Story Script & Imagen 3)", value=st.session_state.gemini_api_key, type="password")
        f_key = st.text_input("FAL_KEY (Fal.ai — 3D Character Walking & Moving Video)", value=st.session_state.fal_api_key, type="password")
        hg_key = st.text_input("HEYGEN_API_KEY (HeyGen — Talking AI Avatar & Lip-Sync)", value=st.session_state.heygen_api_key, type="password")
        hd_key = st.text_input("HEDRA_API_KEY (Hedra — Singing & Expression Lip-Sync)", value=st.session_state.hedra_api_key, type="password")
        rp_key = st.text_input("RAZORPAY_KEY_ID (Live Key ID: rzp_live_...)", value=st.session_state.razorpay_key_id)
        rp_sec = st.text_input("RAZORPAY_KEY_SECRET (Live Key Secret)", value=st.session_state.razorpay_key_secret, type="password")

        if st.button("Save All Keys Permanently (.env)", type="primary"):
            st.session_state.app_base_url = base_u
            st.session_state.google_client_id = gc_id
            st.session_state.google_client_secret = gc_sec
            st.session_state.gemini_api_key = g_key
            st.session_state.fal_api_key = f_key
            st.session_state.heygen_api_key = hg_key
            st.session_state.hedra_api_key = hd_key
            st.session_state.razorpay_key_id = rp_key
            st.session_state.razorpay_key_secret = rp_sec
            env_path = os.path.join(base_dir, ".env")
            with open(env_path, "w", encoding="utf-8") as ef:
                ef.write(
                    f"APP_BASE_URL={base_u.strip()}\n"
                    f"GOOGLE_CLIENT_ID={gc_id.strip()}\n"
                    f"GOOGLE_CLIENT_SECRET={gc_sec.strip()}\n"
                    f"GEMINI_API_KEY={g_key.strip()}\n"
                    f"FAL_KEY={f_key.strip()}\n"
                    f"HEYGEN_API_KEY={hg_key.strip()}\n"
                    f"HEDRA_API_KEY={hd_key.strip()}\n"
                    f"RAZORPAY_KEY_ID={rp_key.strip()}\n"
                    f"RAZORPAY_KEY_SECRET={rp_sec.strip()}\n"
                )
            st.success("✅ All Keys saved permanently in .env!")