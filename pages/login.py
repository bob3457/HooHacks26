import streamlit as st
import sqlite3
import re
import os
import base64
import bcrypt
import secrets
import time


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "users.db")
IMAGES_DIR = os.path.join(_ROOT, "images")


def get_image_base64(filename):
    img_path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            ext  = filename.split(".")[-1].lower()
            mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
            return f"data:{mime};base64,{data}"
    return None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS session_tokens "
        "(token TEXT PRIMARY KEY, email TEXT NOT NULL, expires_at INTEGER NOT NULL)"
    )
    try:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    except sqlite3.OperationalError:
        pass
    conn.execute("DELETE FROM users WHERE password_hash IS NULL")
    conn.execute("DELETE FROM session_tokens WHERE expires_at < ?", (int(time.time()),))
    conn.commit()
    conn.close()


def create_session_token(email: str) -> str:
    token   = secrets.token_urlsafe(32)
    expires = int(time.time()) + SESSION_TTL
    conn    = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO session_tokens (token, email, expires_at) VALUES (?, ?, ?)",
        (token, email, expires),
    )
    conn.commit()
    conn.close()
    return token


def validate_session_token(token: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT email FROM session_tokens WHERE token = ? AND expires_at > ?",
        (token, int(time.time())),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def delete_session_token(token: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM session_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def email_exists(email: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row is not None


def get_password_hash(email: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def register_user(email: str, password: str) -> bool:
    hashed = hash_password(password)
    conn   = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


# ── Init ──────────────────────────────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="Gas Forecast", page_icon="🌱",
    layout="centered", initial_sidebar_state="collapsed",
)

st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}"
    "[data-testid='collapsedControl']{display:none;}"
    "section[data-testid='stSidebar']{display:none;}</style>",
    unsafe_allow_html=True,
)

aerial_view_bg = get_image_base64("aerial_view.jpg")
bg_url = aerial_view_bg or "linear-gradient(#f0f7f0,#e8f5e9)"

st.markdown(f"""
<style>
    body, .stApp {{
        background: linear-gradient(rgba(0,0,0,0.5),rgba(0,0,0,0.5)), url('{bg_url}');
        background-size: cover; background-position: center; background-attachment: fixed;
    }}
    .block-container {{
        padding-top: 4rem; background: rgba(255,255,255,0.95);
        border-radius: 12px; margin: 2rem auto; max-width: 450px;
        padding: 2rem; box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }}
    h1,h2,h3,p,label,.stMarkdown {{ color: #1a5c2a !important; }}
    .stTextInput>div>div>input {{ border:1.5px solid #4caf50; border-radius:8px; color:#1a5c2a; }}
    .stTextInput>div>div>input:focus {{ border-color:#2e7d32; box-shadow:0 0 0 2px rgba(76,175,80,.25); }}
    .stButton>button {{
        background-color:#4caf50; color:white; border:none; border-radius:8px;
        padding:.5rem 2rem; font-size:1rem; font-weight:600; width:100%;
    }}
    .stButton>button:hover {{ background-color:#388e3c; }}
    .auth-footer {{ text-align:center; font-size:.85rem; color:#666; margin-top:1rem; }}
    .auth-footer a {{ color:#2e7d32; font-weight:700; text-decoration:none; margin-left:.25rem; }}
    .logo-area {{ text-align:center; margin-bottom:1.5rem; }}
</style>
""", unsafe_allow_html=True)

# ── Session bootstrap ─────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Check for a persisted token in the URL query params
if not st.session_state.logged_in:
    _tok = st.query_params.get("s")
    if _tok:
        _email = validate_session_token(_tok)
        if _email:
            st.session_state.logged_in         = True
            st.session_state.user_email        = _email
            st.session_state["_session_token"] = _tok

if st.session_state.logged_in:
    st.switch_page("pages/main_app.py")

# ── Login / Register UI ───────────────────────────────────────────────────────
st.markdown('<div class="logo-area"><span style="font-size:3rem;">🌾</span></div>', unsafe_allow_html=True)
st.markdown("<h2 style='text-align:center;font-weight:700;'>Gas Forecast</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#4caf50!important;margin-bottom:2rem;'>Smart alerts for your farm</p>", unsafe_allow_html=True)

if "register_prefill" not in st.session_state:
    st.session_state.register_prefill = False

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
    st.markdown("<p style='text-align:center;font-size:1.05rem;font-weight:600;'>Create an account</p>", unsafe_allow_html=True)
    prefill = st.session_state.pop("_reg_prefill_email", "")
    if prefill and "reg_email" not in st.session_state:
        st.session_state["reg_email"] = prefill
    new_email        = st.text_input("Email address", key="reg_email", placeholder="you@example.com")
    new_password     = st.text_input("Password", type="password", key="reg_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
    if st.button("Create Account", key="btn_register"):
        if not new_email.strip():
            st.warning("Please enter your email.")
        elif not new_password.strip():
            st.warning("Please enter a password.")
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
                _tok = create_session_token(new_email.strip().lower())
                st.session_state.logged_in         = True
                st.session_state.user_email        = new_email.strip().lower()
                st.session_state["_session_token"] = _tok
                st.session_state.register_prefill  = False
                st.query_params["s"] = _tok
                st.switch_page("pages/main_app.py")
            else:
                st.error("Failed to create account. Please try again.")
    st.markdown('<p class="auth-footer">Already have an account?<a href="?action=login" target="_self">Sign in</a></p>', unsafe_allow_html=True)
else:
    email    = st.text_input("Email address", key="login_email", placeholder="you@example.com")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Sign In", key="btn_login"):
        if not email.strip():
            st.warning("Please enter your email.")
        elif not password.strip():
            st.warning("Please enter your password.")
        elif not is_valid_email(email.strip()):
            st.warning("Please enter a valid email address.")
        elif not email_exists(email.strip().lower()):
            st.session_state.register_prefill      = True
            st.session_state["_reg_prefill_email"] = email.strip().lower()
            st.rerun()
        else:
            hashed = get_password_hash(email.strip().lower())
            if not hashed:
                st.error("No password set for this account. Please create a new account.")
            elif verify_password(password.strip(), hashed):
                _tok = create_session_token(email.strip().lower())
                st.session_state.logged_in         = True
                st.session_state.user_email        = email.strip().lower()
                st.session_state["_session_token"] = _tok
                st.query_params["s"] = _tok
                st.switch_page("pages/main_app.py")
            else:
                st.error("Incorrect password.")
    st.markdown('<p class="auth-footer">Don\'t have an account?<a href="?action=register" target="_self">Create one</a></p>', unsafe_allow_html=True)
