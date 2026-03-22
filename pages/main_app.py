import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import colorsys
import os
import json # Make sure to import json at the top of your file!

# ── Auth guard ───────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.switch_page("login.py")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "users.db")

# Add this new line:
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "processed", "cache.json")

# ── Database ─────────────────────────────────────────────────────────────────
def init_farm_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS farm_crops (
            id         INTEGER PRIMARY KEY,
            user_email TEXT    NOT NULL,
            crop_name  TEXT    NOT NULL,
            acres      REAL    NOT NULL,
            season     TEXT    NOT NULL DEFAULT 'Spring'
        )
    """)
    # Migrate existing tables that may lack the season column
    cols = [r[1] for r in conn.execute("PRAGMA table_info(farm_crops)").fetchall()]
    if "season" not in cols:
        conn.execute("ALTER TABLE farm_crops ADD COLUMN season TEXT NOT NULL DEFAULT 'Spring'")
    conn.commit()
    conn.close()


def get_farmer_crops(email: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT id, crop_name, acres, season FROM farm_crops WHERE user_email = ?",
        conn, params=(email,),
    )
    conn.close()
    return df


def add_crop(email: str, crop_name: str, acres: float, season: str):
    """Insert or merge crop. Same crop name (case-insensitive) + same season → add acres."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, crop_name FROM farm_crops WHERE user_email=? AND LOWER(crop_name)=LOWER(?) AND season=?",
        (email, crop_name, season),
    ).fetchone()
    if row:
        conn.execute("UPDATE farm_crops SET acres = acres + ? WHERE id = ?", (acres, row[0]))
    else:
        conn.execute(
            "INSERT INTO farm_crops (user_email, crop_name, acres, season) VALUES (?,?,?,?)",
            (email, crop_name, acres, season),
        )
    conn.commit()
    conn.close()


def delete_crop(row_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM farm_crops WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


# ── Season helpers ────────────────────────────────────────────────────────────
DEFAULT_SEASONS = ["Spring", "Fall"]

# Base hue for each season (hue in 0-1 range for colorsys)
SEASON_BASE_COLORS = {"Spring": "#2ecc71", "Fall": "#e67e22"}
EXTRA_PALETTE = ["#3498db", "#9b59b6", "#e74c3c", "#1abc9c", "#f39c12", "#34495e"]


def get_season_base_colors(seasons: list) -> dict:
    """Maps each season name to a base hex color."""
    result = {}
    extra_idx = 0
    for s in seasons:
        if s in SEASON_BASE_COLORS:
            result[s] = SEASON_BASE_COLORS[s]
        else:
            result[s] = EXTRA_PALETTE[extra_idx % len(EXTRA_PALETTE)]
            extra_idx += 1
    return result


def _hex_to_hls(hex_color: str):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h, l, s) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


# Fixed alternating pattern: dark → light → medium-dark → medium-light → darkest → medium
# Applied as (lightness, saturation_scale) pairs, cycling for any number of crops
_SHADE_PATTERN = [
    (0.34, 1.00),
    (0.65, 0.70),
    (0.44, 0.90),
    (0.72, 0.55),
    (0.26, 1.00),
    (0.55, 0.80),
]


def get_crop_colors_for_df(df: pd.DataFrame, season_base: dict) -> list:
    """
    Returns a list of hex colors (one per row in df). Each crop gets a shade of
    its season's hue following the fixed _SHADE_PATTERN, so crops are visually
    distinct but clearly grouped by season.
    """
    season_shades: dict = {}
    for season in df["season"].unique():
        n = len(df[df["season"] == season])
        base = season_base.get(season, "#888888")
        hue, _, sat = _hex_to_hls(base)
        shades = [
            _hls_to_hex(hue, l, min(sat * s_scale, 1.0))
            for l, s_scale in (_SHADE_PATTERN * ((n // len(_SHADE_PATTERN)) + 1))[:n]
        ]
        season_shades[season] = {"shades": shades, "idx": 0}

    colors = []
    for _, row in df.iterrows():
        info = season_shades[row["season"]]
        colors.append(info["shades"][info["idx"]])
        info["idx"] += 1
    return colors


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
    """Reads the ML model's 3-month price forecast from the pipeline cache."""
    try:
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
            
        # Extract the ML forecast data generated by run_pipeline.py
        labels = cache["forecast"]["labels"]
        prices = cache["forecast"]["mean"]
        
        return pd.DataFrame({
            "month": labels,
            "predicted_price_per_ton": prices
        })
    except Exception as e:
        # Fallback if the cache file isn't generated yet
        print(f"Warning: Could not load cache.json: {e}")
        base = datetime.today().replace(day=1)
        months = [(base + timedelta(days=31 * i)).strftime("%b %Y") for i in range(3)]
        return pd.DataFrame({"month": months, "predicted_price_per_ton": [520, 535, 548]})

def get_buy_advice() -> dict:
    """Reads the Monte Carlo risk assessment and signal from the pipeline cache."""
    try:
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
            
        signal_data = cache["signal"]
        
        # Map the backend engine's output to our Streamlit UI dictionary
        return {
            "recommendation": signal_data["recommendation"],  # e.g., "Buy Now" or "Wait"
            "risk_level": signal_data["urgency"].title(),     # e.g., "High", "Moderate", "Low"
            "reasoning": f"{signal_data['rationale']} \n\n**Driver:** {signal_data['key_driver']}"
        }
    except Exception as e:
        return {
            "recommendation": "System Offline",
            "risk_level": "Unknown",
            "reasoning": "Could not connect to the AgriSignal AI Engine. Please run the backend pipeline."
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

# ── Season session state ──────────────────────────────────────────────────────
if "seasons" not in st.session_state:
    st.session_state.seasons = list(DEFAULT_SEASONS)

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
        # Handle "Create new season" flow outside the form
        season_options = st.session_state.seasons + ["Create new…"]
        if "pending_new_season" not in st.session_state:
            st.session_state.pending_new_season = False

        with st.form("add_crop_form", clear_on_submit=True):
            col_a, col_b, col_c, col_d = st.columns([3, 2, 2, 1])
            crop_input  = col_a.text_input("Crop name", placeholder="e.g. Corn")
            acres_input = col_b.text_input("Acres", placeholder="e.g. 320")
            season_sel  = col_c.selectbox("Season", options=season_options)
            new_season_input = col_c.text_input(
                "New season name",
                placeholder="e.g. Summer",
                key="new_season_name",
            ) if season_sel == "Create new…" else ""
            col_d.markdown("<br>", unsafe_allow_html=True)
            submitted = col_d.form_submit_button("Add", use_container_width=True)

            if submitted:
                # Resolve season
                if season_sel == "Create new…":
                    new_s = new_season_input.strip().title()
                    if not new_s:
                        st.warning("Please enter a name for the new season.")
                        st.stop()
                    if new_s not in st.session_state.seasons:
                        st.session_state.seasons.append(new_s)
                    season_val = new_s
                else:
                    season_val = season_sel

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
                add_crop(email, crop_input.strip().title(), acres_val, season_val)
                st.success(f"Added {crop_input.strip().title()} — {season_val} ({acres_val:,.0f} acres).")
                # Preserve pie filter state across the rerun
                st.session_state["_pie_select_all_saved"] = st.session_state.get("pie_select_all", True)
                st.session_state["_pie_filter_saved"] = st.session_state.get("pie_season_filter", None)
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

            # Season filter
            all_seasons_in_data = sorted(df["season"].unique().tolist())
            # Ensure any new seasons from session state are also available
            all_seasons_available = sorted(set(all_seasons_in_data + st.session_state.seasons))

            # Restore saved filter state if coming from an add-crop rerun
            if "_pie_select_all_saved" in st.session_state:
                st.session_state["pie_select_all"] = st.session_state.pop("_pie_select_all_saved")
            if "_pie_filter_saved" in st.session_state:
                saved = st.session_state.pop("_pie_filter_saved")
                if saved is not None:
                    st.session_state["pie_season_filter"] = saved

            select_all = st.checkbox("Select all seasons", value=True, key="pie_select_all")
            if select_all:
                selected_seasons = all_seasons_available
            else:
                selected_seasons = st.multiselect(
                    "Filter by season",
                    options=all_seasons_available,
                    default=all_seasons_in_data,
                    key="pie_season_filter",
                )

            filtered_df = df[df["season"].isin(selected_seasons)].copy() if selected_seasons else df.iloc[0:0].copy()

            season_base = get_season_base_colors(all_seasons_available)

            if filtered_df.empty:
                st.info("No crops match the selected seasons.")
            else:
                crop_colors = get_crop_colors_for_df(filtered_df, season_base)

                # Build legend traces: one invisible scatter per season for the color key
                fig = go.Figure()
                fig.add_trace(go.Pie(
                    labels=filtered_df["crop_name"],
                    values=filtered_df["acres"],
                    marker=dict(colors=crop_colors, line=dict(color="white", width=1.5)),
                    textposition="inside",
                    textinfo="percent+label",
                    hole=0.35,
                    showlegend=False,
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f} acres (%{percent})<extra></extra>",
                ))
                # Add dummy traces for the season legend
                for season in [s for s in all_seasons_available if s in selected_seasons]:
                    fig.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode="markers",
                        marker=dict(size=10, color=season_base[season], symbol="square"),
                        name=season,
                        showlegend=True,
                    ))
                fig.update_layout(
                    legend_title_text="Season",
                    margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(visible=False, fixedrange=True),
                    yaxis=dict(visible=False, fixedrange=True),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.subheader("Crop Breakdown")
            for _, row in df.iterrows():
                r1, r2 = st.columns([3, 1])
                r1.markdown(f"**{row['crop_name']}** · {row['acres']:,.0f} acres  \n*{row['season']}*")
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
