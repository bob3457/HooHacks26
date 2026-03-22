import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# ── Auth guard ───────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.switch_page("login.py")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "users.db")


# ── Database ─────────────────────────────────────────────────────────────────
def init_farm_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS farm_crops (
            id         INTEGER PRIMARY KEY,
            user_email TEXT    NOT NULL,
            crop_name  TEXT    NOT NULL,
            acres      REAL    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_farmer_crops(email: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT id, crop_name, acres FROM farm_crops WHERE user_email = ?",
        conn, params=(email,),
    )
    conn.close()
    return df


def add_crop(email: str, crop_name: str, acres: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO farm_crops (user_email, crop_name, acres) VALUES (?,?,?)",
        (email, crop_name, acres),
    )
    conn.commit()
    conn.close()


def delete_crop(row_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM farm_crops WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


# ── Fertilizer calculation (swap body with real function later) ───────────────
def get_fertilizer_totals(crops_df: pd.DataFrame) -> dict:
    """
    PLACEHOLDER — replace the body with a call to your calculation module, e.g.:
        from backend.src.features.engineer import calculate_fertilizer
        return calculate_fertilizer(crops_df)

    Receives the farmer's crops DataFrame (columns: crop_name, acres).
    Returns a dict with keys:
        fertilizer_used_lbs (float)  |  fertilizer_cost_usd (float)
    """
    # Dummy rates per acre
    rates = {"Corn": (150, 60), "Soybeans": (100, 50), "Wheat": (100, 40), "Cotton": (120, 60)}
    default = (110, 50)
    used, cost = 0.0, 0.0
    for _, row in crops_df.iterrows():
        lbs_per_acre, cost_per_acre = rates.get(row["crop_name"], default)
        used += lbs_per_acre * row["acres"]
        cost += cost_per_acre * row["acres"]
    return {"fertilizer_used_lbs": used, "fertilizer_cost_usd": cost}


# ── Price / risk data functions (swap bodies with real model calls later) ─────
def get_fertilizer_price_forecast() -> pd.DataFrame:
    """
    PLACEHOLDER — replace the body with a call to your forecasting module, e.g.:
        from backend.src.models.forecaster import predict_fertilizer_prices
        return predict_fertilizer_prices()

    Returns a DataFrame with columns:
        month (str)  |  predicted_price_per_ton (float)
    """
    base = datetime.today().replace(day=1)
    months = [(base + timedelta(days=31 * i)).strftime("%b %Y") for i in range(12)]
    prices = [520, 535, 548, 560, 572, 558, 545, 530, 518, 510, 505, 512]
    return pd.DataFrame({"month": months, "predicted_price_per_ton": prices})


def get_buy_advice() -> dict:
    """
    PLACEHOLDER — replace the body with a call to your signals/risk module, e.g.:
        from backend.src.signals.engine import get_fertilizer_advice
        return get_fertilizer_advice()

    Returns a dict with keys:
        recommendation (str)  |  risk_level (str)  |  reasoning (str)
    """
    return {
        "recommendation": "Buy within the next 30 days",
        "risk_level": "Medium",
        "reasoning": (
            "Current futures indicate a ~10% price increase over the next quarter. "
            "Locking in supply now reduces exposure to spring demand spikes. "
            "Weather models suggest normal planting conditions, supporting stable demand."
        ),
    }


# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Gas Forecast — Dashboard", page_icon="🌾", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid='stSidebarNav'] { display: none; }
    [data-testid='collapsedControl'] { display: none; }
    section[data-testid='stSidebar'] { display: none; }
    header[data-testid='stHeader'] { display: none; }
    body, .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: #1a5c2a; font-family: system-ui, sans-serif; }

    /* shrink top padding so content starts higher */
    .block-container { padding-top: 0.5rem !important; }

    /* Sticky header row — first direct child of the top-level vertical block */
    section[data-testid="stMain"] > div > div[data-testid="stVerticalBlock"] > div:first-child {
        position: sticky;
        top: 0;
        z-index: 999;
        background: white;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #e8f4e8;
    }

    /* Keep "Logged in as …" on one line */
    .user-email-bar {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: right;
        padding-top: 0.42rem;
        font-size: 0.95rem;
        color: #444;
    }

    /* Prevent button labels from wrapping */
    .stButton button, button[data-testid^="stBaseButton"] {
        white-space: nowrap !important;
    }

    .banner {
        background-color: #f0f7f0;
        border: 1px solid #d4edda;
        padding: 2.8rem 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }

    .metric-card {
        background: #f9fbf9;
        border: 1px solid #e0e0e0;
        border-radius: 0px;
        padding: 2rem 1.5rem;
        text-align: center;
    }

    .metric-label {
        color: #666;
        font-size: 1rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .metric-value {
        color: #1a5c2a;
        font-size: 2.4rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }

    .advice-card {
        background: #f9fbf9;
        border-left: 4px solid #1a5c2a;
        border-radius: 0px;
        padding: 2rem 1.8rem;
        margin-top: 1.5rem;
    }

    .risk-medium { color: #e67e22; font-weight: 600; }
    .risk-low    { color: #27ae60; font-weight: 600; }
    .risk-high   { color: #e74c3c; font-weight: 600; }

    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: #999;
        font-size: 1.1rem;
        background: #f9fbf9;
        border: 1px solid #e0e0e0;
    }

    /* make tab labels bigger */
    button[data-baseweb="tab"] { font-size: 1.05rem !important; }
</style>
""", unsafe_allow_html=True)

init_farm_db()
email = st.session_state.user_email
df = get_farmer_crops(email)

# ── Top-right user bar ────────────────────────────────────────────────────────
_, col_user, col_signout = st.columns([5, 3, 1])
with col_user:
    st.markdown(f'<div class="user-email-bar">Logged in as <strong>{email}</strong></div>', unsafe_allow_html=True)
with col_signout:
    if st.button("Sign Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.switch_page("login.py")

# ── Banner ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="banner">
    <h1 style="margin:0 0 0.6rem 0; font-size:3.2rem;">🌾 Gas Forecast</h1>
    <p style="margin:0; color:#555; font-size:1.2rem;">Fertilizer intelligence for farmers</p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_overview, tab_fertilizer = st.tabs(["Overview", "Fertilizer Costs & Risk Assessment"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
with tab_overview:

    # ── Add crop form ─────────────────────────────────────────────────────
    with st.expander("Add a Crop", expanded=df.empty):
        with st.form("add_crop_form", clear_on_submit=True):
            col_a, col_b, col_c = st.columns([3, 2, 1])
            crop_input  = col_a.text_input("Crop name", placeholder="e.g. Corn")
            acres_input = col_b.text_input("Acres", placeholder="e.g. 320")
            col_c.markdown("<br>", unsafe_allow_html=True)
            submitted = col_c.form_submit_button("Add", use_container_width=True)
            if submitted:
                if not crop_input.strip():
                    st.warning("Please enter a crop name.")
                    st.stop()
                try:
                    acres_val = float(acres_input.strip().replace(",", ""))
                    if acres_val <= 0:
                        raise ValueError
                except ValueError:
                    st.warning("Please enter a valid number of acres.")
                    st.stop()
                add_crop(email, crop_input.strip().title(), acres_val)
                st.success(f"Added {crop_input.strip().title()} ({acres_val:,.0f} acres).")
                st.rerun()

    # ── No data state ─────────────────────────────────────────────────────
    if df.empty:
        st.markdown(
            '<div class="empty-state">'
            '<p style="font-size:1.4rem; font-weight:500; margin-bottom:0.8rem;">No farm data yet</p>'
            '<p style="color:#999; font-size:1.1rem;">Use the form above to add your crops and acreage.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        fert = get_fertilizer_totals(df)
        total_acres      = df["acres"].sum()
        num_crops        = df["crop_name"].nunique()
        total_fertilizer = fert["fertilizer_used_lbs"]
        total_cost       = fert["fertilizer_cost_usd"]

        c1, c2, c3, c4 = st.columns(4)
        for col, label, value in [
            (c1, "Total Acres",     f"{total_acres:,.0f}"),
            (c2, "Different Crops", str(num_crops)),
            (c3, "Fertilizer Used", f"{total_fertilizer:,.0f} lbs"),
            (c4, "Fertilizer Cost", f"${total_cost:,.0f}"),
        ]:
            col.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">{label}</div>'
                f'<div class="metric-value">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        col_chart, col_gap, col_table = st.columns([5, 0.3, 3])

        with col_chart:
            st.subheader("Crop Distribution")
            fig = px.pie(
                df,
                values="acres",
                names="crop_name",
                color_discrete_sequence=px.colors.sequential.Greens_r,
                hole=0.35,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.subheader("Crop Breakdown")
            for _, row in df.iterrows():
                r1, r2 = st.columns([3, 1])
                r1.markdown(f"**{row['crop_name']}** · {row['acres']:,.0f} acres")
                if r2.button("Remove", key=f"del_{row['id']}", use_container_width=True):
                    delete_crop(row["id"])
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — FERTILIZER COSTS & RISK ASSESSMENT
# ════════════════════════════════════════════════════════════════════════════
with tab_fertilizer:
    st.subheader("Predicted Fertilizer Price")
    st.caption("Next 12 months forecast")

    forecast_df = get_fertilizer_price_forecast()

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=forecast_df["month"],
        y=forecast_df["predicted_price_per_ton"],
        mode="lines+markers",
        line=dict(color="#1a5c2a", width=2),
        marker=dict(size=6, color="#1a5c2a"),
        name="Predicted $/ton",
        hovertemplate="%{x}<br><b>$%{y}/ton</b><extra></extra>",
    ))
    fig2.update_layout(
        xaxis_title="Month",
        yaxis_title="Price per Ton (USD)",
        yaxis=dict(tickprefix="$"),
        plot_bgcolor="#f9fbf9",
        paper_bgcolor="white",
        margin=dict(t=20, b=40, l=60, r=20),
        font=dict(family="system-ui, sans-serif"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Buying Advice")

    advice = get_buy_advice()
    risk   = advice["risk_level"]
    risk_class = f"risk-{risk.lower()}"

    st.markdown(
        f'<div class="advice-card">'
        f'<p style="font-size:1.2rem; font-weight:600; color:#1a5c2a; margin:0 0 0.9rem 0;">'
        f'📋 {advice["recommendation"]}</p>'
        f'<p style="margin:0 0 0.7rem 0; font-size:1.05rem;">Risk Level: <span class="{risk_class}">{risk}</span></p>'
        f'<p style="color:#555; margin:0; line-height:1.6; font-size:1.05rem;">{advice["reasoning"]}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
