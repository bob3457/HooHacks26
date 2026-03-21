# AgriSignal — Data Findings & Usage Guide

---

## 1. Data Inventory & Status

| File | Rows | Date Range | Status | Role in Project |
|---|---|---|---|---|
| `data/natural-gas-prices/daily.csv` | 7,190 | 1997-01-07 → 2025-08-18 | **PRIMARY** ✅ | Henry Hub spot, $/MMBtu |
| `data/natural-gas-prices/monthly.csv` | 343 | 1997-01 → 2025-07 | **PRIMARY** ✅ | Henry Hub monthly mean, $/MMBtu |
| `data/series_data/NG_SUM_LSUM_DCU_NUS_M.xls` | multi-sheet | 1973-01 → 2025-12 | **SECONDARY** ✅ | Industrial price, storage, production |
| `data/series_data/NG_MOVE_STATE_A_EPG0_IM0_MMCF_A.xls` | 53 | 1973 → 2025 (annual) | **LOW VALUE** ⚠️ | State-level imports — skip for MVP |
| `data/agriculture-and-farming-dataset/agriculture_dataset.csv` | 50 | No time index | **LOOKUP ONLY** ⚠️ | Fertilizer intensity benchmarks |

### What's MISSING (must fetch externally):
- **Fertilizer prices** (Urea, DAP, Ammonia $/mt) — World Bank Pink Sheet
- **NG futures prices** (1-month, 3-month) — EIA API
- **USDA crop prices** — EIA/USDA APIs

---

## 2. File-by-File Details

---

### 2.1 `data/natural-gas-prices/daily.csv` — Henry Hub Daily Spot

**Columns:** `Date` (string, YYYY-MM-DD), `Price` (float, $/MMBtu)

**Issues & fixes:**
- `Date` is stored as object — always parse: `pd.to_datetime(df['Date'])`
- 1 null row: `2018-01-05` — forward-fill with `.ffill()`
- Business days only (weekends missing) — expected, not a bug

**Key stats (2018–2025):**
- Normal range: $1.50 – $5.00 / MMBtu
- 2022 energy crisis spike: **avg $7–8.80/MMBtu** (May–Aug 2022), peak daily ~$9.85
- Recent (2025): $2.78–$4.20 range

**How to load:**
```python
df = pd.read_csv('data/natural-gas-prices/daily.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['Price'] = df['Price'].ffill()  # fills the one null
df = df.set_index('Date').rename(columns={'Price': 'ng_spot'})
```

**To get monthly mean (for feature store):**
```python
monthly = df['ng_spot'].resample('MS').mean()  # MS = month start
```

---

### 2.2 `data/natural-gas-prices/monthly.csv` — Henry Hub Monthly

**Columns:** `Month` (string, YYYY-MM), `Price` (float, $/MMBtu)

**Issues & fixes:**
- `Month` is string — parse: `pd.to_datetime(df['Month'])`
- No nulls
- This is a pre-aggregated monthly series — use this directly instead of resampling daily

**How to load:**
```python
ng_m = pd.read_csv('data/natural-gas-prices/monthly.csv')
ng_m['Month'] = pd.to_datetime(ng_m['Month'])
ng_m = ng_m.set_index('Month').rename(columns={'Price': 'ng_spot'})
# index is month-start timestamps (2025-07-01, etc.)
```

---

### 2.3 `data/series_data/NG_SUM_LSUM_DCU_NUS_M.xls` — EIA US NG Summary

Multi-sheet EIA workbook. **Header row is index 2** (row 0 = "Back to Contents", row 1 = source keys, row 2 = column names). Dates are in column 0 as timestamps with format `YYYY-MM-15`.

**Sheets and their value:**

| Sheet | Content | Value |
|---|---|---|
| Data 1 | 12 price series ($/Mcf) | **HIGH** — industrial price is key |
| Data 2 | 11 production series (MMcf) | MEDIUM — dry production useful |
| Data 3 | Imports/Exports (MMcf) | LOW for MVP |
| Data 4 | Underground Storage (MMcf) | **HIGH** — storage is a key price predictor |
| Data 5 | Consumption (MMcf) | MEDIUM — seasonal patterns |

**Standard load pattern:**
```python
def load_xls_sheet(sheet_name):
    df = pd.read_excel(
        'data/series_data/NG_SUM_LSUM_DCU_NUS_M.xls',
        sheet_name=sheet_name,
        header=2  # row 2 = column headers
    )
    df = df.rename(columns={df.columns[0]: 'Date'})
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.set_index('Date')
    df.index = df.index.to_period('M').to_timestamp()  # normalize to month-start
    return df
```

**Data 1 — Key columns to extract:**

```python
prices = load_xls_sheet('Data 1')

# Industrial price ($/Mcf) — highly correlated with Henry Hub (r=0.896)
# NOTE: units are $/Mcf (thousand cubic feet), NOT $/MMBtu
# Convert: $/Mcf ÷ 1.02 ≈ $/MMBtu (rough, since 1 MMBtu ≈ 1 Mcf for NG)
ng_industrial = prices['United States Natural Gas Industrial Price (Dollars per Thousand Cubic Feet)']

# Wellhead price — all NaN from ~2018 onward, skip it
# Use ng_spot from the CSV files instead
```

**Data 4 — Underground storage (key feature for price forecasting):**

```python
storage = load_xls_sheet('Data 4')

# Working gas = the gas actually available for withdrawal — the key metric
working_gas = storage['U.S. Total Natural Gas in Underground Storage (Working Gas) (MMcf)']
# Range (2018–2025): 1.18M – 3.94M MMcf
# Low storage → upward price pressure; high storage → price suppression
# No nulls, data through 2025-12
```

**Storage → price relationship:**
- Low storage (< 1.8M MMcf, like Feb 2025): prices spike ($4–6/MMBtu)
- High storage (> 3.5M MMcf, like Oct 2025): prices stay suppressed
- Use as a feature: `storage_vs_5yr_avg` = current / 5-year monthly average

---

### 2.4 `data/agriculture-and-farming-dataset/agriculture_dataset.csv` — Farm Dataset

**⚠️ IMPORTANT LIMITATION:** This is an **Indian farming dataset** (Kharif/Zaid/Rabi are Indian seasons). It has only 50 rows and no time series. It cannot be used for forecasting.

**What it IS useful for:**
- Fertilizer intensity benchmarks (tons/acre) as a fallback if USDA data is unavailable
- The spec uses USDA data for this — prefer USDA if fetched

**Fertilizer intensity (tons/acre) from this dataset:**
```
Potato:    0.199 tons/acre   (not a target US crop)
Sugarcane: 0.113 tons/acre
Wheat:     0.033 tons/acre   ← US crop
Soybean:   0.022 tons/acre   ← US crop
Cotton:    0.019 tons/acre   ← US crop
Maize:     0.014 tons/acre   ← US crop (corn proxy)
```

**Use for exposure calculator only as fallback.** Prefer spec's hardcoded values:
```python
# From spec (US-specific, lbs N/acre):
CROP_N_LBS_PER_ACRE = {
    'corn':     150,
    'wheat':    90,
    'cotton':   80,
    'sorghum':  80,
    'soybeans': 5,
    'hay':      20,
}
# Convert: lbs N / 2000 lbs/ton = tons N/acre
# Then multiply by fertilizer $/ton for cost/acre
```

---

### 2.5 `data/series_data/NG_MOVE_STATE_A_EPG0_IM0_MMCF_A.xls` — State Imports

Annual data, 19 states, in MMcf. Only 53 rows (one per year). Not useful for the monthly ML model. Skip for MVP.

---

## 3. Key Trends & Signals

### Natural Gas Price Regimes (2018–2025)
| Period | Avg $/MMBtu | Driver |
|---|---|---|
| 2018–2020 | $2.00–$3.00 | Shale glut, low demand |
| 2021 | $3.50–$5.50 | Post-COVID demand recovery |
| 2022 | $4.40–$8.80 | Ukraine war, EU LNG demand, hot summer |
| 2023 | $1.49–$3.20 | Warm winter, storage glut |
| 2024 | $1.49–$3.18 | Record production, weak demand |
| 2025 | $2.78–$4.19 | Recovering, LNG exports rising |

### Nat Gas → Fertilizer Price Lag
The core insight of the project: fertilizer prices lag Henry Hub by **4–8 weeks** due to:
1. Production scheduling (Haber-Bosch process uses NG as feedstock)
2. Distribution pipeline delays
3. Contract pricing cycles

This is why `ng_lag1` through `ng_lag4` are the most important features in the XGBoost model.

### Storage as a Leading Indicator
Underground storage working gas is a **leading indicator** of nat gas prices:
- Storage injections peak Oct–Nov → prices fall
- Storage withdrawals peak Jan–Feb → prices rise
- 2025 pattern: storage reached 3.94M MMcf (Oct) → prices suppressed through fall

---

## 4. Feature Construction Quick Reference

```python
import pandas as pd

# Load primary data
ng_daily = pd.read_csv('data/natural-gas-prices/daily.csv')
ng_daily['Date'] = pd.to_datetime(ng_daily['Date'])
ng_daily['Price'] = ng_daily['Price'].ffill()
ng_daily = ng_daily.set_index('Date')

# Monthly spot (resample from daily OR use monthly CSV directly)
ng_monthly = ng_daily['Price'].resample('MS').mean().rename('ng_spot')

# Load storage from XLS
storage_raw = pd.read_excel(
    'data/series_data/NG_SUM_LSUM_DCU_NUS_M.xls',
    sheet_name='Data 4', header=2
)
storage_raw.columns = ['Date'] + list(storage_raw.columns[1:])
storage_raw['Date'] = pd.to_datetime(storage_raw.iloc[:, 0], errors='coerce')
storage_raw = storage_raw.dropna(subset=['Date']).set_index('Date')
storage_raw.index = storage_raw.index.to_period('M').to_timestamp()
working_gas = storage_raw.iloc[:, 3].rename('storage_working_gas_mmcf')  # Working Gas column

# Build feature store base
features = pd.DataFrame({'ng_spot': ng_monthly})
features = features.join(working_gas, how='left')

# Filter to model window
features = features[features.index >= '2018-01-01']

# Lag features
for lag in [1, 2, 3, 4]:
    features[f'ng_lag{lag}'] = features['ng_spot'].shift(lag)

# Rolling stats
features['ng_rolling_mean_3m'] = features['ng_spot'].rolling(3).mean()
features['ng_rolling_mean_6m'] = features['ng_spot'].rolling(6).mean()
features['ng_rolling_std_3m']  = features['ng_spot'].rolling(3).std()

# Momentum
features['ng_mom_1m'] = features['ng_spot'].pct_change(1)
features['ng_mom_3m'] = features['ng_spot'].pct_change(3)

# Season dummies
features['season_q1'] = (features.index.month.isin([1, 2, 3])).astype(int)
features['season_q2'] = (features.index.month.isin([4, 5, 6])).astype(int)
features['season_q3'] = (features.index.month.isin([7, 8, 9])).astype(int)
features['season_q4'] = (features.index.month.isin([10, 11, 12])).astype(int)

# Storage z-score (deviation from mean — indicates tightness)
features['storage_zscore'] = (
    (features['storage_working_gas_mmcf'] - features['storage_working_gas_mmcf'].mean())
    / features['storage_working_gas_mmcf'].std()
)
```

---

## 5. What Needs to Be Fetched Externally

The local data covers **nat gas prices and storage** well. The model's target variable (fertilizer prices) and futures data must be fetched:

| Data | Source | How |
|---|---|---|
| Urea, DAP, Ammonia prices | World Bank Pink Sheet | Download Excel from World Bank CMO page |
| NG futures (1m, 3m) | EIA API | `GET /v2/natural-gas/pri/sum/data/` with series `NG.RNGC1.D`, `NG.RNGC3.D` |
| USDA crop/fertilizer data | USDA ERS | Direct xlsx download |

See `scripts/seed_data.py` spec — these should be fetched once and cached to `data/raw/`.

---

## 6. Data Quality Summary

| Dataset | Quality | Notes |
|---|---|---|
| NG daily | ✅ Excellent | 1 null, trivial to fix |
| NG monthly | ✅ Excellent | Clean, no issues |
| NG industrial price | ✅ Good | r=0.896 with spot, runs through 2025-12 |
| Storage working gas | ✅ Excellent | No nulls, runs through 2025-12 |
| Agriculture dataset | ⚠️ Poor fit | Indian dataset, no time series, 50 rows only |
| State imports | ❌ Skip | Annual, not useful for monthly model |
