import streamlit as st
import sqlite3
import re
import os
import base64
import bcrypt


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def get_image_base64(filename):
    """Convert image to base64 data URL"""
    img_path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(img_path):
        with open(img_path, "rb") as img_file:
            data = base64.b64encode(img_file.read()).decode()
            ext = filename.split(".")[-1].lower()
            mime_type = "image/jpeg" if ext == "jpg" else f"image/{ext}"
            return f"data:{mime_type};base64,{data}"
    return None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT)"
    )
    # Add password_hash column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def email_exists(email: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row is not None


def get_password_hash(email: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row[0] if row else None


def register_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
    conn.commit()
    conn.close()


def register_user(email: str, password: str):
    hashed = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email already exists
    finally:
        conn.close()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


init_db()

st.set_page_config(page_title="Gas Forecast", page_icon="🌱", layout="centered", initial_sidebar_state="collapsed")

st.markdown("<style>[data-testid='stSidebarNav'] { display: none; } [data-testid='collapsedControl'] { display: none; } section[data-testid='stSidebar'] { display: none; }</style>", unsafe_allow_html=True)

# Get base64 encoded background
aerial_view_bg = get_image_base64("aerial_view.jpg")
bg_url = aerial_view_bg if aerial_view_bg else "linear-gradient(#f0f7f0, #e8f5e9)"

st.markdown(
    f"""
    <style>
        body, .stApp {{
            background: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)), url('{bg_url}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .block-container {{
            padding-top: 4rem;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            margin: 2rem auto;
            max-width: 450px;
            padding: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        h1, h2, h3, p, label, .stMarkdown {{
            color: #1a5c2a !important;
        }}
        .stTextInput > div > div > input {{
            border: 1.5px solid #4caf50;
            border-radius: 8px;
            color: #1a5c2a;
        }}
        .stTextInput > div > div > input:focus {{
            border-color: #2e7d32;
            box-shadow: 0 0 0 2px rgba(76,175,80,0.25);
        }}
        .stButton > button {{
            background-color: #4caf50;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            width: 100%;
            transition: background-color 0.2s;
        }}
        .stButton > button:hover {{
            background-color: #388e3c;
        }}
        .divider {{
            border-top: 1px solid #c8e6c9;
            margin: 1.5rem 0;
        }}
        .auth-footer {{
            text-align: center;
            font-size: 0.85rem;
            color: #666;
            margin-top: 1rem;
        }}
        .auth-footer a {{
            color: #2e7d32;
            font-weight: 700;
            text-decoration: none;
            margin-left: 0.25rem;
        }}
        .auth-footer a:hover {{
            text-decoration: underline;
        }}
        .logo-area {{
            text-align: center;
            margin-bottom: 1.5rem;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    st.switch_page("pages/main_app.py")
else:
    st.markdown(
        '<div class="logo-area"><span style="font-size:3rem;">🌾</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h2 style='text-align:center; font-weight:700;'>Gas Forecast</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#4caf50 !important; margin-bottom:2rem;'>Smart alerts for your farm</p>",
        unsafe_allow_html=True,
    )

    if "register_prefill" not in st.session_state:
        st.session_state.register_prefill = False

    # Handle inline link clicks via query params
    _action = st.query_params.get("action", "")
    if _action == "register":
        st.query_params.clear()
        st.session_state.register_prefill = True
        st.rerun()
    elif _action == "login":
        st.query_params.clear()
        st.session_state.register_prefill = False
        st.rerun()

    if st.session_state.register_prefill:
        # ── Register form ──────────────────────────────────────────────────
        st.markdown("<p style='text-align:center; font-size:1.05rem; font-weight:600;'>Create an account</p>", unsafe_allow_html=True)
        prefill = st.session_state.pop("_reg_prefill_email", "")
        if prefill and "reg_email" not in st.session_state:
            st.session_state["reg_email"] = prefill
        new_email = st.text_input("Email address", key="reg_email", placeholder="you@example.com")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        if st.button("Create Account", key="btn_register"):
            if not new_email.strip():
                st.warning("Please enter your email.")
            elif not new_password.strip():
                st.warning("Please enter a password.")
            elif not confirm_password.strip():
                st.warning("Please confirm your password.")
            elif new_password.strip() != confirm_password.strip():
                st.warning("Passwords do not match.")
            elif not is_valid_email(new_email.strip()):
                st.warning("Please enter a valid email address.")
            elif email_exists(new_email.strip().lower()):
                st.info("An account with this email already exists.")
                st.session_state.register_prefill = False
                st.rerun()
            else:
                if register_user(new_email.strip().lower(), new_password.strip()):
                    st.session_state.logged_in = True
                    st.session_state.user_email = new_email.strip().lower()
                    st.session_state.register_prefill = False
                    st.switch_page("pages/main_app.py")
                else:
                    st.error("Failed to create account. Please try again.")
        st.markdown('<p class="auth-footer">Already have an account?<a href="?action=login" target="_self">Sign in</a></p>', unsafe_allow_html=True)
    else:
        # ── Sign In form ───────────────────────────────────────────────────
        email = st.text_input("Email address", key="login_email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign In", key="btn_login"):
            if not email.strip():
                st.warning("Please enter your email.")
            elif not password.strip():
                st.warning("Please enter your password.")
            elif not is_valid_email(email.strip()):
                st.warning("Please enter a valid email address.")
            elif not email_exists(email.strip().lower()):
                st.session_state.register_prefill = True
                st.session_state["_reg_prefill_email"] = email.strip().lower()
                st.rerun()
            else:
                hashed = get_password_hash(email.strip().lower())
                if hashed and verify_password(password.strip(), hashed):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email.strip().lower()
                    st.switch_page("pages/main_app.py")
                else:
                    st.error("Incorrect password.")
        st.markdown('<p class="auth-footer">Don\'t have an account?<a href="?action=register" target="_self">Create one</a></p>', unsafe_allow_html=True)
    