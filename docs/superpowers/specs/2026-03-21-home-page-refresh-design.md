# Home Page Refresh — Design Spec
**Date:** 2026-03-21
**File modified:** `pages/main_app.py` — Overview tab only
**Status:** Approved by user

---

## Summary

Replace the current Overview tab (4 metric cards + donut chart + crop expander) with a full-width three-column layout. The design fuses the financial data hierarchy of "Direction 4" with the green gradient palette of "Direction 3" from the brainstorm session. The layout fills the screen on wide monitors without looking sparse.

---

## Layout

```
st.columns([1, 1.4, 1])
```

Three columns rendered inside `tab_overview`. No padding changes needed — Streamlit's default column gap is sufficient.

---

## Column 1 — Financial Summary Panel (Left)

**Background:** Green gradient via `st.markdown` HTML div (`#14532d → #15803d`).
**Text:** White throughout.

### Contents (top to bottom)

1. **Hero number block**
   - Label: "Season Fertilizer Exposure" (xs uppercase, `#86efac`)
   - Value: `${total_cost:,.0f}` (2rem bold white) — from `get_fertilizer_totals(df)`
   - Subline: `{total_acres:,.0f} acres · {n_crops} crops` (`#bbf7d0`, 0.68rem)

2. **Sparkline**
   - Plotly line chart, height=80, no axes, no margins
   - Data: last 12 months of urea prices from `cache["urea_history"]`
   - Line color `#86efac`, fill `rgba(134,239,172,0.15)`, dot at latest point

3. **Stat pills row** (3 items, flex)
   - Per-Acre Average: `${cost_per_acre:.2f}`
   - Current Urea: `${sig["currentPrice"]:.0f}/mt`
   - 60-Day Signal: `{sig["signal"]}` (text only, no color coding here)

4. **Horizontal cost bar chart per crop**
   - One row per crop: emoji + name · bar (width proportional to cost share) · `$X.XK`
   - Bar colors: `#4ade80` (largest) → `#86efac` → `#bbf7d0` (smallest)
   - Total row at bottom with dashed top border

5. **Insight card** (conditional)
   - Shows if `abs(sig["ng_change_30d"]) > 0.05`
   - Text: "💡 Nat gas {+/-X%} last 30 days — watch for urea cost changes in 6–8 weeks."
   - Background: `rgba(255,255,255,0.10)`, rounded, small font

**Empty state (df is empty):**
All dollar values show `—`. Insight card reads: "Add crops to see your cost exposure."

---

## Column 2 — Crop Distribution (Center)

**Background:** `#f0fdf4` (mint).

### Contents

1. **Section header:** "Crop Distribution" (xs uppercase green label)

2. **Plotly donut chart** (existing chart, restyled)
   - `plot_bgcolor="rgba(0,0,0,0)"`, `paper_bgcolor="rgba(0,0,0,0)"`
   - Green palette: primary crop `#15803d`, secondary `#22c55e`, tertiary `#4ade80`, additional colors cycle through existing `get_crop_colors_for_df()` logic
   - `height=240`, legend below chart
   - Existing season-filter checkbox + multiselect retained

3. **Two insight cards** (side by side, below chart)
   - Card 1 — Largest Cost Driver: crop name + `${cost:,.0f} · {pct:.0f}% of spend`
   - Card 2 — Highest N Intensity: `{n_lbs} lbs/ac` + crop name
   - White background, `#d1fae5` border, `#14532d` text
   - Hidden if df is empty

**Empty state:** Donut replaced with a grey dashed circle placeholder + centered text "No crops yet — add one on the right."

---

## Column 3 — Crop Management (Right)

**Background:** White with `#f0fdf4` outer padding.

### Contents

1. **Section header row:** "Your Crops" label + season badge (green pill)

2. **Crop list** (existing `get_farmer_crops` data)
   - Each row: colored dot · crop name (bold) · season+acres (small grey) · `$X.XK` cost · ✕ remove button
   - Colored dots match donut chart colors
   - Remove button: small, red border, `#fff5f5` background
   - Scrollable if many crops (max-height via CSS)

3. **"＋ Add a Crop" button** — full-width, dark green (`#14532d`), white text
   - Clicking expands `st.expander` directly below it (existing add-crop form logic retained: crop name, acres, season select/create)

4. **Signal pill** (bottom of column)
   - Colored dot (red/amber/green/grey per signal) + `{signal}` text + "Full analysis →" that sets `st.session_state` to switch to Tab 2
   - White background, `#d1fae5` border

**Empty state:**
Crop list replaced with: "Your farm is empty. Add your first crop below." (grey italic, centered). Add button and signal pill always visible.

---

## What's Removed

| Removed | Replaced by |
|---|---|
| Top banner image div | Green left panel serves as hero |
| 4 standalone metric cards row | Stats embedded in left panel |
| Top-of-page "Add a Crop" expander | Button + expander in right column |
| Plain empty-state div | Per-column empty states |

The existing `get_fertilizer_totals()`, `get_crop_colors_for_df()`, `get_farmer_crops()`, and `delete_crop()` functions are all reused. No backend changes.

---

## Data Dependencies

| Data | Source | Fallback |
|---|---|---|
| Crop list | `get_farmer_crops(email)` | Empty df → empty states |
| Fertilizer cost/lbs | `get_fertilizer_totals(df)` | `0` if df empty |
| Urea sparkline | `cache["urea_history"]` | Hide sparkline if cache None |
| Current price / signal | `cache["signal"]` | Show `—` if cache None |
| Nat gas change | `cache["signal"]["ng_change_30d"]` | Hide insight card if missing |

---

## Styling Notes

- All custom HTML rendered via `st.markdown(..., unsafe_allow_html=True)`
- Green panel uses `min-height: 100%` to stretch full column height
- Streamlit columns handle responsive reflow — no extra CSS needed for narrow screens
- Existing CSS classes (`.metric-card`, `.empty-state`) can be removed or left unused — no conflict

---

## Out of Scope

- Login page (`login.py`) — not changed
- Tab 2 (Fertilizer Costs & Risk Assessment) — not changed
- Tab 3 (Regional Price Map) — not changed
- Backend pipeline — not changed
