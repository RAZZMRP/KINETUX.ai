import streamlit as st
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import requests
import urllib.parse
import base64
import os
import json
import re
from datetime import datetime, timedelta

# --- PAGE SETUP ---
st.set_page_config(
    page_title="KINETUX Ai",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE INITIALIZATION ---
defaults = {
    "active_tab": "New chat",
    "show_more_pocket": False,
    "show_settings_pocket": False,
    "show_account_switcher": False,
    "theme_mode": "Dark",
    "dev_mode": False,
    "model_mode": "Kinetux Auto",
    "current_user": None,
    "library": [],
    "notebooks": ["Free AI Platform Kaise Banayein", "Cartoon Story Ideas"],
    "prompt_prefill": ""
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- USER DATABASE ---
DB_FILE = "kinetux_users.json"

def load_users():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

users_db = load_users()

@st.cache_data(ttl=3600)
def get_ip_location():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=3).json()
        return r.get("ip", "127.0.0.1"), f"{r.get('city', 'India')}, {r.get('country_name', 'IN')}"
    except:
        return "192.168.1.1", "India"

user_ip, user_loc = get_ip_location()

# --- THEME & SPACE STARS + FLOATING ASTRONAUT CSS ---
is_light = st.session_state.theme_mode == "Light"
bg_gradient = "linear-gradient(135deg, #F0F4F9 0%, #E2E8F0 100%)" if is_light else "radial-gradient(ellipse at bottom, #1B2735 0%, #090A0F 100%)"
sidebar_bg = "#F8FAFC" if is_light else "#1E1F20"
pocket_bg = "#FFFFFF" if is_light else "#282A2C"
text_color = "#1F1F1F" if is_light else "#E3E3E3"
border_color = "#CBD5E1" if is_light else "#3C4043"

st.markdown(f"""
<style>
    .stApp {{
        background: {bg_gradient};
        color: {text_color};
        overflow-x: hidden;
    }}
    .stars-layer {{
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        pointer-events: none;
        background-image: 
            radial-gradient(2px 2px at 20px 30px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 40px 70px, #a5b4fc, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 90px 40px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 160px 120px, #38bdf8, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 230px 80px, #ffffff, rgba(0,0,0,0));
        background-repeat: repeat;
        background-size: 280px 280px;
        animation: twinkle 4s infinite alternate;
        opacity: 0.65;
        z-index: 0;
    }}
    @keyframes twinkle {{
        0% {{ opacity: 0.35; }}
        100% {{ opacity: 0.85; }}
    }}
    .floating-astro {{
        position: fixed;
        right: 6%;
        top: 14%;
        font-size: 54px;
        animation: floatAstro 6s ease-in-out infinite;
        pointer-events: none;
        opacity: 0.85;
        z-index: 1;
        filter: drop-shadow(0 0 15px rgba(66,133,244,0.6));
    }}
    @keyframes floatAstro {{
        0%, 100% {{ transform: translateY(0px) rotate(-6deg); }}
        50% {{ transform: translateY(-22px) rotate(8deg); }}
    }}
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg};
        border-right: 1px solid {border_color};
    }}
    div[data-testid="stSidebar"] .stButton > button {{
        background-color: transparent;
        color: {text_color};
        border: none;
        text-align: left;
        justify-content: flex-start;
        padding: 8px 14px;
        border-radius: 24px;
        font-size: 14.5px;
        font-weight: 500;
        width: 100%;
    }}
    div[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: {pocket_bg};
    }}
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {pocket_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 28px !important;
        padding: 12px 18px !important;
        box-shadow: 0 8px 28px rgba(0,0,0,0.4) !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] input {{
        background-color: transparent !important;
        border: none !important;
        color: {text_color} !important;
        font-size: 16px !important;
    }}
    .suggestion-btn > button {{
        background-color: transparent !important;
        border: none !important;
        color: {text_color} !important;
        text-align: left !important;
        padding: 6px 10px !important;
        font-size: 14px !important;
        opacity: 0.88;
    }}
    .suggestion-btn > button:hover {{
        background-color: rgba(255,255,255,0.08) !important;
        border-radius: 12px !important;
        opacity: 1;
    }}
    .pro-pill {{
        background-color: #1A73E8;
        color: white;
        padding: 2px 9px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
    }}
</style>
<div class="stars-layer"></div>
<div class="floating-astro">👨‍🚀</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. LEFT SIDEBAR
# ==========================================
with st.sidebar:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_file = os.path.join(base_dir, "logo.png")
    logo_b64 = base64.b64encode(open(logo_file, "rb").read()).decode() if os.path.exists(logo_file) else None

    c_logo, c_name, c_icons = st.columns([1.2, 3.3, 1.5])
    with c_logo:
        if logo_b64:
            st.markdown(f'<img src="data:image/png;base64,{logo_b64}" style="width:36px; height:36px; object-fit:contain; border-radius:8px; margin-top:4px;">', unsafe_allow_html=True)
        else:
            st.markdown("### ✦")
    with c_name:
        st.markdown("### **KINETUX**")
    with c_icons:
        st.markdown("<div style='padding-top:10px; font-size:15px;'>🔍 &nbsp;❐</div>", unsafe_allow_html=True)

    search_txt = st.text_input("Search", placeholder="Search Kinetux...", label_visibility="collapsed")

    if st.button("📝  New chat"):
        st.session_state.active_tab = "New chat"
        st.session_state.show_settings_pocket = False
    if st.button("⊞  Library"):
        st.session_state.active_tab = "Library"
        st.session_state.show_settings_pocket = False
    if st.button("🖼️  Images"):
        st.session_state.active_tab = "Images"
        st.session_state.show_settings_pocket = False
    if st.button("🕒  Scheduled"):
        st.session_state.active_tab = "Scheduled"
        st.session_state.show_settings_pocket = False
    if st.button("🎓  Students"):
        st.session_state.active_tab = "Students"
        st.session_state.show_settings_pocket = False

    if st.button("•••  More"):
        st.session_state.show_more_pocket = not st.session_state.show_more_pocket

    if st.session_state.show_more_pocket:
        with st.container(border=True):
            if st.button("⚙️  Customise"):
                st.session_state.active_tab = "Customise"
                st.session_state.show_more_pocket = False
            if st.button("🎬  Videos"):
                st.session_state.active_tab = "Videos"
                st.session_state.show_more_pocket = False

    st.markdown("---")
    st.caption("Notebooks")
    if st.button("＋  New notebook"):
        st.session_state.notebooks.append(f"Cartoon Script #{len(st.session_state.notebooks)+1}")

    st.caption("All")
    for nb in st.session_state.notebooks:
        if not search_txt or search_txt.lower() in nb.lower():
            st.markdown(f"<div style='padding:5px 12px; font-size:13.5px; opacity:0.85;'>{nb}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ==========================================
    # 3. BOTTOM PROFILE BAR + SETTINGS GEAR
    # ==========================================
    curr_email = st.session_state.current_user
    
    if not curr_email:
        col_g1, col_g2 = st.columns([4, 1])
        with col_g1:
            if st.button("👤 Sign in / Add Account"):
                st.session_state.show_account_switcher = not st.session_state.show_account_switcher
        with col_g2:
            if st.button("⚙️"):
                st.session_state.show_settings_pocket = not st.session_state.show_settings_pocket
    else:
        u_info = users_db[curr_email]
        plan_badge = "Pro" if u_info["plan"] in ["pro_99", "ultra", "trial"] else "Free"
        col_u1, col_u2 = st.columns([4, 1])
        with col_u1:
            if st.button(f"🟢 {u_info['name']} ({plan_badge})"):
                st.session_state.show_account_switcher = not st.session_state.show_account_switcher
        with col_u2:
            if st.button("⚙️"):
                st.session_state.show_settings_pocket = not st.session_state.show_settings_pocket

    if st.session_state.show_account_switcher:
        with st.container(border=True):
            if curr_email:
                u_info = users_db[curr_email]
                st.markdown(f"**{u_info['name']}** <span class='pro-pill'>{u_info['plan'].upper()}</span>", unsafe_allow_html=True)
                st.caption(curr_email)
                st.markdown("---")
                for em, details in users_db.items():
                    if em != curr_email:
                        if st.button(f"🔄 {details['name']} ({em[:14]}...)"):
                            st.session_state.current_user = em
                            st.rerun()

            st.markdown("**➕ Add another account**")
            with st.form("add_acc_form", clear_on_submit=True):
                new_name = st.text_input("Full Name", placeholder="Rajveer Purohit")
                new_email = st.text_input("Google / Email ID", placeholder="example@gmail.com")
                if st.form_submit_button("Add & Connect Account", use_container_width=True):
                    if new_email:
                        em_clean = new_email.strip().lower()
                        if em_clean not in users_db:
                            users_db[em_clean] = {
                                "name": new_name or "Creator",
                                "videos_created": 0,
                                "plan": "free",
                                "plan_expiry": None,
                                "memory": "",
                                "skills": "Cartoon Director",
                                "avatar": "Astronaut",
                                "gems": "3D Pixar"
                            }
                            save_users(users_db)
                        st.session_state.current_user = em_clean
                        st.session_state.show_account_switcher = False
                        st.rerun()

            if curr_email:
                if st.button("🚪 Sign out of all accounts", use_container_width=True):
                    st.session_state.current_user = None
                    st.session_state.show_account_switcher = False
                    st.rerun()

    if st.session_state.show_settings_pocket:
        with st.container(border=True):
            st.caption("Account")
            if st.button("🕒  Usage limits"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button("💳  Manage subscription"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button("✦  Upgrade to Kinetux AI Ultra"):
                st.session_state.active_tab = "Settings_Sub"

            st.caption("Preferences")
            if st.button("🧠  Personal intelligence"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button("🛠️  Skills, Avatar & Gems"):
                st.session_state.active_tab = "Settings_Sub"
            
            new_t = st.selectbox("🎨 Theme", ["Dark", "Light", "System"], index=["Dark", "Light", "System"].index(st.session_state.theme_mode))
            if new_t != st.session_state.theme_mode:
                st.session_state.theme_mode = new_t
                st.rerun()

            st.session_state.dev_mode = st.toggle("</> Developer Mode", value=st.session_state.dev_mode)
            st.checkbox("🌐 Browser & Task Settings", value=True)

            st.caption("Data and privacy")
            if st.button("📥  Import memory to Kinetux"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button("🔗  Your public links"):
                st.session_state.active_tab = "Settings_Sub"
            if st.button("💬  Send feedback & Help"):
                st.session_state.active_tab = "Settings_Sub"

            st.markdown(f"<small>📍 <b>Location:</b> {user_loc}<br>🌐 <b>IP:</b> {user_ip}<br>🕒 <b>Activity:</b> Active</small>", unsafe_allow_html=True)

# ==========================================
# 4. ACCESS & SUBSCRIPTION LOGIC
# ==========================================
def check_subscription(email):
    if not email:
        return False, "NO_ACCOUNT"
    u = users_db[email]
    if u["plan"] == "free":
        if u["videos_created"] < 2:
            return True, f"Free Plan: {2 - u['videos_created']} cartoon videos remaining."
        return False, "LIMIT_OVER"
    elif u["plan"] in ["trial", "pro_99", "ultra"]:
        exp = u.get("plan_expiry")
        if exp and datetime.now() < datetime.fromisoformat(exp):
            return True, f"{u['plan'].upper()} Plan Active!"
        return False, "EXPIRED"
    return False, "LIMIT_OVER"

# ==========================================
# 5. SMART CARTOON SCRIPT GENERATOR (NO API KEY ERROR)
# ==========================================
def generate_cartoon_scenes(story, lang_code):
    prompt = f"""Create a 3-scene kids cartoon video script for: "{story}".
Return ONLY a valid JSON array of 3 objects. Each object must have two keys:
"narration": 1-2 short engaging sentences in {"Hindi" if lang_code=="hi" else "English"}.
"image_prompt": detailed 3D Pixar colorful cartoon illustration prompt in English.
Do not write any extra text outside JSON."""

    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?json=true"
        res = requests.get(url, timeout=30).text
        match = re.search(r'\[.*\]', res, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, list) and len(data) >= 1:
                return data[:3]
    except Exception:
        pass

    # Built-in Smart Fallback Scenes (100% Guaranteed Working)
    if lang_code == "hi":
        return [
            {"narration": f"Ek baar ki baat hai, {story}. Yeh kahani bahut hi romanchak thi.", "image_prompt": f"3D Pixar colorful cartoon opening scene, {story}, bright sunny sky, cute characters"},
            {"narration": "Sabhi doston ne milkar ek naya safar shuru kiya aur khoob masti ki.", "image_prompt": f"3D Pixar cartoon adventure scene, {story}, vibrant magical background, happy expressions"},
            {"narration": "Aur is tarah unhone apni samajhdari se sabka dil jeet liya!", "image_prompt": f"3D Pixar cartoon happy ending celebration, {story}, fireworks and glowing stars"}
        ]
    else:
        return [
            {"narration": f"Once upon a time, {story}. It was the beginning of an amazing adventure.", "image_prompt": f"3D Pixar colorful cartoon opening scene, {story}, bright sunny sky, cute characters"},
            {"narration": "Together with friends, they explored a magical world full of wonders.", "image_prompt": f"3D Pixar cartoon adventure scene, {story}, vibrant magical background, happy expressions"},
            {"narration": "In the end, everyone celebrated their wonderful journey under the stars!", "image_prompt": f"3D Pixar cartoon happy ending celebration, {story}, fireworks and glowing stars"}
        ]

# ==========================================
# 6. MAIN SCREEN WORKSPACE
# ==========================================
tab = st.session_state.active_tab

if tab == "New chat":
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    user_greeting = f"Hello, {users_db[curr_email]['name']}" if curr_email else "Welcome to KINETUX Ai"
    st.markdown(f"<p style='text-align:center; color:#8AB4F8; font-size:18px; margin-bottom:0;'>✦ {user_greeting}</p>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center; font-size:44px; font-weight:500; margin-top:4px;'>Where should we start?</h1>", unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 3.2, 1])
    with center_col:
        with st.container(border=True):
            c_plus, c_input = st.columns([0.5, 9.5])
            with c_plus:
                st.markdown("<h3 style='margin-top:4px; opacity:0.8;'>＋</h3>", unsafe_allow_html=True)
            with c_input:
                story_input = st.text_input(
                    "Ask Kinetux",
                    value=st.session_state.prompt_prefill,
                    placeholder="Ask Kinetux — Apne cartoon video ki kahani likhein...",
                    label_visibility="collapsed"
                )

            b1, b2, b3, b4 = st.columns([2.2, 2.2, 0.8, 2.3])
            with b1:
                voice_lang = st.selectbox("Lang", ["Hindi Voice", "English Voice"], label_visibility="collapsed")
            with b2:
                st.session_state.model_mode = st.selectbox("Model", ["Kinetux Auto ⌄", "3D Pixar Pro", "2D Anime"], label_visibility="collapsed")
            with b3:
                if st.button("🎙️", help="Voice Dictation"):
                    st.toast("🎙️ Voice Dictation Ready!")
            with b4:
                run_gen = st.button("🚀 Generate Video", type="primary", use_container_width=True)

        st.markdown("<div style='margin-top:14px;' class='suggestion-btn'>", unsafe_allow_html=True)
        if st.button("📋  Help me polish a formal notice"):
            st.session_state.prompt_prefill = "Help me polish a formal notice for school annual cartoon competition"
            st.rerun()
        if st.button("✏️  Give me writing prompts based on my life"):
            st.session_state.prompt_prefill = "Give me writing prompts based on my life in a cute 3D animated cartoon story"
            st.rerun()
        if st.button("✦  Create an image of a floating astronaut"):
            st.session_state.prompt_prefill = "Create an animated cartoon video of a floating astronaut discovering a glowing planet"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # --- HANDLE GENERATION ---
        if run_gen:
            if not curr_email:
                st.warning("👤 Video banane ke liye pehle niche left sidebar me **Sign in / Add Account** par click karke apna email account jodein.")
                st.session_state.show_account_switcher = True
                st.stop()

            allowed, status_code = check_subscription(curr_email)
            u_obj = users_db[curr_email]

            if not allowed:
                with st.container(border=True):
                    st.subheader("🔒 Free Cartoon Limit Reached (2/2 Used)")
                    st.write("Aage cartoon videos banane ke liye **7-Day Free Trial** start karein ya **₹99/Month** plan lein.")
                    t_col1, t_col2 = st.columns(2)
                    with t_col1:
                        if st.button("🎁 Activate 7-Day Free Trial", use_container_width=True):
                            u_obj["plan"] = "trial"
                            u_obj["plan_expiry"] = (datetime.now() + timedelta(days=7)).isoformat()
                            save_users(users_db)
                            st.rerun()
                    with t_col2:
                        if st.button("💳 Subscribe ₹99 / Month", type="primary", use_container_width=True):
                            u_obj["plan"] = "pro_99"
                            u_obj["plan_expiry"] = (datetime.now() + timedelta(days=30)).isoformat()
                            save_users(users_db)
                            st.rerun()
                st.stop()

            if not story_input.strip():
                st.warning("⚠️ Kripya 'Ask Kinetux' box me cartoon ki story likhein!")
                st.stop()

            try:
                lang_code = "hi" if "Hindi" in voice_lang else "en"
                status = st.status("🎬 KINETUX Ai cartoon video bana raha hai...", expanded=True)

                status.write("📝 Step 1: KINETUX AI cartoon script aur scenes bana raha hai...")
                scenes = generate_cartoon_scenes(story_input, lang_code)

                if st.session_state.dev_mode:
                    st.json(scenes)

                clips = []
                temp_dir = os.path.join(base_dir, "temp_kinetux")
                os.makedirs(temp_dir, exist_ok=True)

                for i, sc in enumerate(scenes):
                    status.write(f"🎨 Step 2.{i+1}: Scene {i+1} ka cartoon aur awaaz ban rahi hai...")
                    a_path = os.path.join(temp_dir, f"a_{i}.mp3")
                    gTTS(text=sc["narration"], lang=lang_code).save(a_path)
                    a_clip = AudioFileClip(a_path)

                    img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote('3D Pixar cute cartoon, ' + sc['image_prompt'])}?width=1280&height=720&nologo=true"
                    i_path = os.path.join(temp_dir, f"s_{i}.jpg")
                    with open(i_path, "wb") as f:
                        f.write(requests.get(img_url, timeout=60).content)

                    clips.append(ImageClip(i_path).set_duration(a_clip.duration).set_audio(a_clip))

                status.write("🎞️ Step 3: Final MP4 Cartoon Video export ho raha hai...")
                out_name = f"Kinetux_{datetime.now().strftime('%H%M%S')}.mp4"
                out_path = os.path.join(base_dir, out_name)
                final_vid = concatenate_videoclips(clips, method="compose")
                final_vid.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
                for c in clips:
                    c.close()

                u_obj["videos_created"] += 1
                save_users(users_db)
                st.session_state.library.append({"title": story_input, "path": out_path})

                status.update(label="✅ KINETUX Ai Video Taiyar Hai!", state="complete", expanded=False)
                st.video(out_path)
                with open(out_path, "rb") as f:
                    st.download_button("⬇️ Download MP4 Video", f, file_name=out_name, mime="video/mp4", use_container_width=True)

            except Exception as e:
                st.error(f"Error: {e}")

# ------------------------------------------
# SETTINGS SUB-PAGES
# ------------------------------------------
elif tab.startswith("Settings_"):
    st.title("⚙️ KINETUX Ai Account & Settings")
    if not curr_email:
        st.warning("Pehle sidebar se apna Account Sign In karein.")
    else:
        u_obj = users_db[curr_email]
        with st.container(border=True):
            st.subheader(f"👤 {u_obj['name']} ({curr_email})")
            st.write(f"**Current Plan:** `{u_obj['plan'].upper()}` | **Videos Generated:** `{u_obj['videos_created']}`")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🎁 Start 7-Day Free Trial", use_container_width=True):
                    u_obj["plan"] = "trial"
                    u_obj["plan_expiry"] = (datetime.now() + timedelta(days=7)).isoformat()
                    save_users(users_db)
                    st.success("7-Day Trial Activated!")
            with c2:
                if st.button("💳 Subscribe ₹99 / Month", type="primary", use_container_width=True):
                    u_obj["plan"] = "pro_99"
                    u_obj["plan_expiry"] = (datetime.now() + timedelta(days=30)).isoformat()
                    save_users(users_db)
                    st.success("₹99 Pro Subscription Activated!")
            with c3:
                if st.button("✦ Upgrade to Kinetux AI Ultra", use_container_width=True):
                    u_obj["plan"] = "ultra"
                    u_obj["plan_expiry"] = (datetime.now() + timedelta(days=30)).isoformat()
                    save_users(users_db)
                    st.success("Upgraded to Kinetux AI Ultra!")

        st.subheader("🧠 Personal Intelligence, Skills, Avatar & Gems")
        u_obj["memory"] = st.text_area("Import / Edit Personal Memory:", value=u_obj.get("memory", ""))
        col_a, col_b, col_c = st.columns(3)
        u_obj["skills"] = col_a.selectbox("Skills", ["Cartoon Director", "Kids Storyteller", "Anime Creator"])
        u_obj["avatar"] = col_b.selectbox("Avatar", ["Astronaut", "3D Robot", "Cute Lion"])
        u_obj["gems"] = col_c.selectbox("Gems", ["3D Pixar", "Disney Classic", "2D Anime"])
        if st.button("Save All Preferences"):
            save_users(users_db)
            st.success("✅ Preferences Saved!")

        st.info(f"🔗 **Your Public Link:** `https://kinetux.ai/u/{u_obj['name'].lower().replace(' ', '')}` | 📍 **Location:** {user_loc} | 🌐 **IP:** {user_ip}")

# ------------------------------------------
# OTHER TABS
# ------------------------------------------
elif tab == "Library":
    st.title("⊞ Cartoon Library")
    if not st.session_state.library:
        st.info("Abhi tak koi cartoon video nahi bana hai.")
    for item in reversed(st.session_state.library):
        st.subheader(item["title"])
        if os.path.exists(item["path"]):
            st.video(item["path"])

elif tab == "Images":
    st.title("🖼️ AI Cartoon Image Generator")
    img_p = st.text_input("Describe cartoon image:", value="A floating astronaut in space, 3D Pixar style")
    if st.button("Generate Image") and img_p:
        st.image(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_p)}?width=1024&height=1024&nologo=true")

elif tab == "Scheduled":
    st.title("🕒 Scheduled Cartoon Releases")
    st.date_input("Select Release Date")
    st.text_input("Cartoon Video Title")
    st.button("Schedule Release")

elif tab == "Students":
    st.title("🎓 KINETUX Students Program")
    st.success("Students ko ₹99 wale subscription par 50% discount milta hai!")

elif tab == "Customise":
    st.title("⚙️ Customise KINETUX")
    st.selectbox("Video Resolution", ["1080p Full HD", "720p HD", "4K Ultra"])

elif tab == "Videos":
    st.title("🎬 Trending Cartoon Templates")
    st.info("New chat me jakar kisi bhi story par click karein aur 1-click me video banayein.")