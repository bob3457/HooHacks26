# Home Page Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Overview tab's 4-metric-card + top-expander layout with a 3-column design: green financial panel (left), donut chart + insight cards (center), crop management (right).

**Architecture:** All changes are inside the `with tab_overview:` block in `pages/main_app.py` (lines ~488–690). The three columns are rendered with `st.columns([1, 1.4, 1])`. Column 1 uses `st.markdown` HTML for the styled green panel with an SVG sparkline and HTML bar rows. Columns 2 and 3 use standard Streamlit widgets. No new files, no backend changes.

**Note on tab switching:** Streamlit's `st.tabs` has no programmatic API to select a tab by index. The "View full analysis →" signal pill in Column 3 is therefore rendered as an `st.info()` hint, not a functional navigation button.

**Tech Stack:** Streamlit, Plotly, Python, SQLite, HTML/SVG inline via `st.markdown`

---

## Files Modified

- `pages/main_app.py` — Overview tab only. All helper functions above the `with tab_overview:` block are unchanged.

---

## Task 1: Add two helper functions above the tab block

Both helpers are pure functions with no side effects. Add them just before the `with tab_overview:` line (around line ~487, after `build_state_df`).

**Files:**
- Modify: `pages/main_app.py` — insert after `build_state_df` function

- [ ] **Step 1: Add `_build_sparkline_svg`**

```python
def _build_sparkline_svg(values: list, width: int = 200, height: int = 48) -> str:
    """Returns an inline SVG polyline from a list of floats. Empty string if insufficient data."""
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    step = width / (len(values) - 1)
    pts = " ".join(
        f"{i * step:.1f},{height - ((v - mn) / rng) * (height - 6) - 3:.1f}"
        for i, v in enumerate(values)
    )
    fill_pts = f"0,{height} " + pts + f" {width},{height}"
    last_x = (len(values) - 1) * step
    last_y = height - ((values[-1] - mn) / rng) * (height - 6) - 3
    return (
        f'<svg viewBox="0 0 {width} {height}" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" style="width:100%;height:{height}px;">'
        f'<polygon points="{fill_pts}" fill="rgba(134,239,172,0.15)"/>'
        f'<polyline points="{pts}" stroke="#86efac" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="#4ade80"/>'
        f'</svg>'
    )
```

- [ ] **Step 2: Add `_build_cost_bars_html`**

```python
def _build_cost_bars_html(df: pd.DataFrame, fert_totals: dict) -> str:
    """Returns HTML string of per-crop horizontal cost bars for the green financial panel."""
    if df.empty:
        return '<div style="color:#86efac;font-size:0.75rem;opacity:0.7;">Add crops to see breakdown.</div>'

    _cache = load_cache()
    cur_p = (_cache or {}).get("signal", {}).get("currentPrice", 400) or 400
    cost_per_lb_n = (cur_p / LBS_PER_MT) / UREA_N_CONTENT

    from collections import defaultdict
    agg: dict = defaultdict(float)
    for _, row in df.iterrows():
        n_lbs = N_INTENSITY_LBS_PER_ACRE.get(row["crop_name"], 100) * row["acres"]
        agg[row["crop_name"]] += n_lbs * cost_per_lb_n

    total = sum(agg.values()) or 1
    # Colors from brightest (largest) to dimmest (smallest)
    bar_colors = ["#4ade80", "#34d399", "#22c55e", "#16a34a", "#15803d"]
    crop_emojis = {"Corn": "🌽", "Wheat": "🌾", "Soybeans": "🫘",
                   "Cotton": "🪴", "Sorghum": "🌿", "Hay": "🌱"}
    html = ""
    for i, (crop, cost) in enumerate(sorted(agg.items(), key=lambda x: -x[1])):
        pct = cost / total * 100
        color = bar_colors[min(i, len(bar_colors) - 1)]
        emoji = crop_emojis.get(crop, "🌾")
        html += (
            f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;">'
            f'<span style="font-size:0.65rem;color:#d1fae5;width:72px;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;">{emoji} {crop}</span>'
            f'<div style="flex:1;height:5px;background:rgba(255,255,255,0.12);'
            f'border-radius:3px;overflow:hidden;">'
            f'<div style="width:{pct:.0f}%;height:100%;background:{color};border-radius:3px;"></div>'
            f'</div>'
            f'<span style="font-size:0.62rem;color:#d1fae5;font-weight:700;'
            f'width:42px;text-align:right;">${cost/1000:.1f}K</span>'
            f'</div>'
        )

    total_val = fert_totals.get("fertilizer_cost_usd", 0)
    html += (
        f'<div style="display:flex;justify-content:space-between;'
        f'border-top:1px dashed rgba(255,255,255,0.2);margin-top:5px;padding-top:5px;">'
        f'<span style="font-size:0.62rem;color:#86efac;">Total</span>'
        f'<span style="font-size:0.68rem;font-weight:700;color:#fff;">${total_val:,.0f}</span>'
        f'</div>'
    )
    return html
```

- [ ] **Step 3: Syntax check**

```bash
cd C:/Users/Damien/Desktop/HooHacks26
python -c "import ast; ast.parse(open('pages/main_app.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pages/main_app.py
git commit -m "feat: add sparkline and cost bar HTML helpers"
```

---

## Task 2: Replace the `with tab_overview:` block with the 3-column skeleton + Column 1

**Before starting:** The entire existing `with tab_overview:` block runs from line ~488 to ~710. Save the add-crop form code (lines ~491–570) to a scratch buffer — you will need it verbatim in Task 4.

**Files:**
- Modify: `pages/main_app.py` — replace `with tab_overview:` block (lines ~488–710)

- [ ] **Step 1: Replace the entire `with tab_overview:` block**

Delete everything from `with tab_overview:` through the end of the old crop table code (stop before `# ════ TAB 2`). Replace with the following. The add-crop form (Task 4) and the rest of the columns (Tasks 3–4) will be filled in subsequent tasks — leave their `with col_X:` blocks open as stubs for now:

```python
with tab_overview:
    # ── Shared computed values ────────────────────────────────────────────
    fert          = get_fertilizer_totals(df) if not df.empty else {"fertilizer_used_lbs": 0, "fertilizer_cost_usd": 0}
    total_acres   = float(df["acres"].sum()) if not df.empty else 0.0
    total_cost    = fert["fertilizer_cost_usd"]
    cost_per_acre = (total_cost / total_acres) if total_acres > 0 else 0.0
    n_crops       = int(df["crop_name"].nunique()) if not df.empty else 0

    sig           = (cache or {}).get("signal", {})
    cur_price     = sig.get("currentPrice", 0) or 0
    signal_label  = sig.get("signal", "N/A")
    ng_chg        = sig.get("ng_change_30d", 0) or 0

    urea_hist     = (cache or {}).get("urea_history", None)

    col_left, col_center, col_right = st.columns([1, 1.4, 1])

    # ── COLUMN 1: Financial Panel ─────────────────────────────────────────
    with col_left:
        spark_svg = ""
        if urea_hist and urea_hist.get("values"):
            spark_svg = _build_sparkline_svg(urea_hist["values"][-12:])

        if abs(ng_chg) > 0.05:
            direction = "up" if ng_chg > 0 else "down"
            insight_html = (
                f'<div style="background:rgba(255,255,255,0.10);border-radius:8px;'
                f'padding:8px 10px;font-size:0.68rem;color:#d1fae5;line-height:1.5;margin-top:6px;">'
                f'💡 Nat gas {direction} {abs(ng_chg)*100:.0f}% last 30 days — '
                f'watch for urea cost changes in 6–8 weeks.</div>'
            )
        elif df.empty:
            insight_html = (
                '<div style="background:rgba(255,255,255,0.10);border-radius:8px;'
                'padding:8px 10px;font-size:0.68rem;color:#d1fae5;line-height:1.5;margin-top:6px;">'
                '💡 Add crops to see your cost exposure.</div>'
            )
        else:
            insight_html = ""

        cost_bars_html = _build_cost_bars_html(df, fert)

        hero_val   = f"${total_cost:,.0f}" if not df.empty else "—"
        acres_line = (
            f"{total_acres:,.0f} acres · {n_crops} crop{'s' if n_crops != 1 else ''}"
            if not df.empty else "No crops added yet"
        )
        per_acre  = f"${cost_per_acre:.2f}" if not df.empty else "—"
        urea_disp = f"${cur_price:.0f}/mt" if cur_price else "—"

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#14532d 0%,#166534 55%,#15803d 100%);
                    border-radius:12px;padding:20px 18px;
                    display:flex;flex-direction:column;gap:10px;">
          <div>
            <div style="font-size:0.58rem;text-transform:uppercase;letter-spacing:1px;
                        color:#86efac;margin-bottom:4px;">Season Fertilizer Exposure</div>
            <div style="font-size:2rem;font-weight:800;color:#fff;line-height:1.1;">{hero_val}</div>
            <div style="font-size:0.68rem;color:#bbf7d0;margin-top:4px;">{acres_line}</div>
          </div>
          {spark_svg}
          <div style="display:flex;gap:14px;border-top:1px solid rgba(255,255,255,0.12);padding-top:10px;">
            <div>
              <div style="font-size:0.52rem;color:#6ee7b7;text-transform:uppercase;
                          letter-spacing:0.5px;">Per Acre</div>
              <div style="font-size:0.85rem;font-weight:700;color:#fff;margin-top:1px;">{per_acre}</div>
            </div>
            <div>
              <div style="font-size:0.52rem;color:#6ee7b7;text-transform:uppercase;
                          letter-spacing:0.5px;">Urea Price</div>
              <div style="font-size:0.85rem;font-weight:700;color:#fff;margin-top:1px;">{urea_disp}</div>
            </div>
            <div>
              <div style="font-size:0.52rem;color:#6ee7b7;text-transform:uppercase;
                          letter-spacing:0.5px;">60-Day Signal</div>
              <div style="font-size:0.85rem;font-weight:700;color:#fff;margin-top:1px;">{signal_label}</div>
            </div>
          </div>
          <div style="border-top:1px solid rgba(255,255,255,0.12);padding-top:8px;">
            <div style="font-size:0.55rem;color:#86efac;text-transform:uppercase;
                        letter-spacing:0.5px;margin-bottom:6px;">Cost by Crop</div>
            {cost_bars_html}
          </div>
          {insight_html}
        </div>
        """, unsafe_allow_html=True)

    # ── COLUMN 2: placeholder (filled in Task 3) ──────────────────────────
    with col_center:
        st.write("chart coming soon")

    # ── COLUMN 3: placeholder (filled in Task 4) ──────────────────────────
    with col_right:
        st.write("management coming soon")
```

- [ ] **Step 2: Syntax check and smoke test**

```bash
python -c "import ast; ast.parse(open('pages/main_app.py', encoding='utf-8').read()); print('OK')"
```

Then open the app and verify: left green panel renders with hero number, sparkline, stat pills, and bars. Center and right show placeholder text.

- [ ] **Step 3: Commit**

```bash
git add pages/main_app.py
git commit -m "feat: add 3-column skeleton and green financial panel"
```

---

## Task 3: Fill Column 2 — Donut Chart + Insight Cards

Replace `st.write("chart coming soon")` in `with col_center:` with the full chart + cards.

**Files:**
- Modify: `pages/main_app.py` — replace stub inside `with col_center:`

- [ ] **Step 1: Replace the col_center stub**

Replace `st.write("chart coming soon")` with:

```python
        st.markdown(
            '<div style="font-size:0.62rem;color:#4b7c59;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">'
            'Crop Distribution</div>',
            unsafe_allow_html=True,
        )

        if df.empty:
            st.markdown("""
            <div style="background:#f0fdf4;border-radius:12px;height:260px;
                        display:flex;align-items:center;justify-content:center;
                        border:2px dashed #86efac;text-align:center;padding:20px;">
              <div>
                <div style="font-size:2rem;margin-bottom:8px;">🌾</div>
                <div style="font-size:0.85rem;color:#4b7c59;font-weight:600;">No crops yet</div>
                <div style="font-size:0.72rem;color:#9ca3af;margin-top:4px;">
                  Add your first crop on the right →</div>
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            # Year filter
            all_years_in_data = sorted(df["year"].dropna().astype(int).unique().tolist(), reverse=True)
            current_year = 2026
            default_year = current_year if current_year in all_years_in_data else (all_years_in_data[0] if all_years_in_data else current_year)
            if "pie_year_filter" not in st.session_state:
                st.session_state["pie_year_filter"] = default_year
            if st.session_state["pie_year_filter"] not in all_years_in_data and all_years_in_data:
                st.session_state["pie_year_filter"] = default_year
            selected_year = st.selectbox(
                "Year",
                options=all_years_in_data,
                index=all_years_in_data.index(st.session_state["pie_year_filter"]) if st.session_state["pie_year_filter"] in all_years_in_data else 0,
                key="pie_year_filter",
            )

            # Season filter
            all_seasons_in_data   = sorted(df["season"].unique().tolist())
            all_seasons_available = sorted(set(all_seasons_in_data + st.session_state.seasons))
            if "_pie_select_all_saved" in st.session_state:
                st.session_state["pie_select_all"] = st.session_state.pop("_pie_select_all_saved")
            if "_pie_filter_saved" in st.session_state:
                saved = st.session_state.pop("_pie_filter_saved")
                if saved is not None:
                    st.session_state["pie_season_filter"] = saved
            if "pie_select_all" not in st.session_state:
                st.session_state["pie_select_all"] = True
            select_all = st.checkbox("Select all seasons", key="pie_select_all")
            selected_seasons = (
                all_seasons_available if select_all else
                st.multiselect("Filter by season", options=all_seasons_available,
                               default=all_seasons_in_data, key="pie_season_filter")
            )

            filtered_df = df[
                (df["season"].isin(selected_seasons)) &
                (df["year"].astype(int) == int(selected_year))
            ].copy() if selected_seasons else df.iloc[0:0].copy()

            season_base = get_season_base_colors(all_seasons_available)

            if filtered_df.empty:
                st.info("No crops match the selected year and seasons.")
            else:
                crop_colors = get_crop_colors_for_df(filtered_df, season_base)
                dup_crops = filtered_df["crop_name"].duplicated(keep=False)
                filtered_df["display_label"] = filtered_df.apply(
                    lambda r: f"{r['crop_name']} ({r['season']})" if dup_crops[r.name] else r["crop_name"],
                    axis=1,
                )
                fig = go.Figure()
                fig.add_trace(go.Pie(
                    labels=filtered_df["display_label"],
                    values=filtered_df["acres"],
                    marker=dict(colors=crop_colors, line=dict(color="white", width=1.5)),
                    textposition="inside",
                    textinfo="percent+label",
                    hole=0.35,
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f} acres (%{percent})<extra></extra>",
                    showlegend=True,
                ))
                # Season legend traces
                for season, base_color in season_base.items():
                    if season in filtered_df["season"].values:
                        fig.add_trace(go.Scatter(
                            x=[None], y=[None], mode="markers",
                            marker=dict(symbol="square", size=10, color=base_color),
                            name=season, showlegend=True,
                        ))
                fig.update_layout(
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.28,
                                xanchor="center", x=0.5, font=dict(size=11)),
                    margin=dict(t=10, b=70, l=10, r=10),
                    height=270,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#14532d"),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Insight cards — largest cost driver + highest N intensity
                _c2p  = (cache or {}).get("signal", {}).get("currentPrice", 400) or 400
                _cplbn = (_c2p / LBS_PER_MT) / UREA_N_CONTENT
                crop_costs = {}
                for crop_name in df["crop_name"].unique():
                    total_n = df[df["crop_name"] == crop_name]["acres"].sum() * N_INTENSITY_LBS_PER_ACRE.get(crop_name, 100)
                    crop_costs[crop_name] = total_n * _cplbn

                top_crop = max(crop_costs, key=crop_costs.get) if crop_costs else "—"
                top_cost = crop_costs.get(top_crop, 0)
                top_pct  = top_cost / sum(crop_costs.values()) * 100 if crop_costs else 0
                hi_n_crop = max(df["crop_name"].unique(),
                                key=lambda c: N_INTENSITY_LBS_PER_ACRE.get(c, 0),
                                default="—")
                hi_n_val = N_INTENSITY_LBS_PER_ACRE.get(hi_n_crop, 0)

                ic1, ic2 = st.columns(2)
                ic1.markdown(f"""
                <div style="background:#fff;border:1.5px solid #d1fae5;border-radius:10px;
                            padding:10px 12px;margin-top:4px;">
                  <div style="font-size:0.55rem;color:#6b7280;text-transform:uppercase;
                              letter-spacing:0.4px;margin-bottom:3px;">Largest Cost Driver</div>
                  <div style="font-size:0.95rem;font-weight:700;color:#14532d;">{top_crop}</div>
                  <div style="font-size:0.6rem;color:#6b7280;margin-top:2px;">
                    ${top_cost:,.0f} · {top_pct:.0f}% of spend</div>
                </div>""", unsafe_allow_html=True)
                ic2.markdown(f"""
                <div style="background:#fff;border:1.5px solid #d1fae5;border-radius:10px;
                            padding:10px 12px;margin-top:4px;">
                  <div style="font-size:0.55rem;color:#6b7280;text-transform:uppercase;
                              letter-spacing:0.4px;margin-bottom:3px;">Highest N Intensity</div>
                  <div style="font-size:0.95rem;font-weight:700;color:#14532d;">{hi_n_val} lbs/ac</div>
                  <div style="font-size:0.6rem;color:#6b7280;margin-top:2px;">{hi_n_crop} — most N-heavy</div>
                </div>""", unsafe_allow_html=True)
```

- [ ] **Step 2: Syntax check and smoke test**

```bash
python -c "import ast; ast.parse(open('pages/main_app.py', encoding='utf-8').read()); print('OK')"
```

Open app — center column shows donut chart with green palette and two insight cards below. Right column still shows placeholder text.

- [ ] **Step 3: Commit**

```bash
git add pages/main_app.py
git commit -m "feat: add donut chart and insight cards to center column"
```

---

## Task 4: Fill Column 3 — Crop Management

Replace `st.write("management coming soon")` in `with col_right:` with the crop list, add-crop form (full code below — do not reference deleted lines), and signal pill.

**Files:**
- Modify: `pages/main_app.py` — replace stub inside `with col_right:`

- [ ] **Step 1: Replace the col_right stub**

Replace `st.write("management coming soon")` with:

```python
        st.markdown(
            '<div style="font-size:0.62rem;color:#4b7c59;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'
            'Your Crops</div>',
            unsafe_allow_html=True,
        )

        # Crop list
        if not df.empty:
            season_base_r = get_season_base_colors(st.session_state.seasons)
            crop_colors_r = get_crop_colors_for_df(df, season_base_r)
            for (_, row), color in zip(df.iterrows(), crop_colors_r):
                r1, r2 = st.columns([4, 1])
                r1.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;">'
                    f'<div style="width:9px;height:9px;border-radius:50%;background:{color};'
                    f'flex-shrink:0;"></div>'
                    f'<div>'
                    f'<div style="font-size:0.75rem;font-weight:600;color:#14532d;">{row["crop_name"]}</div>'
                    f'<div style="font-size:0.62rem;color:#6b7280;">'
                    f'{row["season"]} · {row["acres"]:,.0f} ac · '
                    f'${N_INTENSITY_LBS_PER_ACRE.get(row["crop_name"],100)*row["acres"]*(cur_price/LBS_PER_MT/UREA_N_CONTENT if cur_price else 0):,.0f}'
                    f'</div></div></div>',
                    unsafe_allow_html=True,
                )
                if r2.button("✕", key=f"del_{row['id']}", use_container_width=True):
                    delete_crop(row["id"])
                    st.rerun()
        else:
            st.markdown(
                '<div style="font-size:0.8rem;color:#9ca3af;font-style:italic;'
                'text-align:center;padding:16px 0 8px 0;">Your farm is empty.<br>'
                'Add your first crop below.</div>',
                unsafe_allow_html=True,
            )

        # Add crop form (full logic — no external reference needed)
        with st.expander("＋ Add a Crop", expanded=df.empty):
            COMMON_CROPS = [
                "Alfalfa", "Barley", "Canola", "Cotton", "Corn", "Hay",
                "Oats", "Rice", "Sorghum", "Soybeans", "Sunflowers", "Wheat",
            ]
            if "custom_crops" not in st.session_state:
                st.session_state.custom_crops = []
            if "_next_crop" in st.session_state:
                st.session_state["crop_selectbox"] = st.session_state.pop("_next_crop")
            if "_next_season" in st.session_state:
                st.session_state["season_selectbox"] = st.session_state.pop("_next_season")

            all_crops = COMMON_CROPS + st.session_state.custom_crops + ["Add new crop…"]
            col_a, col_c, col_yr = st.columns([3, 3, 1])
            crop_sel = col_a.selectbox("Crop", options=all_crops, key="crop_selectbox")
            if crop_sel == "Add new crop…":
                new_crop_text = col_a.text_input("New crop name", placeholder="e.g. Millet", key="new_crop_text")
                if col_a.button("Add to list", key="add_crop_btn"):
                    nc = new_crop_text.strip().title()
                    if nc and nc not in COMMON_CROPS and nc not in st.session_state.custom_crops:
                        st.session_state.custom_crops.append(nc)
                    if nc:
                        st.session_state["_next_crop"] = nc
                        st.rerun()

            season_options = st.session_state.seasons + ["Create new…"]
            season_sel = col_c.selectbox("Season", options=season_options, key="season_selectbox")
            if season_sel == "Create new…":
                new_season_text = col_c.text_input("New season name", placeholder="e.g. Summer", key="new_season_text")
                if col_c.button("Add season", key="add_season_btn"):
                    ns = new_season_text.strip().title()
                    if ns and ns not in st.session_state.seasons:
                        st.session_state.seasons.append(ns)
                    if ns:
                        st.session_state["_next_season"] = ns
                        st.rerun()

            year_sel = col_yr.number_input("Year", min_value=2000, max_value=2100, value=2025, step=1, key="year_input")

            with st.form("add_crop_form", clear_on_submit=True):
                col_b, col_d = st.columns([5, 1])
                acres_input = col_b.text_input("Acres", placeholder="e.g. 320")
                col_d.markdown("<br>", unsafe_allow_html=True)
                submitted = col_d.form_submit_button("Add", width='stretch')
                if submitted:
                    crop_val   = st.session_state.get("crop_selectbox", "")
                    season_val = st.session_state.get("season_selectbox", "")
                    year_val   = st.session_state.get("year_input", 2025)
                    if not crop_val or crop_val == "Add new crop…":
                        st.warning("Please select (or add) a crop first.")
                        st.stop()
                    if not season_val or season_val == "Create new…":
                        st.warning("Please select (or create) a season first.")
                        st.stop()
                    try:
                        acres_val = float(acres_input.strip().replace(",", ""))
                        if acres_val <= 0:
                            raise ValueError
                    except ValueError:
                        st.warning("Please enter a valid number of acres.")
                        st.stop()
                    add_crop(email, crop_val, acres_val, season_val, int(year_val))
                    st.success(f"Added {crop_val} — {season_val} {int(year_val)} ({acres_val:,.0f} acres).")
                    st.session_state["_pie_select_all_saved"] = st.session_state.get("pie_select_all", True)
                    st.session_state["_pie_filter_saved"] = st.session_state.get("pie_season_filter", None)
                    st.rerun()

        # Signal pill (informational — Streamlit tabs cannot be switched programmatically)
        _sig_colors = {
            "BUY_NOW": "#ef4444", "CONSIDER_BUYING": "#f59e0b",
            "WAIT": "#22c55e", "NEUTRAL": "#6b7280",
        }
        _dot_color = _sig_colors.get(signal_label, "#6b7280")
        _rationale = sig.get("rationale", "Run pipeline for signal.")
        _rationale_short = _rationale[:70] + ("…" if len(_rationale) > 70 else "")
        st.markdown(f"""
        <div style="background:#fff;border:1.5px solid #d1fae5;border-radius:8px;
                    padding:8px 12px;display:flex;align-items:flex-start;gap:8px;margin-top:8px;">
          <div style="width:9px;height:9px;border-radius:50%;background:{_dot_color};
                      flex-shrink:0;margin-top:3px;"></div>
          <div style="font-size:0.68rem;color:#14532d;line-height:1.5;">
            <strong>{signal_label}</strong> — {_rationale_short}<br>
            <span style="color:#4b7c59;font-size:0.62rem;">
              See "Fertilizer Costs &amp; Risk Assessment" tab for full analysis.</span>
          </div>
        </div>""", unsafe_allow_html=True)
```

- [ ] **Step 2: Syntax check**

```bash
python -c "import ast; ast.parse(open('pages/main_app.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Full smoke test — three scenarios**

```bash
.venv/Scripts/streamlit run login.py
```

1. **New user (no crops):** Left = dashes + insight card. Center = dashed circle placeholder. Right = italic empty message + open add-crop form + signal pill.
2. **Add a crop via the form:** All three columns update. Donut appears. Bars appear in left panel. Crop row appears in right column list.
3. **Remove a crop:** Row disappears, costs update. Back to empty state if last crop removed.

- [ ] **Step 4: Commit**

```bash
git add pages/main_app.py
git commit -m "feat: add crop management and signal pill to right column"
```

---

## Task 5: Cleanup — remove dead code

**Files:**
- Modify: `pages/main_app.py` — CSS block and banner section

- [ ] **Step 1: Remove unused CSS classes**

In the `<style>` block (around line 400), find and delete the `.metric-card`, `.metric-label`, `.metric-value`, and `.empty-state` rule blocks — they are no longer referenced.

- [ ] **Step 2: Remove the old banner and crop_circle image call**

Find and remove:
```python
crop_circle_bg = get_image_base64("crop_circle.jpg")
banner_bg_url = crop_circle_bg if crop_circle_bg else "linear-gradient(#f0f7f0, #e8f5e9)"
```
And the `st.markdown(""" <div class="banner"> ... """, ...)` block that follows it — the green financial panel now serves as the visual hero.

- [ ] **Step 3: Final syntax check and full regression test**

```bash
python -c "import ast; ast.parse(open('pages/main_app.py', encoding='utf-8').read()); print('OK')"
.venv/Scripts/streamlit run login.py
```

Verify:
- Overview tab: 3-column layout correct
- Fertilizer Costs tab: unchanged
- Regional Price Map tab: unchanged
- Sign out and sign back in: session state resets correctly

- [ ] **Step 4: Final commit**

```bash
git add pages/main_app.py
git commit -m "feat: complete overview tab 3-column refresh, remove dead CSS and banner"
```
