import streamlit as st
import pandas as pd
import numpy as np
import joblib
import json
import plotly.express as px
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from scipy.stats import norm as _norm

# --- CONFIGURATION ---
st.set_page_config(page_title="AgriSignal Pro", page_icon="🌾", layout="wide")

st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #E85D04; }
    .alert-box { padding: 20px; background-color: #ffcccc; border-radius: 10px;
                 color: #cc0000; font-weight: bold; margin-bottom: 10px; }
    .success-box { padding: 20px; background-color: #ccffcc; border-radius: 10px;
                   color: #006600; font-weight: bold; }

    /* ── Collapse Streamlit's own toolbar so it doesn't compete ── */
    header[data-testid="stHeader"] {
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    /* ── Fixed app header (title + subtitle) ── */
    .app-header {
        position: fixed;
        top: 0;
        left: 21rem;
        right: 0;
        z-index: 1000;
        background-color: #0e1117;
        padding: 0.7rem 2rem 0.55rem 2rem;
        border-bottom: 1px solid #21262d;
    }
    .app-header h1 {
        margin: 0;
        padding: 0;
        font-size: 1.8rem;
        line-height: 1.2;
    }
    .app-header p {
        margin: 0.15rem 0 0 0;
        color: #888;
        font-size: 0.9rem;
    }

    /* ── Fixed tab bar, pinned just below the app-header ── */
    [data-baseweb="tab-list"] {
        position: fixed !important;
        top: 4.6rem !important;
        left: 21rem !important;
        right: 0 !important;
        z-index: 999 !important;
        background-color: #0e1117 !important;
        border-bottom: 1px solid #21262d;
        padding: 4px 2rem 4px 2rem !important;
    }

    /* ── Push page content down so it starts below both fixed bars ── */
    div[data-testid="stMainBlockContainer"] {
        padding-top: 8rem !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <h1>🌾 AgriSignal Pro: Risk Mitigation Engine</h1>
    <p>Automated Farm Loan Portfolio Monitoring &amp; Proactive Hedging</p>
</div>
""", unsafe_allow_html=True)

# --- CONSTANTS (nitrogen intensity per crop, matching server.js) ---
N_INTENSITY_LBS_PER_ACRE = {
    "Corn": 150, "Wheat": 90, "Cotton": 120,
    "Sorghum": 80, "Soybeans": 60, "Hay": 50,
}
UREA_N_CONTENT = 0.46     # urea is 46% nitrogen by weight
LBS_PER_MT     = 2204.6   # pounds per metric ton

# Maps synthetic dataset crop names to N_INTENSITY keys
CROP_NAME_MAP = {
    "Maize": "Corn", "Wheat": "Wheat", "Cotton": "Cotton",
    "Soybean": "Soybeans", "Tomato": None,
}

# --- DATA LOADERS ---
@st.cache_resource
def load_ml_model():
    try:
        return joblib.load('data/models/farm_risk_model.joblib')
    except Exception as e:
        st.error(f"🚨 Model not found! Run `python backend/training_and_eval.py` first. Error: {e}")
        return None

@st.cache_data(ttl=3600)
def load_cache():
    try:
        with open('data/processed/cache.json') as f:
            return json.load(f)
    except Exception:
        return None

@st.cache_data
def load_portfolio_data():
    try:
        return pd.read_csv('data/agriculture-and-farming-dataset/synthetic_farm_borrowers.csv')
    except Exception:
        return pd.DataFrame()

model = load_ml_model()
cache = load_cache()
df    = load_portfolio_data()

# --- EMAIL ALERT FUNCTION ---
def send_risk_alert(recipient_email, borrower_data, probability, action):
    SENDER_EMAIL = "your_burner_email@gmail.com"
    APP_PASSWORD  = "your_16_character_app_password"

    msg = MIMEMultipart()
    msg['From']    = SENDER_EMAIL
    msg['To']      = recipient_email
    msg['Subject'] = "🚨 AgriSignal Alert: High Risk Farm Detected"

    body = f"""
    AgriSignal Risk Mitigation Engine has flagged a portfolio account.

    Borrower Metrics:
    - Crop Focus: {borrower_data['Crop_Type']}
    - Farm Size: {borrower_data['Farm_Area_Acres']} Acres
    - Irrigation Type: {borrower_data['Irrigation_Type']}
    - Soil Type: {borrower_data['Soil_Type']}
    - Season: {borrower_data['Season']}
    - Est. Fertilizer Need: {borrower_data['Fertilizer_Used_Tons']} Tons
    - Current LTV Ratio: {borrower_data['Current_LTV_Ratio']}
    - Months Since Delinquency: {borrower_data['Months_Since_Delinquency']}

    Risk Assessment:
    - Stress Probability: {probability * 100:.1f}%

    Automated Recommendation: {action}

    Log into the AgriSignal portal to review this account immediately.
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("🏦 Loan Officer Portal")
    st.markdown("Log in to receive automated portfolio alerts.")
    officer_email = st.text_input("Officer Email Address", placeholder="loan.officer@bank.com")
    if officer_email:
        st.success(f"Logged in as: {officer_email}")

    if cache:
        st.divider()
        st.markdown("**Last pipeline run**")
        st.caption(cache.get("generated_at", "N/A")[:19].replace("T", " ") + " UTC")
        sig = cache["signal"]
        st.markdown(f"**Signal:** `{sig['signal']}`")
        st.markdown(f"**As-of date:** {cache.get('as_of_date', 'N/A')}")

# ==============================================================================
#  TABS
# ==============================================================================
tab1, tab2 = st.tabs(["🌽  Market Intelligence", "🏦  Portfolio Risk"])


# ==============================================================================
#  TAB 1 — MARKET INTELLIGENCE
#  XGBoost price forecast + Monte Carlo simulation + signal engine
# ==============================================================================
with tab1:
    if cache is None:
        st.warning(
            "No forecast data found. "
            "Run `python backend/run_pipeline.py` first to generate `data/processed/cache.json`."
        )
        st.stop()

    sig = cache["signal"]
    mc  = cache["monte_carlo"]
    fc  = cache["forecast"]

    SIGNAL_COLORS = {
        "BUY_NOW":         "#ef4444",
        "CONSIDER_BUYING": "#f59e0b",
        "WAIT":            "#22c55e",
        "NEUTRAL":         "#6b7280",
    }
    color = SIGNAL_COLORS.get(sig["signal"], "#6b7280")

    # ── SECTION 1: BUY SIGNAL ─────────────────────────────────────────────────
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
        <span style="color:#aaa; font-size:0.88rem;">
            Confidence: {sig['confidence']*100:.0f}%
            &nbsp;|&nbsp; {sig['key_driver']}
            &nbsp;|&nbsp; Best month: {sig['bestMonth']} (${sig['bestPrice']:.0f}/mt)
        </span>
        <br>
        <span style="color:#cbd5e1; font-size:0.95rem; margin-top:8px; display:block;">
            {sig['rationale']}
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── SECTION 2: PRICE FORECAST CHART ───────────────────────────────────────
    st.subheader("📈 Urea Price History + XGBoost Forecast")

    show_ng = st.toggle("Overlay Natural Gas prices (secondary axis)", value=False)

    hist_x  = cache["urea_history"]["labels"]
    hist_y  = cache["urea_history"]["values"]

    # Bridge last historical point so lines connect
    bridge_x    = [hist_x[-1]] + fc["labels"]
    bridge_mean = [hist_y[-1]] + fc["mean"]
    bridge_high = [hist_y[-1]] + fc["high"]
    bridge_low  = [hist_y[-1]] + fc["low"]

    fig = go.Figure()

    # 80% Monte Carlo confidence band (filled)
    fig.add_trace(go.Scatter(
        x=bridge_x + bridge_x[::-1],
        y=bridge_high + bridge_low[::-1],
        fill="toself",
        fillcolor="rgba(239,68,68,0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        name="80% MC Band",
        hoverinfo="skip",
    ))

    # Historical urea prices
    fig.add_trace(go.Scatter(
        x=hist_x, y=hist_y,
        name="Urea — Historical",
        line=dict(color="#60a5fa", width=2),
        hovertemplate="$%{y:.0f}/mt<extra>Historical</extra>",
    ))

    # XGBoost forecast (dashed)
    fig.add_trace(go.Scatter(
        x=bridge_x, y=bridge_mean,
        name="XGBoost Forecast",
        line=dict(color="#ef4444", width=2.5, dash="dash"),
        hovertemplate="$%{y:.0f}/mt<extra>Forecast (median)</extra>",
    ))

    # Forecast point markers
    fig.add_trace(go.Scatter(
        x=fc["labels"], y=fc["mean"],
        mode="markers",
        marker=dict(color="#ef4444", size=9),
        showlegend=False,
        hoverinfo="skip",
    ))

    if show_ng:
        fig.add_trace(go.Scatter(
            x=cache["natgas_history"]["labels"],
            y=cache["natgas_history"]["values"],
            name="Nat Gas ($/MMBtu)",
            line=dict(color="#a3e635", width=1.5),
            yaxis="y2",
            hovertemplate="$%{y:.2f}/MMBtu<extra>Nat Gas</extra>",
        ))
        fig.update_layout(yaxis2=dict(
            title="Nat Gas ($/MMBtu)",
            overlaying="y", side="right",
            showgrid=False, tickfont=dict(color="#a3e635"),
        ))

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Urea Price ($/mt)",
        legend=dict(orientation="h", y=1.08, x=0),
        plot_bgcolor="#0b1120",
        paper_bgcolor="#0b1120",
        font=dict(color="#e2e8f0"),
        hovermode="x unified",
        height=430,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"As-of: {cache.get('as_of_date', 'N/A')}. "
        "Shaded region = 80% Monte Carlo confidence band (p10–p90, 10,000 simulated paths). "
        f"Generated: {cache.get('generated_at', 'N/A')[:10]}."
    )

    st.divider()

    # ── SECTION 3: MONTE CARLO DISTRIBUTION ───────────────────────────────────
    st.subheader("🎲 Monte Carlo Price Distribution — 60-Day Horizon")
    st.markdown(
        "Each bar represents how often a simulated price landed in that range across "
        "**10,000 paths**. Draws are taken from the XGBoost residual distribution "
        "captured during walk-forward cross-validation."
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Histogram(
        x=cache["sim_t2_distribution"],
        nbinsx=60,
        marker_color="#60a5fa",
        opacity=0.75,
        name="Simulated Prices",
    ))
    for label, val, clr in [
        ("P10 (Optimistic)",  mc["p10_t2"], "#22c55e"),
        ("P50 (Median)",      mc["p50_t2"], "#f59e0b"),
        ("P90 (Pessimistic)", mc["p90_t2"], "#ef4444"),
    ]:
        fig2.add_vline(
            x=val, line_color=clr, line_width=2, line_dash="dot",
            annotation_text=f" {label}: ${val:.0f}",
            annotation_font_color=clr,
            annotation_position="top right",
        )
    fig2.update_layout(
        xaxis_title="Simulated Urea Price ($/mt) at t+2 months",
        yaxis_title="Frequency (paths)",
        plot_bgcolor="#0b1120",
        paper_bgcolor="#0b1120",
        font=dict(color="#e2e8f0"),
        height=320,
        showlegend=False,
        margin=dict(t=30, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)

    mc_c1, mc_c2, mc_c3, mc_c4 = st.columns(4)
    mc_c1.metric("P10 — Optimistic",    f"${mc['p10_t2']:.0f}/mt")
    mc_c2.metric("P50 — Median",        f"${mc['p50_t2']:.0f}/mt")
    mc_c3.metric("P90 — Pessimistic",   f"${mc['p90_t2']:.0f}/mt")
    mc_c4.metric("Prob. >10% Rise",     f"{mc['prob_10pct_increase_t2']*100:.0f}%")

    st.divider()

    # ── SECTION 4: EXPOSURE CALCULATOR ────────────────────────────────────────
    st.subheader("🧮 Fertilizer Cost Exposure Calculator")
    st.markdown(
        "Enter your farm details to project input costs at each forecast horizon "
        "using the XGBoost price forecast and Monte Carlo uncertainty bands."
    )

    calc_c1, calc_c2 = st.columns(2)
    with calc_c1:
        calc_crop  = st.selectbox("Crop Type", list(N_INTENSITY_LBS_PER_ACRE.keys()), key="calc_crop")
        calc_acres = st.number_input("Acreage", min_value=1.0, value=500.0, step=50.0, key="calc_acres")
    with calc_c2:
        pre_pct = st.slider("Already pre-purchased (%)", 0, 100, 0, key="pre_pct")
        n_int   = N_INTENSITY_LBS_PER_ACRE[calc_crop]
        total_urea_mt = calc_acres * n_int / (UREA_N_CONTENT * LBS_PER_MT)
        st.info(
            f"**{calc_crop}** → {n_int} lbs N/acre  \n"
            f"Total N needed: **{calc_acres * n_int:,.0f} lbs**  \n"
            f"Urea needed (46% N): **{total_urea_mt:.1f} mt**"
        )

    remaining_mt = total_urea_mt * (1 - pre_pct / 100)

    cost_rows = []
    for label, mean, low, high in zip(fc["labels"], fc["mean"], fc["low"], fc["high"]):
        cost_rows.append({
            "Month":                     label,
            "Forecast Price ($/mt)":     f"${mean:.0f}",
            "P10 — Low ($/mt)":          f"${low:.0f}",
            "P90 — High ($/mt)":         f"${high:.0f}",
            "Your Cost — Expected":      f"${remaining_mt * mean:,.0f}",
            "Your Cost — Low":           f"${remaining_mt * low:,.0f}",
            "Your Cost — High":          f"${remaining_mt * high:,.0f}",
        })

    st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)
    st.caption(
        f"{calc_acres:.0f} ac × {n_int} lbs N/ac ÷ (0.46 × 2204.6) = {total_urea_mt:.1f} mt total.  "
        f"{pre_pct}% pre-purchased → **{remaining_mt:.1f} mt remaining to buy.**"
    )

    st.divider()

    # ── SECTION 4b: PRE-PURCHASE OPTIMIZER ────────────────────────────────────
    meta = cache["model_metadata"]
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

    # Map horizon
    horizon_key = {1: "t1", 2: "t2", 3: "t3"}[months_to_plant]
    p50_h = mc[f"p50_{horizon_key}"]
    std_h = meta[f"residual_std_{horizon_key}"]
    cur   = sig["currentPrice"]

    # 10 000 MC paths for the chosen horizon
    rng       = np.random.default_rng(seed=42)
    mc_paths  = rng.normal(loc=p50_h, scale=std_h, size=10_000).clip(50, 2000)

    # Objective = (1-α)·E[cost] + α·CVaR₉₀[cost]  — convex in f, grid-search is exact
    alpha_map = {"Conservative": 0.75, "Balanced": 0.45, "Aggressive": 0.15}
    alpha     = alpha_map[risk_label]

    f_grid    = np.linspace(0, 1, 201)
    obj_vals  = []
    for f in f_grid:
        costs  = remaining_mt * (f * cur + (1 - f) * mc_paths)
        obj_vals.append((1 - alpha) * costs.mean() + alpha * np.percentile(costs, 90))

    f_star  = float(f_grid[np.argmin(obj_vals)])
    mt_now  = remaining_mt * f_star
    mt_wait = remaining_mt * (1 - f_star)

    # Cost breakdown for three strategies
    def _cost_stats(paths):
        return paths.mean(), np.percentile(paths, 10), np.percentile(paths, 90)

    c_all_now   = np.full(10_000, remaining_mt * cur)
    c_all_wait  = remaining_mt * mc_paths
    c_optimal   = remaining_mt * (f_star * cur + (1 - f_star) * mc_paths)

    exp_now,  p10_now,  p90_now  = _cost_stats(c_all_now)
    exp_wait, p10_wait, p90_wait = _cost_stats(c_all_wait)
    exp_opt,  p10_opt,  p90_opt  = _cost_stats(c_optimal)

    # ── Recommendation banner ──────────────────────────────────────────────────
    pct_now   = round(f_star * 100)
    pct_wait  = 100 - pct_now
    save_vs_wait = exp_wait - exp_opt
    save_sign    = "save" if save_vs_wait >= 0 else "costs"

    rec_color = "#22c55e" if pct_now >= 60 else ("#f59e0b" if pct_now >= 30 else "#60a5fa")
    st.markdown(
        f"<div style='border:2px solid {rec_color};border-radius:12px;"
        f"padding:16px 20px;background:{rec_color}18;margin-bottom:12px;'>"
        f"<span style='font-size:1.05rem;font-weight:700;color:{rec_color};'>"
        f"Optimal split: Buy {pct_now}% now · Wait on {pct_wait}%</span><br>"
        f"<span style='color:#94a3b8;font-size:0.85rem;'>"
        f"Lock in <b style='color:#f1f5f9;'>{mt_now:.1f} mt</b> at today's "
        f"<b style='color:#f1f5f9;'>${cur:,.0f}/mt</b> — "
        f"defer <b style='color:#f1f5f9;'>{mt_wait:.1f} mt</b> until closer to planting.  "
        f"Expected to <b style='color:#f1f5f9;'>{save_sign} ${abs(save_vs_wait):,.0f}</b> "
        f"vs. waiting entirely.</span></div>",
        unsafe_allow_html=True,
    )

    # ── Three-strategy comparison ──────────────────────────────────────────────
    oc1, oc2, oc3 = st.columns(3)
    for col, label, exp, p10, p90, is_opt in [
        (oc1, "Buy All Now",        exp_now,  p10_now,  p90_now,  False),
        (oc2, f"Optimal ({pct_now}% now)", exp_opt, p10_opt, p90_opt, True),
        (oc3, "Wait Entirely",      exp_wait, p10_wait, p90_wait, False),
    ]:
        border = "#f59e0b" if is_opt else "#1e293b"
        bg     = "rgba(245,158,11,0.07)" if is_opt else "rgba(255,255,255,0.02)"
        badge  = "★ RECOMMENDED" if is_opt else ""
        bdg_c  = "#f59e0b"
        with col:
            st.markdown(
                f"<div style='border:2px solid {border};border-radius:10px;"
                f"padding:14px 16px;background:{bg};min-height:175px;'>"
                f"<div style='font-size:0.9rem;font-weight:700;color:#f1f5f9;'>{label}</div>"
                + (f"<div style='font-size:0.68rem;font-weight:700;color:{bdg_c};"
                   f"margin-bottom:6px;'>{badge}</div>" if badge else
                   "<div style='margin-bottom:20px;'></div>")
                + f"<div style='font-size:1.45rem;font-weight:800;color:#f1f5f9;'>${exp:,.0f}</div>"
                f"<div style='font-size:0.73rem;color:#64748b;'>expected total cost</div>"
                f"<hr style='border:none;border-top:1px solid #1e293b;margin:10px 0;'>"
                f"<div style='font-size:0.76rem;color:#64748b;'>"
                f"P10  <span style='color:#22c55e;'>${p10:,.0f}</span> · "
                f"P90  <span style='color:#ef4444;'>${p90:,.0f}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Objective curve chart ──────────────────────────────────────────────────
    fig_opt = go.Figure()
    fig_opt.add_trace(go.Scatter(
        x=f_grid * 100, y=obj_vals,
        mode="lines", line=dict(color="#60a5fa", width=2),
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
        plot_bgcolor="#0b1120", paper_bgcolor="#0b1120",
        font=dict(color="#e2e8f0"), height=260,
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

    # ── SECTION 5: SCENARIO COMPARISON ────────────────────────────────────────
    st.subheader("⚖️ Timing Decision: Buy Now vs. Wait")
    st.markdown(
        "Side-by-side cost comparison for each timing option using your farm inputs "
        f"above. Costs shown for your **remaining {remaining_mt:.1f} mt** to purchase."
    )

    current_price = cur   # already set in optimizer section above
    cost_now      = remaining_mt * current_price

    def _prob_rising(p50, std):
        """P(simulated price > current_price) under N(p50, std)."""
        if std <= 0:
            return 1.0 if p50 > current_price else 0.0
        return float(1 - _norm.cdf(current_price, loc=p50, scale=std))

    scenarios = [
        {
            "label":    "Buy Now",
            "sublabel": "Lock in today's spot price",
            "p10": current_price, "p50": current_price, "p90": current_price,
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

        # ── Pre-compute every display value as a plain Python variable ─────
        p10, p50, p90   = s["p10"], s["p50"], s["p90"]
        c_p50           = remaining_mt * p50
        c_p10           = remaining_mt * p10
        c_p90           = remaining_mt * p90
        delta           = c_p50 - cost_now
        delta_pct       = (delta / cost_now * 100) if cost_now > 0 else 0
        is_baseline     = s["prob_rising"] is None
        prob_save_pct   = 0.0 if is_baseline else (1 - s["prob_rising"]) * 100

        # Formatted strings — all plain str, no HTML
        price_str       = f"${p50:,.0f} /mt"
        range_str       = "Fixed — no price risk" if is_baseline else f"P10  ${p10:,.0f}  –  P90  ${p90:,.0f} /mt"
        cost_str        = f"${c_p50:,.0f}"
        cost_range_str  = f"${c_p10:,.0f} – ${c_p90:,.0f}"
        delta_str       = "No price risk — cost locked in" if is_baseline else f"vs Buy Now:  {delta:+,.0f}  ({delta_pct:+.1f}%)"
        prob_str        = "&nbsp;" if is_baseline else f"Prob cheaper than now:  {prob_save_pct:.0f}%"

        # Card colours
        if is_baseline:
            border = "#60a5fa"
            bg     = "rgba(96,165,250,0.07)"
            b_col  = "#60a5fa"
            badge  = "BASELINE"
        elif p50 < current_price:
            border = "#22c55e"
            bg     = "rgba(34,197,94,0.07)"
            b_col  = "#22c55e"
            badge  = f"SAVE {abs(delta_pct):.1f}%"
        else:
            pct_up = s["prob_rising"] * 100
            if pct_up < 70:
                border = "#f59e0b"; bg = "rgba(245,158,11,0.07)"; b_col = "#f59e0b"
            else:
                border = "#ef4444"; bg = "rgba(239,68,68,0.07)";  b_col = "#ef4444"
            badge = f"{pct_up:.0f}% CHANCE HIGHER"

        delta_col = "#64748b" if is_baseline else ("#22c55e" if delta <= 0 else "#ef4444")
        prob_col  = "#22c55e" if prob_save_pct >= 50 else "#f59e0b"

        with col:
            st.markdown(
                f"<div style='border:2px solid {border};border-radius:12px;"
                f"padding:18px 16px;background:{bg};min-height:300px;"
                f"display:flex;flex-direction:column;'>"
                f"<div style='font-size:1.0rem;font-weight:700;color:#f1f5f9;'>{s['label']}</div>"
                f"<div style='font-size:0.75rem;color:#64748b;margin-bottom:6px;'>{s['sublabel']}</div>"
                f"<span style='background:{b_col}22;color:{b_col};font-size:0.68rem;"
                f"font-weight:700;padding:3px 9px;border-radius:20px;'>{badge}</span>"
                f"<div style='margin-top:14px;font-size:1.9rem;font-weight:800;"
                f"color:#f1f5f9;line-height:1.1;'>{price_str}</div>"
                f"<div style='font-size:0.76rem;color:#64748b;margin-bottom:12px;'>{range_str}</div>"
                f"<hr style='border:none;border-top:1px solid #1e293b;margin:12px 0;'>"
                f"<div style='font-size:0.7rem;color:#64748b;text-transform:uppercase;"
                f"letter-spacing:0.05em;'>Your cost (expected)</div>"
                f"<div style='font-size:1.5rem;font-weight:700;color:#f1f5f9;margin:2px 0;'>{cost_str}</div>"
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


# ==============================================================================
#  TAB 2 — PORTFOLIO RISK
#  Random Forest farm risk model + Risk × Fertilizer Cost overlay
# ==============================================================================
with tab2:

    # ── PORTFOLIO OVERVIEW ─────────────────────────────────────────────────────
    if not df.empty:
        st.subheader("📊 Live Portfolio Overview")

        col1, col2, col3 = st.columns(3)
        high_risk = len(df[df['Requires_Intervention'] == 1])
        with col1:
            st.metric("Total Borrowers", f"{len(df):,}")
        with col2:
            st.metric(
                "Flagged for Intervention", f"{high_risk:,}",
                delta=f"{high_risk} High Risk", delta_color="inverse",
            )
        with col3:
            st.metric("Average LTV", f"{df['Current_LTV_Ratio'].mean()*100:.1f}%")

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig_r1 = px.histogram(
                df, x="Crop_Type", color="Requires_Intervention",
                title="Risk Distribution by Crop Type", barmode="group",
            )
            st.plotly_chart(fig_r1, use_container_width=True)
        with chart_col2:
            fig_r2 = px.scatter(
                df, x="Farm_Area_Acres", y="Current_LTV_Ratio",
                color="Requires_Intervention",
                title="LTV vs. Acreage (red = high risk)",
            )
            st.plotly_chart(fig_r2, use_container_width=True)

        # ── RISK × FERTILIZER COST OVERLAY ────────────────────────────────────
        if cache is not None:
            st.divider()
            st.subheader("⚠️ Risk × Fertilizer Cost Overlay")
            st.markdown(
                "Combines the **Random Forest stress score** with the **XGBoost fertilizer forecast** "
                "to surface which crop segments need intervention most urgently."
            )

            urea_now = cache["signal"]["currentPrice"]
            urea_t2  = cache["signal"]["forecast_t2"]
            fc_pct   = (urea_t2 - urea_now) / urea_now * 100

            avg_acres_by_crop = df.groupby("Crop_Type")["Farm_Area_Acres"].mean()
            crop_risk = (
                df.groupby("Crop_Type")
                .agg(
                    avg_stress=("Stress_Probability", "mean"),
                    high_risk_count=("Requires_Intervention", "sum"),
                    total=("Requires_Intervention", "count"),
                )
                .reset_index()
            )
            crop_risk["high_risk_pct"] = crop_risk["high_risk_count"] / crop_risk["total"] * 100

            overlay_rows = []
            for _, row in crop_risk.iterrows():
                crop     = row["Crop_Type"]
                eng_name = CROP_NAME_MAP.get(crop)
                acres    = avg_acres_by_crop.get(crop, 250)

                if eng_name and eng_name in N_INTENSITY_LBS_PER_ACRE:
                    tons     = (acres * N_INTENSITY_LBS_PER_ACRE[eng_name]) / (UREA_N_CONTENT * LBS_PER_MT)
                    cost_str = f"+${(tons * urea_t2) - (tons * urea_now):,.0f}"
                else:
                    cost_str = "N/A"

                priority = round(row["high_risk_pct"] * (1 + max(fc_pct, 0) / 100), 1)

                overlay_rows.append({
                    "Crop":                                  crop,
                    "High Risk %":                           f"{row['high_risk_pct']:.0f}%",
                    "Avg Stress Probability":                f"{row['avg_stress']*100:.1f}%",
                    "Avg Acreage":                           f"{acres:.0f} ac",
                    "Est. Fertilizer Cost Increase (60d)":   cost_str,
                    "Priority Score":                        priority,
                })

            overlay_df = pd.DataFrame(overlay_rows).sort_values("Priority Score", ascending=False)
            st.dataframe(overlay_df, use_container_width=True, hide_index=True)
            st.caption(
                f"Priority Score = High Risk % × (1 + fertilizer cost increase %).  "
                f"Current forecast: urea {fc_pct:+.1f}% in 60 days.  "
                "Higher score = intervene first."
            )

    st.divider()

    # ── INDIVIDUAL FARM RISK ASSESSMENT ───────────────────────────────────────
    st.subheader("🔍 Run Individual Farm Risk Assessment")

    with st.form("risk_form"):
        input_col1, input_col2 = st.columns(2)

        with input_col1:
            crop_type   = st.selectbox("Crop Type", ["Maize", "Wheat", "Cotton", "Soybean", "Tomato"])
            farm_acres  = st.number_input("Farm Acreage", min_value=10.0, max_value=5000.0, value=250.0)
            irrigation  = st.selectbox("Irrigation Type", ["Sprinkler", "Drip", "Flood", "Rain-fed"])
            soil        = st.selectbox("Soil Type", ["Loamy", "Clay", "Sandy", "Silty"])

        with input_col2:
            season      = st.selectbox("Season", ["Kharif", "Rabi", "Zaid"])
            fert_tons   = st.number_input("Est. Fertilizer Need (Tons)", value=45.0)
            ltv         = st.slider("Current Loan-to-Value (LTV) Ratio", 0.0, 1.0, 0.75)
            delinquency = st.number_input("Months Since Last Delinquency (-1 for never)", value=-1)

        submit_button = st.form_submit_button(label="Run Prediction Engine")

    if submit_button:
        if model is None:
            st.error("Cannot run prediction: model failed to load.")
        else:
            st.write("Analyzing macroeconomic data and borrower profile...")

            borrower_data = {
                "Crop_Type":               crop_type,
                "Farm_Area_Acres":         farm_acres,
                "Irrigation_Type":         irrigation,
                "Soil_Type":               soil,
                "Season":                  season,
                "Fertilizer_Used_Tons":    fert_tons,
                "Current_LTV_Ratio":       ltv,
                "Months_Since_Delinquency": delinquency,
            }

            stress_probability  = model.predict_proba(pd.DataFrame([borrower_data]))[0][1]
            is_high_risk        = stress_probability > 0.65
            recommended_action  = "Offer 60-day interest-only period."

            res_col1, res_col2 = st.columns(2)

            with res_col1:
                st.markdown(
                    f'<p class="big-font">Stress Probability: {stress_probability * 100:.1f}%</p>',
                    unsafe_allow_html=True,
                )

            with res_col2:
                if is_high_risk:
                    st.markdown(
                        f'<div class="alert-box">🚨 HIGH RISK DETECTED<br>'
                        f'Action Required: {recommended_action}</div>',
                        unsafe_allow_html=True,
                    )
                    if officer_email:
                        with st.spinner("Dispatching alert to Loan Officer..."):
                            success = send_risk_alert(
                                officer_email, borrower_data,
                                stress_probability, recommended_action,
                            )
                        if success:
                            st.toast(f"📧 Alert successfully sent to {officer_email}!", icon="✅")
                        else:
                            st.error("Failed to send email. Check terminal for errors.")
                    else:
                        st.warning("⚠️ Enter an email in the sidebar to receive automated email alerts.")

                    if st.button("Dispatch Intervention Offer (SMS)"):
                        st.toast("✅ SMS Offer sent to Borrower!", icon="📱")
                else:
                    st.markdown(
                        '<div class="success-box">✅ Account is Healthy. No intervention needed.</div>',
                        unsafe_allow_html=True,
                    )
