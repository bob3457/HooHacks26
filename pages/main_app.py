import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import colorsys
import os
import json
import numpy as np
from scipy.stats import norm as _norm
import pydeck as pdk

# ── Fertilizer constants (nitrogen intensity per crop) ────────────────────────
N_INTENSITY_LBS_PER_ACRE = {
    "Corn": 150, "Wheat": 90, "Cotton": 120,
    "Sorghum": 80, "Soybeans": 60, "Hay": 50,
}
UREA_N_CONTENT = 0.46   # urea is 46% nitrogen by weight
LBS_PER_MT     = 2204.6 # pounds per metric ton
import json # Make sure to import json at the top of your file!

# USDA 2023 planted acres by state (thousands of acres)
# (lat, lng, corn_k, wheat_k, soy_k)
_STATE_AG = {
    "Iowa":           (42.00, -93.50, 12900,     0,  9400),
    "Illinois":       (40.00, -89.00, 10800,   500, 10100),
    "Nebraska":       (41.50, -99.90, 10300,  1400,  5500),
    "Minnesota":      (46.40, -94.30,  8100,  1600,  7500),
    "Indiana":        (40.30, -86.10,  5400,   500,  5800),
    "South Dakota":   (44.30,-100.30,  5200,  1600,  4300),
    "Kansas":         (38.50, -98.40,  4400,  7800,  5000),
    "Ohio":           (40.40, -82.70,  3700,   500,  4900),
    "Wisconsin":      (44.50, -89.50,  3600,   100,  1900),
    "Missouri":       (38.30, -92.40,  3100,   600,  5400),
    "North Dakota":   (47.50,-100.50,  2600,  5500,  5900),
    "Michigan":       (44.30, -84.50,  2300,   400,  2300),
    "Texas":          (31.40, -99.30,  1900,  5000,   100),
    "Colorado":       (39.00,-105.50,  1500,  2500,   400),
    "Kentucky":       (37.80, -84.90,  1300,   400,  1600),
    "Oklahoma":       (35.60, -97.50,   400,  4500,   700),
    "Montana":        (46.90,-110.40,   200,  4500,   100),
    "North Carolina": (35.50, -79.30,   900,   100,  1100),
    "Arkansas":       (34.80, -92.20,   800,   200,  3000),
    "Tennessee":      (35.80, -86.50,   800,   200,  1500),
    "Pennsylvania":   (41.20, -77.20,  1100,   200,   700),
    "New York":       (42.50, -76.00,   800,   200,   300),
    "Mississippi":    (32.70, -89.70,   400,   100,  2300),
    "Washington":     (47.40,-120.40,   100,  2100,   100),
    "Virginia":       (37.40, -79.00,   400,   200,   600),
    "Georgia":        (32.20, -83.40,   500,   300,   500),
    "Maryland":       (39.00, -76.80,   500,   200,   300),
    "Idaho":          (44.20,-114.50,   100,  1500,   100),
    "Wyoming":        (43.00,-107.50,   100,   500,   100),
    "California":     (37.00,-119.50,   200,   700,   100),
    "Delaware":       (39.00, -75.50,   200,   100,   200),
}

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

# ── State fertilizer exposure builder ────────────────────────────────────────
def build_state_df(cache: dict) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per state containing:
      urea_mt         — total urea metric tons needed annually
      current_cost_m  — fertilizer bill at current price ($M)
      forecast_cost_m — fertilizer bill at t2 forecast price ($M)
      impact_m        — cost change vs. today ($M, positive = more expensive)
      elevation       — column height in metres for PyDeck (normalised, max 500 km)
      color           — RGBA list for PyDeck heat gradient
      tooltip         — HTML tooltip string
    """
    sig           = cache["signal"]
    current_price = sig["currentPrice"]
    forecast_t2   = sig["forecast_t2"]
    price_chg_pct = (forecast_t2 - current_price) / current_price * 100

    rows = []
    for state, (lat, lng, corn_k, wheat_k, soy_k) in _STATE_AG.items():
        n_lbs     = corn_k * 1000 * 150 + wheat_k * 1000 * 90 + soy_k * 1000 * 60
        urea_mt   = n_lbs / (UREA_N_CONTENT * LBS_PER_MT)
        cur_cost  = urea_mt * current_price / 1e6
        fc_cost   = urea_mt * forecast_t2   / 1e6
        impact    = fc_cost - cur_cost
        rows.append({
            "state":          state,
            "lat":            lat,
            "lng":            lng,
            "corn_acres":     corn_k * 1000,
            "wheat_acres":    wheat_k * 1000,
            "soy_acres":      soy_k  * 1000,
            "urea_mt":        urea_mt,
            "current_cost_m": cur_cost,
            "forecast_cost_m":fc_cost,
            "impact_m":       impact,
        })

    df = pd.DataFrame(rows)

    # Elevation: normalise urea_mt so the tallest state = 500 km
    max_mt        = df["urea_mt"].max()
    df["elevation"] = (df["urea_mt"] / max_mt) * 500_000

    # Heat color: green (low exposure) → yellow → red (high exposure)
    intensity        = df["urea_mt"] / max_mt          # 0-1
    df["color_r"]    = (intensity * 255).astype(int)
    df["color_g"]    = (255 - intensity * 200).clip(0, 255).astype(int)
    df["color_b"]    = 30
    df["color_a"]    = 210

    sign = "▲" if price_chg_pct >= 0 else "▼"
    df["tooltip"] = df.apply(lambda r: (
        f"<b>{r['state']}</b><br>"
        f"Urea needed: {r['urea_mt']/1000:,.0f}K mt/yr<br>"
        f"Current bill: ${r['current_cost_m']:.1f}M<br>"
        f"60-day forecast: ${r['forecast_cost_m']:.1f}M<br>"
        f"Impact: {sign}${abs(r['impact_m']):.1f}M ({price_chg_pct:+.1f}%)"
    ), axis=1)

    return df.sort_values("urea_mt", ascending=False)


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
df    = get_farmer_crops(email)
cache = load_cache()

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
tab_overview, tab_fertilizer, tab_map = st.tabs(["Overview", "Fertilizer Costs & Risk Assessment", "🌍 Regional Price Map"])


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

    if cache is None:
        st.warning(
            "No forecast data found. "
            "Run `python backend/run_pipeline.py` first to generate `data/processed/cache.json`."
        )
    else:
        sig  = cache["signal"]
        mc   = cache["monte_carlo"]
        fc   = cache["forecast"]
        meta = cache["model_metadata"]

        SIGNAL_COLORS = {
            "BUY_NOW":         "#ef4444",
            "CONSIDER_BUYING": "#f59e0b",
            "WAIT":            "#22c55e",
            "NEUTRAL":         "#6b7280",
        }
        color = SIGNAL_COLORS.get(sig["signal"], "#6b7280")

        # ── SECTION 1: BUY SIGNAL ─────────────────────────────────────────────
        st.subheader("📡 Buy Signal")

        m1, m2, m3, m4 = st.columns(4)
        pct_chg = (sig["forecast_t2"] - sig["currentPrice"]) / sig["currentPrice"] * 100
        with m1:
            st.metric("Current Urea Price", f"${sig['currentPrice']:.0f}/mt")
        with m2:
            st.metric("60-Day Forecast (t2)", f"${sig['forecast_t2']:.0f}/mt", delta=f"{pct_chg:+.1f}%")
        with m3:
            st.metric("Prob. Rising (60d)", f"{sig['prob_rising']*100:.0f}%")
        with m4:
            st.metric(
                "Nat Gas Spot", f"${sig['ng_current']:.2f}/MMBtu",
                delta=f"{sig['ng_change_30d']*100:+.1f}% (30d)"
            )

        st.markdown(f"""
        <div style="background:{color}22; border-left:4px solid {color}; padding:16px;
                    border-radius:6px; margin:12px 0 4px 0;">
            <span style="font-size:1.35rem; font-weight:bold; color:{color};">
                {sig['recommendation']}
            </span>
            &nbsp;&nbsp;
            <span style="color:#666; font-size:0.88rem;">
                Confidence: {sig['confidence']*100:.0f}%
                &nbsp;|&nbsp; {sig['key_driver']}
                &nbsp;|&nbsp; Best month: {sig['bestMonth']} (${sig['bestPrice']:.0f}/mt)
            </span>
            <br>
            <span style="color:#444; font-size:0.95rem; margin-top:8px; display:block;">
                {sig['rationale']}
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── SECTION 2: PRICE FORECAST CHART ───────────────────────────────────
        st.subheader("📈 Urea Price History + XGBoost Forecast")

        show_ng = st.toggle("Overlay Natural Gas prices (secondary axis)", value=False)

        hist_x  = cache["urea_history"]["labels"]
        hist_y  = cache["urea_history"]["values"]

        bridge_x    = [hist_x[-1]] + fc["labels"]
        bridge_mean = [hist_y[-1]] + fc["mean"]
        bridge_high = [hist_y[-1]] + fc["high"]
        bridge_low  = [hist_y[-1]] + fc["low"]

        fig_fc = go.Figure()

        fig_fc.add_trace(go.Scatter(
            x=bridge_x + bridge_x[::-1],
            y=bridge_high + bridge_low[::-1],
            fill="toself",
            fillcolor="rgba(239,68,68,0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            name="80% MC Band",
            hoverinfo="skip",
        ))
        fig_fc.add_trace(go.Scatter(
            x=hist_x, y=hist_y,
            name="Urea — Historical",
            line=dict(color="#2563eb", width=2),
            hovertemplate="$%{y:.0f}/mt<extra>Historical</extra>",
        ))
        fig_fc.add_trace(go.Scatter(
            x=bridge_x, y=bridge_mean,
            name="XGBoost Forecast",
            line=dict(color="#ef4444", width=2.5, dash="dash"),
            hovertemplate="$%{y:.0f}/mt<extra>Forecast (median)</extra>",
        ))
        fig_fc.add_trace(go.Scatter(
            x=fc["labels"], y=fc["mean"],
            mode="markers",
            marker=dict(color="#ef4444", size=9),
            showlegend=False,
            hoverinfo="skip",
        ))

        if show_ng:
            fig_fc.add_trace(go.Scatter(
                x=cache["natgas_history"]["labels"],
                y=cache["natgas_history"]["values"],
                name="Nat Gas ($/MMBtu)",
                line=dict(color="#16a34a", width=1.5),
                yaxis="y2",
                hovertemplate="$%{y:.2f}/MMBtu<extra>Nat Gas</extra>",
            ))
            fig_fc.update_layout(yaxis2=dict(
                title="Nat Gas ($/MMBtu)",
                overlaying="y", side="right",
                showgrid=False, tickfont=dict(color="#16a34a"),
            ))

        fig_fc.update_layout(
            xaxis_title="Month",
            yaxis_title="Urea Price ($/mt)",
            legend=dict(orientation="h", y=1.08, x=0),
            plot_bgcolor="#f9fbf9",
            paper_bgcolor="white",
            font=dict(color="#333"),
            hovermode="x unified",
            height=430,
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(fig_fc, use_container_width=True)
        st.caption(
            f"As-of: {cache.get('as_of_date', 'N/A')}. "
            "Shaded region = 80% Monte Carlo confidence band (p10–p90, 10,000 simulated paths). "
            f"Generated: {cache.get('generated_at', 'N/A')[:10]}."
        )

        st.divider()

        # ── SECTION 3: MONTE CARLO DISTRIBUTION ───────────────────────────────
        st.subheader("🎲 Monte Carlo Price Distribution — 60-Day Horizon")
        st.markdown(
            "Each bar represents how often a simulated price landed in that range across "
            "**10,000 paths**. Draws are taken from the XGBoost residual distribution "
            "captured during walk-forward cross-validation."
        )

        fig_mc = go.Figure()
        fig_mc.add_trace(go.Histogram(
            x=cache["sim_t2_distribution"],
            nbinsx=60,
            marker_color="#2563eb",
            opacity=0.75,
            name="Simulated Prices",
        ))
        for label, val, clr in [
            ("P10 (Optimistic)",  mc["p10_t2"], "#16a34a"),
            ("P50 (Median)",      mc["p50_t2"], "#f59e0b"),
            ("P90 (Pessimistic)", mc["p90_t2"], "#ef4444"),
        ]:
            fig_mc.add_vline(
                x=val, line_color=clr, line_width=2, line_dash="dot",
                annotation_text=f" {label}: ${val:.0f}",
                annotation_font_color=clr,
                annotation_position="top right",
            )
        fig_mc.update_layout(
            xaxis_title="Simulated Urea Price ($/mt) at t+2 months",
            yaxis_title="Frequency (paths)",
            plot_bgcolor="#f9fbf9",
            paper_bgcolor="white",
            font=dict(color="#333"),
            height=320,
            showlegend=False,
            margin=dict(t=30, b=40),
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        mc_c1, mc_c2, mc_c3, mc_c4 = st.columns(4)
        mc_c1.metric("P10 — Optimistic",  f"${mc['p10_t2']:.0f}/mt")
        mc_c2.metric("P50 — Median",      f"${mc['p50_t2']:.0f}/mt")
        mc_c3.metric("P90 — Pessimistic", f"${mc['p90_t2']:.0f}/mt")
        mc_c4.metric("Prob. >10% Rise",   f"{mc['prob_10pct_increase_t2']*100:.0f}%")

        st.divider()

        # ── SECTION 4: EXPOSURE CALCULATOR ────────────────────────────────────
        st.subheader("🧮 Fertilizer Cost Exposure Calculator")
        st.markdown(
            "Enter your farm details to project input costs at each forecast horizon "
            "using the XGBoost price forecast and Monte Carlo uncertainty bands."
        )

        # Pre-populate acreage from user's farm DB if available
        default_acres = float(df["acres"].sum()) if not df.empty else 500.0

        calc_c1, calc_c2 = st.columns(2)
        with calc_c1:
            calc_crop  = st.selectbox("Crop Type", list(N_INTENSITY_LBS_PER_ACRE.keys()), key="calc_crop")
            calc_acres = st.number_input("Acreage", min_value=1.0, value=default_acres, step=50.0, key="calc_acres")
        with calc_c2:
            pre_pct = st.slider("Already pre-purchased (%)", 0, 100, 0, key="pre_pct")
            n_int   = N_INTENSITY_LBS_PER_ACRE[calc_crop]
            total_urea_mt = calc_acres * n_int / (UREA_N_CONTENT * LBS_PER_MT)
            st.info(
                f"**{calc_crop}** → {n_int} lbs N/acre  \n"
                f"Total N needed: **{calc_acres * n_int:,.0f} lbs**  \n"
                f"Urea needed (46% N): **{total_urea_mt:.1f} mt**"
            )

        remaining_mt  = total_urea_mt * (1 - pre_pct / 100)
        cur           = sig["currentPrice"]
        cost_now      = remaining_mt * cur

        cost_rows = []
        for label, mean, low, high in zip(fc["labels"], fc["mean"], fc["low"], fc["high"]):
            cost_rows.append({
                "Month":                 label,
                "Forecast Price ($/mt)": f"${mean:.0f}",
                "P10 — Low ($/mt)":      f"${low:.0f}",
                "P90 — High ($/mt)":     f"${high:.0f}",
                "Your Cost — Expected":  f"${remaining_mt * mean:,.0f}",
                "Your Cost — Low":       f"${remaining_mt * low:,.0f}",
                "Your Cost — High":      f"${remaining_mt * high:,.0f}",
            })

        st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)
        st.caption(
            f"{calc_acres:.0f} ac × {n_int} lbs N/ac ÷ (0.46 × 2204.6) = {total_urea_mt:.1f} mt total.  "
            f"{pre_pct}% pre-purchased → **{remaining_mt:.1f} mt remaining to buy.**"
        )

        st.divider()

        # ── SECTION 4b: PRE-PURCHASE OPTIMIZER (CVaR) ─────────────────────────
        st.subheader("🎯 Pre-Purchase Optimizer")
        st.markdown(
            "Computes the statistically **optimal fraction to buy now vs. wait** "
            "given your planting timeline and risk tolerance — minimising expected cost "
            "while controlling downside exposure via CVaR."
        )

        opt_c1, opt_c2 = st.columns(2)
        with opt_c1:
            months_to_plant = st.slider(
                "Months until planting / purchase deadline",
                min_value=1, max_value=3, value=2, key="months_to_plant",
            )
        with opt_c2:
            risk_label = st.radio(
                "Risk tolerance",
                ["Conservative", "Balanced", "Aggressive"],
                index=1, horizontal=True, key="risk_tol",
            )

        horizon_key = {1: "t1", 2: "t2", 3: "t3"}[months_to_plant]
        p50_h = mc[f"p50_{horizon_key}"]
        std_h = meta[f"residual_std_{horizon_key}"]

        rng      = np.random.default_rng(seed=42)
        mc_paths = rng.normal(loc=p50_h, scale=std_h, size=10_000).clip(50, 2000)

        alpha_map = {"Conservative": 0.75, "Balanced": 0.45, "Aggressive": 0.15}
        alpha     = alpha_map[risk_label]

        f_grid   = np.linspace(0, 1, 201)
        obj_vals = []
        for f in f_grid:
            costs = remaining_mt * (f * cur + (1 - f) * mc_paths)
            obj_vals.append((1 - alpha) * costs.mean() + alpha * np.percentile(costs, 90))

        f_star  = float(f_grid[np.argmin(obj_vals)])
        mt_now  = remaining_mt * f_star
        mt_wait = remaining_mt * (1 - f_star)

        def _cost_stats(paths):
            return paths.mean(), np.percentile(paths, 10), np.percentile(paths, 90)

        c_all_now  = np.full(10_000, remaining_mt * cur)
        c_all_wait = remaining_mt * mc_paths
        c_optimal  = remaining_mt * (f_star * cur + (1 - f_star) * mc_paths)

        exp_now,  p10_now,  p90_now  = _cost_stats(c_all_now)
        exp_wait, p10_wait, p90_wait = _cost_stats(c_all_wait)
        exp_opt,  p10_opt,  p90_opt  = _cost_stats(c_optimal)

        pct_now      = round(f_star * 100)
        pct_wait     = 100 - pct_now
        save_vs_wait = exp_wait - exp_opt
        save_sign    = "save" if save_vs_wait >= 0 else "costs"

        rec_color = "#16a34a" if pct_now >= 60 else ("#f59e0b" if pct_now >= 30 else "#2563eb")
        st.markdown(
            f"<div style='border:2px solid {rec_color};border-radius:12px;"
            f"padding:16px 20px;background:{rec_color}18;margin-bottom:12px;'>"
            f"<span style='font-size:1.05rem;font-weight:700;color:{rec_color};'>"
            f"Optimal split: Buy {pct_now}% now · Wait on {pct_wait}%</span><br>"
            f"<span style='color:#555;font-size:0.85rem;'>"
            f"Lock in <b style='color:#111;'>{mt_now:.1f} mt</b> at today's "
            f"<b style='color:#111;'>${cur:,.0f}/mt</b> — "
            f"defer <b style='color:#111;'>{mt_wait:.1f} mt</b> until closer to planting.  "
            f"Expected to <b style='color:#111;'>{save_sign} ${abs(save_vs_wait):,.0f}</b> "
            f"vs. waiting entirely.</span></div>",
            unsafe_allow_html=True,
        )

        oc1, oc2, oc3 = st.columns(3)
        for col, label, exp, p10, p90, is_opt in [
            (oc1, "Buy All Now",                exp_now,  p10_now,  p90_now,  False),
            (oc2, f"Optimal ({pct_now}% now)",  exp_opt,  p10_opt,  p90_opt,  True),
            (oc3, "Wait Entirely",              exp_wait, p10_wait, p90_wait, False),
        ]:
            border = "#f59e0b" if is_opt else "#d1d5db"
            bg     = "rgba(245,158,11,0.07)" if is_opt else "#f9fbf9"
            badge  = "★ RECOMMENDED" if is_opt else ""
            with col:
                st.markdown(
                    f"<div style='border:2px solid {border};border-radius:10px;"
                    f"padding:14px 16px;background:{bg};min-height:175px;'>"
                    f"<div style='font-size:0.9rem;font-weight:700;color:#111;'>{label}</div>"
                    + (f"<div style='font-size:0.68rem;font-weight:700;color:#f59e0b;"
                       f"margin-bottom:6px;'>{badge}</div>" if badge else
                       "<div style='margin-bottom:20px;'></div>")
                    + f"<div style='font-size:1.45rem;font-weight:800;color:#111;'>${exp:,.0f}</div>"
                    f"<div style='font-size:0.73rem;color:#64748b;'>expected total cost</div>"
                    f"<hr style='border:none;border-top:1px solid #e5e7eb;margin:10px 0;'>"
                    f"<div style='font-size:0.76rem;color:#64748b;'>"
                    f"P10  <span style='color:#16a34a;'>${p10:,.0f}</span> · "
                    f"P90  <span style='color:#ef4444;'>${p90:,.0f}</span></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        fig_opt = go.Figure()
        fig_opt.add_trace(go.Scatter(
            x=f_grid * 100, y=obj_vals,
            mode="lines", line=dict(color="#2563eb", width=2),
            name="Objective",
        ))
        fig_opt.add_vline(
            x=f_star * 100, line_color="#f59e0b", line_width=2, line_dash="dash",
            annotation_text=f" Optimal: {pct_now}%",
            annotation_font_color="#f59e0b",
        )
        fig_opt.update_layout(
            xaxis_title="Fraction purchased now (%)",
            yaxis_title=f"({1-alpha:.0%}) · E[cost]  +  ({alpha:.0%}) · CVaR₉₀",
            plot_bgcolor="#f9fbf9", paper_bgcolor="white",
            font=dict(color="#333"), height=260,
            margin=dict(t=20, b=40, l=60, r=20),
            showlegend=False,
        )
        st.plotly_chart(fig_opt, use_container_width=True)
        st.caption(
            f"Objective minimised at **{pct_now}%** · "
            f"Risk tolerance: {risk_label} (α = {alpha}) · "
            f"Horizon: {months_to_plant}-month MC forecast (residual σ = ${std_h:.0f}/mt)"
        )

        st.divider()

        # ── SECTION 5: TIMING DECISION CARDS ──────────────────────────────────
        st.subheader("⚖️ Timing Decision: Buy Now vs. Wait")
        st.markdown(
            "Side-by-side cost comparison for each timing option using your farm inputs "
            f"above. Costs shown for your **remaining {remaining_mt:.1f} mt** to purchase."
        )

        def _prob_rising(p50, std):
            if std <= 0:
                return 1.0 if p50 > cur else 0.0
            return float(1 - _norm.cdf(cur, loc=p50, scale=std))

        scenarios = [
            {
                "label":    "Buy Now",
                "sublabel": "Lock in today's spot price",
                "p10": cur, "p50": cur, "p90": cur,
                "prob_rising": None,
            },
            {
                "label":    "Wait 30 Days",
                "sublabel": fc["labels"][0],
                "p10": mc["p10_t1"], "p50": mc["p50_t1"], "p90": mc["p90_t1"],
                "prob_rising": _prob_rising(mc["p50_t1"], meta["residual_std_t1"]),
            },
            {
                "label":    "Wait 60 Days",
                "sublabel": fc["labels"][1],
                "p10": mc["p10_t2"], "p50": mc["p50_t2"], "p90": mc["p90_t2"],
                "prob_rising": mc["prob_rising_t2"],
            },
        ]

        sc1, sc2, sc3 = st.columns(3)
        for col, s in zip([sc1, sc2, sc3], scenarios):
            p10, p50, p90 = s["p10"], s["p50"], s["p90"]
            c_p50         = remaining_mt * p50
            c_p10         = remaining_mt * p10
            c_p90         = remaining_mt * p90
            delta         = c_p50 - cost_now
            delta_pct     = (delta / cost_now * 100) if cost_now > 0 else 0
            is_baseline   = s["prob_rising"] is None
            prob_save_pct = 0.0 if is_baseline else (1 - s["prob_rising"]) * 100

            price_str      = f"${p50:,.0f} /mt"
            range_str      = "Fixed — no price risk" if is_baseline else f"P10  ${p10:,.0f}  –  P90  ${p90:,.0f} /mt"
            cost_str       = f"${c_p50:,.0f}"
            cost_range_str = f"${c_p10:,.0f} – ${c_p90:,.0f}"
            delta_str      = "No price risk — cost locked in" if is_baseline else f"vs Buy Now:  {delta:+,.0f}  ({delta_pct:+.1f}%)"
            prob_str       = "&nbsp;" if is_baseline else f"Prob cheaper than now:  {prob_save_pct:.0f}%"

            if is_baseline:
                border = "#2563eb"; bg = "rgba(37,99,235,0.07)"; b_col = "#2563eb"; badge = "BASELINE"
            elif p50 < cur:
                border = "#16a34a"; bg = "rgba(22,163,74,0.07)"; b_col = "#16a34a"
                badge  = f"SAVE {abs(delta_pct):.1f}%"
            else:
                pct_up = s["prob_rising"] * 100
                if pct_up < 70:
                    border = "#f59e0b"; bg = "rgba(245,158,11,0.07)"; b_col = "#f59e0b"
                else:
                    border = "#ef4444"; bg = "rgba(239,68,68,0.07)";  b_col = "#ef4444"
                badge = f"{pct_up:.0f}% CHANCE HIGHER"

            delta_col = "#64748b" if is_baseline else ("#16a34a" if delta <= 0 else "#ef4444")
            prob_col  = "#16a34a" if prob_save_pct >= 50 else "#f59e0b"

            with col:
                st.markdown(
                    f"<div style='border:2px solid {border};border-radius:12px;"
                    f"padding:18px 16px;background:{bg};min-height:300px;"
                    f"display:flex;flex-direction:column;'>"
                    f"<div style='font-size:1.0rem;font-weight:700;color:#111;'>{s['label']}</div>"
                    f"<div style='font-size:0.75rem;color:#64748b;margin-bottom:6px;'>{s['sublabel']}</div>"
                    f"<span style='background:{b_col}22;color:{b_col};font-size:0.68rem;"
                    f"font-weight:700;padding:3px 9px;border-radius:20px;'>{badge}</span>"
                    f"<div style='margin-top:14px;font-size:1.9rem;font-weight:800;"
                    f"color:#111;line-height:1.1;'>{price_str}</div>"
                    f"<div style='font-size:0.76rem;color:#64748b;margin-bottom:12px;'>{range_str}</div>"
                    f"<hr style='border:none;border-top:1px solid #e5e7eb;margin:12px 0;'>"
                    f"<div style='font-size:0.7rem;color:#64748b;text-transform:uppercase;"
                    f"letter-spacing:0.05em;'>Your cost (expected)</div>"
                    f"<div style='font-size:1.5rem;font-weight:700;color:#111;margin:2px 0;'>{cost_str}</div>"
                    f"<div style='font-size:0.76rem;color:#475569;margin-bottom:10px;'>"
                    f"Range: {cost_range_str}</div>"
                    f"<div style='font-size:0.82rem;color:{delta_col};font-weight:600;'>{delta_str}</div>"
                    f"<div style='font-size:0.82rem;color:{prob_col};margin-top:4px;'>{prob_str}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.caption(
            "Prices from Monte Carlo simulation (10,000 paths).  "
            "P10 = optimistic, P50 = median, P90 = pessimistic.  "
            "Probability uses a normal approximation over test-period residuals."
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — REGIONAL PRICE MAP
# 3-D globe / ColumnLayer — fertilizer cost exposure by US state
# ════════════════════════════════════════════════════════════════════════════
with tab_map:

    if cache is None:
        st.warning("No forecast data found. Run `python backend/run_pipeline.py` first.")
    else:
        sig_map  = cache["signal"]
        cur_p    = sig_map["currentPrice"]
        fc_p     = sig_map["forecast_t2"]
        chg_pct  = (fc_p - cur_p) / cur_p * 100
        chg_sign = "▲" if chg_pct >= 0 else "▼"

        # ── Header metrics ─────────────────────────────────────────────────
        st.subheader("🌍 Regional Fertilizer Cost Exposure")
        st.markdown(
            "Each spike shows **how much urea a state needs annually** based on USDA planted "
            "acres (corn · wheat · soy). Height = total exposure. Color = cost intensity. "
            "Drag to rotate · scroll to zoom · hover for details."
        )

        hm1, hm2, hm3 = st.columns(3)
        hm1.metric("Current Urea", f"${cur_p:.0f}/mt")
        hm2.metric("60-Day Forecast", f"${fc_p:.0f}/mt", delta=f"{chg_pct:+.1f}%")
        hm3.metric("Signal", sig_map["signal"])

        # ── Build state dataset ────────────────────────────────────────────
        state_df = build_state_df(cache)

        # ── View controls ──────────────────────────────────────────────────
        vc1, vc2 = st.columns([2, 2])
        with vc1:
            view_mode = st.radio(
                "View mode",
                ["🌐 3-D Perspective", "🗺️ Flat map (top-down)"],
                horizontal=True,
                key="map_view_mode",
            )
        with vc2:
            color_metric = st.radio(
                "Color / height by",
                ["Fertilizer exposure (urea MT)", "60-day cost impact ($M)"],
                horizontal=True,
                key="map_color_metric",
            )

        # Recompute elevation & color if user chooses cost-impact mode
        if "cost impact" in color_metric:
            max_val          = state_df["impact_m"].abs().max()
            norm             = (state_df["impact_m"].abs() / max_val).clip(0, 1)
            state_df["elevation"] = (norm * 500_000).clip(1000)
            state_df["color_r"]   = (norm * 255).astype(int)
            state_df["color_g"]   = (255 - norm * 200).clip(0, 255).astype(int)
            state_df["color_b"]   = 30
            state_df["color_a"]   = 210

        layer = pdk.Layer(
            "ColumnLayer",
            data=state_df,
            get_position="[lng, lat]",
            get_elevation="elevation",
            elevation_scale=1,
            radius=55000,
            get_fill_color="[color_r, color_g, color_b, color_a]",
            pickable=True,
            auto_highlight=True,
            coverage=0.85,
        )

        if "3-D" in view_mode:
            view = pdk.ViewState(
                longitude=-96,
                latitude=36,
                zoom=3.2,
                pitch=55,
                bearing=-10,
            )
        else:
            view = pdk.ViewState(
                longitude=-96,
                latitude=39,
                zoom=3.6,
                pitch=0,
                bearing=0,
            )

        # CARTO dark-matter style — free, no Mapbox token required
        DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            map_style=DARK_STYLE,
            tooltip={
                "html": "{tooltip}",
                "style": {
                    "backgroundColor": "#0f172a",
                    "color": "#f1f5f9",
                    "fontSize": "13px",
                    "padding": "10px 14px",
                    "borderRadius": "8px",
                    "border": "1px solid #334155",
                },
            },
        )

        st.pydeck_chart(deck, use_container_width=True, height=600)

        # ── Color legend ───────────────────────────────────────────────────
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
            <span style="font-size:0.8rem;color:#64748b;">Low exposure</span>
            <div style="height:12px;width:200px;background:linear-gradient(to right,
                #1e7b1e, #b8a010, #ff1e1e);border-radius:4px;"></div>
            <span style="font-size:0.8rem;color:#64748b;">High exposure</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── State rankings table ───────────────────────────────────────────
        st.subheader("State Rankings — Fertilizer Exposure")
        table_df = state_df[[
            "state", "corn_acres", "wheat_acres", "soy_acres",
            "urea_mt", "current_cost_m", "forecast_cost_m", "impact_m",
        ]].copy()
        table_df["urea_mt"]          = table_df["urea_mt"].apply(lambda x: f"{x/1000:,.0f}K mt")
        table_df["current_cost_m"]   = table_df["current_cost_m"].apply(lambda x: f"${x:.1f}M")
        table_df["forecast_cost_m"]  = table_df["forecast_cost_m"].apply(lambda x: f"${x:.1f}M")
        table_df["impact_m"]         = table_df["impact_m"].apply(lambda x: f"{chg_sign}${abs(x):.1f}M")
        table_df["corn_acres"]       = table_df["corn_acres"].apply(lambda x: f"{x/1e6:.1f}M ac" if x >= 1e6 else f"{x/1e3:.0f}K ac")
        table_df["wheat_acres"]      = table_df["wheat_acres"].apply(lambda x: f"{x/1e6:.1f}M ac" if x >= 1e6 else f"{x/1e3:.0f}K ac")
        table_df["soy_acres"]        = table_df["soy_acres"].apply(lambda x: f"{x/1e6:.1f}M ac" if x >= 1e6 else f"{x/1e3:.0f}K ac")
        table_df.columns = [
            "State", "Corn", "Wheat", "Soybeans",
            "Urea Needed", "Current Cost", "60-Day Forecast", f"Impact ({chg_sign})",
        ]
        st.dataframe(table_df, use_container_width=True, hide_index=True)
        st.caption(
            f"USDA 2023 planted acres. Urea = total N ÷ (46% N content).  "
            f"Current price: ${cur_p:.0f}/mt → 60-day forecast: ${fc_p:.0f}/mt ({chg_pct:+.1f}%)."
        )
