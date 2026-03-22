# Gas Forecast — Project Constitution v3
> **24-Hour Hackathon Spec | Natural Gas → Fertilizer Price Intelligence for Farmers**
> Last updated: March 2026 | Status: Active

---

## Table of Contents
1. [Product Vision](#1-product-vision)
2. [Core Insight](#2-core-insight)
3. [Who Uses This](#3-who-uses-this)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Datasets and APIs](#5-datasets-and-apis)
6. [Project Structure](#6-project-structure)
7. [Technology Stack](#7-technology-stack)
8. [Module Specifications](#8-module-specifications)
   - 8.1 [Data Ingestion Layer](#81-data-ingestion-layer)
   - 8.2 [Feature Store](#82-feature-store)
   - 8.3 [Fertilizer Price Forecasting Model](#83-fertilizer-price-forecasting-model)
   - 8.4 [Monte Carlo Simulation Engine](#84-monte-carlo-simulation-engine)
   - 8.5 [Farmer Exposure Calculator](#85-farmer-exposure-calculator)
   - 8.6 [Signal Engine](#86-signal-engine)
   - 8.7 [API Layer](#87-api-layer)
   - 8.8 [Dashboard](#88-dashboard)
9. [Data Models and Schemas](#9-data-models-and-schemas)
10. [Build Order and Time Budget](#10-build-order-and-time-budget)
11. [Scope Reduction Guide](#11-scope-reduction-guide)
12. [Demo Script](#12-demo-script)
13. [Environment Setup](#13-environment-setup)

---

## 1. Product Vision

**Gas Forecast** is a fertilizer price intelligence and early-warning tool for farmers and agricultural producers. It ingests natural gas market data, forecasts fertilizer prices 30/60/90 days forward using machine learning, runs Monte Carlo simulations to show the range of possible outcomes, and translates all of that into plain-English signals that help farmers make better input purchasing decisions.

**No futures trading. No loan products. No financial instruments.** Just clean data, honest forecasts, and actionable signals delivered in a way a farmer can actually use.

**The core value:** A commodity desk analyst monitors nat gas prices and adjusts their fertilizer purchasing calendar accordingly. Farmers don't have a commodity desk. Gas Forecast is that desk — distilled into a dashboard and a weekly digest.

**What a farmer sees:**
- "Urea prices are forecast to rise 14–22% over the next 60 days. If you haven't purchased spring inputs yet, consider acting soon."
- A price chart showing the historical nat gas → fertilizer relationship and where prices are headed
- A cost impact estimate: "At your farm size and crop mix, this price move translates to an estimated +$18,400 in input costs this season"
- A Monte Carlo scenario view: "In 80% of simulated price paths, urea ends up between $380 and $520/mt by June"

---

## 2. Core Insight

```
Henry Hub Natural Gas Price (week T)
            |
            |  Haber-Bosch process: nat gas is the feedstock for
            |  ammonia synthesis (~70-80% of production cost is nat gas)
            |
            |  4–8 week lag (production + distribution pipeline)
            v
Ammonia → Urea / DAP / Nitrate prices rise (week T+4 to T+8)
            |
            |  Farmer's fertilizer purchase price increases
            v
Input cost per acre rises by $X
            |
            |  Multiplied by: acreage × crop fertilizer intensity
            v
Seasonal purchasing decision: buy now, wait, or reduce application rate
```

**Why the lag is exploitable:**
- Nat gas prices move daily and are publicly available
- Fertilizer prices respond with a 4–8 week delay due to production scheduling and distribution
- That window is long enough for a farmer to act — pre-purchase, lock in a supplier contract, or adjust planting plans
- This is the information asymmetry Gas Forecast closes

**Crop-level fertilizer sensitivity (drives the exposure calculator):**

| Crop | N lbs/acre | Fertilizer sensitivity | Notes |
|---|---|---|---|
| Corn | ~150 | Very high | Primary target — most exposure |
| Wheat | ~90 | High | Important for Plains states |
| Cotton | ~80 | High | |
| Sorghum | ~80 | Moderate-high | |
| Soybeans | ~5 | Very low | Fixes atmospheric nitrogen |
| Hay/Alfalfa | ~20 | Low | |
| Livestock only | 0 | None | No direct fertilizer exposure |

---

## 3. Who Uses This

### Primary User: Farmer / Agricultural Producer

A corn or wheat farmer managing 200–5,000 acres. Makes fertilizer purchasing decisions 1–3 times per year, typically in fall (pre-purchase for spring planting) or early spring. Has limited access to commodity market analysis. Makes decisions based on supplier quotes, neighbor conversations, and gut feel.

**What they want to know:**
- Are prices going up or down over the next 60 days?
- How much will this actually cost me, in dollars, for my farm?
- When is the right time to buy?

**How they interact with Gas Forecast:**
- Weekly email digest with current signal and cost estimate
- Dashboard for deeper exploration when they want to dig in
- Input their acreage and crop type once; the tool personalizes estimates from there

### Secondary User: Agricultural Extension Agent / Co-op Advisor

Serves 50–200 farmers in a region. Uses Gas Forecast to advise their farmers on input purchasing timing. Values the regional breakdown and historical context more than the individual farm calculator.

### What this product is NOT:
- Not a trading platform
- Not a loan or financial product
- Not a price guarantee
- Not investment advice

The output is informational. Farmers use it the same way they use a weather forecast — it informs their decision, it doesn't make it for them.

---

## 4. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│   EIA API           World Bank          USDA ERS                 │
│   (nat gas daily)   (fertilizer monthly) (crop use + prices)     │
└──────────┬──────────────────┬────────────────────┬──────────────┘
           │                  │                    │
           v                  v                    v
┌──────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                          │
│   Pull → Normalize → Align to monthly → Cache to data/raw/      │
│   Forward-fill missing values → Save to data/processed/          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────────┐
│                        FEATURE STORE                             │
│   feature_store.parquet                                          │
│   Lagged nat gas prices | Rolling stats | Futures curve shape    │
│   Fertilizer prices | Seasonal dummies | Transmission ratios     │
└──────────┬────────────────────────────────────────┬─────────────┘
           │                                        │
           v                                        v
┌──────────────────────────┐          ┌─────────────────────────────┐
│  FERTILIZER PRICE        │          │  FARMER EXPOSURE            │
│  FORECASTING MODEL       │          │  CALCULATOR                 │
│                          │          │                             │
│  XGBoost regressor       │          │  Crop type × acreage        │
│  Walk-forward CV         │          │  × fertilizer intensity     │
│  ARIMA baseline          │          │  = dollar impact estimate   │
│                          │          │                             │
│  Output:                 │          │  Output:                    │
│  urea_t30/t60/t90        │          │  cost_increase_per_acre     │
│  + residual distribution │          │  total_season_cost_delta    │
└──────────┬───────────────┘          └──────────────┬──────────────┘
           │                                         │
           v                                         │
┌──────────────────────────┐                         │
│  MONTE CARLO ENGINE      │                         │
│                          │                         │
│  10,000 price paths      │                         │
│  from forecast residuals │                         │
│                          │                         │
│  Output:                 │                         │
│  p10/p50/p90 price bands │                         │
│  probability dist plots  │                         │
└──────────┬───────────────┘                         │
           │                                         │
           └──────────────────┬──────────────────────┘
                              │
                              v
┌──────────────────────────────────────────────────────────────────┐
│                       SIGNAL ENGINE                              │
│   Combines forecast + uncertainty + exposure into:               │
│   buy_signal | timing_recommendation | plain_English_rationale   │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                              │
│   /forecast  /monte-carlo  /exposure  /signal  /historical       │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────────┐
│                  STREAMLIT DASHBOARD                             │
│   Signal card | Price chart | Forecast cone | Cost calculator    │
│   Monte Carlo histogram | Historical correlation view            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Datasets and APIs

### 5.1 EIA API — Henry Hub Natural Gas Prices
- **URL:** `https://api.eia.gov/v2/natural-gas/pri/sum/data/`
- **Auth:** Free API key — register instantly at `https://www.eia.gov/opendata/register.php`
- **Series IDs:**
  - `NG.RNGWHHD.D` — daily Henry Hub spot price ($/MMBtu)
  - `NG.RNGC1.D` — 1-month futures contract
  - `NG.RNGC3.D` — 3-month futures contract
- **Format:** JSON
- **Frequency:** Daily (we resample to monthly for modeling)
- **History:** 1997–present
- **Rate limit:** 1,000 requests/hour — well above our needs

```python
# Example request parameters
{
    "api_key": EIA_API_KEY,
    "frequency": "monthly",
    "data[0]": "value",
    "facets[series][]": "NG.RNGWHHD.D",
    "start": "2018-01",
    "end": "2024-12",
    "sort[0][column]": "period",
    "sort[0][direction]": "asc",
    "offset": 0,
    "length": 5000
}
```

### 5.2 World Bank Pink Sheet — Fertilizer Prices
- **URL:** `https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx`
- **Auth:** None — direct download
- **Columns used:** `Urea_EEurope` ($/mt), `DAP` ($/mt), `Ammonia_W_Europe` ($/mt)
- **Format:** Excel (.xlsx), monthly
- **History:** 1960–present
- **Use:** Primary target variable for the forecasting model; source of truth for fertilizer price history

### 5.3 USDA ERS — Fertilizer Use by Crop
- **URL:** `https://www.ers.usda.gov/data-products/fertilizer-use-and-price/`
- **Direct file:** `https://www.ers.usda.gov/webdocs/DataFiles/50048/FertilizerUse.xlsx`
- **Auth:** None
- **Key data:** Nitrogen, phosphate, and potash application rates in lbs per harvested acre, broken down by crop type and year
- **Use:** Powers the Farmer Exposure Calculator — converts fertilizer $/mt into $/acre for each crop type

### 5.4 USDA ERS — Crop Prices and Farm Revenue
- **URL:** `https://www.ers.usda.gov/data-products/feed-grains-database/`
- **Use:** Current corn, wheat, soybean prices — used to contextualize the fertilizer cost increase as a percentage of expected crop revenue
- **Format:** Excel, annual/monthly

### 5.5 FRED — Additional Macro Context (Optional)
- **URL:** `https://fred.stlouisfed.org/` (no auth needed for data downloads)
- **Series of interest:** `DHHNGSP` (Henry Hub, daily), `PCU3253132531` (fertilizer PPI)
- **Use:** Cross-validation of EIA data; PPI series as an alternative fertilizer price proxy
- **Note:** If EIA API has issues during the hackathon, FRED is the backup

### 5.6 Data Caching Strategy — Pull Once, Use Everywhere

Every API call happens exactly once. All downstream modules read from `data/raw/`. This makes the pipeline deterministic and immune to API outages during the hackathon.

```
scripts/seed_data.py    ← run this first, run it once
       │
       ├── calls EIA API        → data/raw/eia_ng_spot.csv
       ├── downloads World Bank → data/raw/worldbank_fertilizer.csv
       ├── downloads USDA ERS   → data/raw/usda_fertilizer_use.csv
       ├── downloads USDA crops → data/raw/usda_crop_prices.csv
       └── writes               → data/raw/MANIFEST.json
```

If a file already exists in `data/raw/` and is less than 24 hours old per `MANIFEST.json`, skip the pull. This means calling `seed_data.py` multiple times is safe.

---

## 6. Project Structure

```
gas_forecast/
├── GAS_FORECAST_SPEC.md             # This file
├── README.md                      # Judges quick start — keep under 20 lines
├── .env                           # API keys — never commit
├── .env.example                   # Safe to commit
├── requirements.txt
│
├── data/
│   ├── raw/                       # Cached source data — never modified after pull
│   │   ├── eia_ng_spot.csv
│   │   ├── eia_ng_futures.csv
│   │   ├── worldbank_fertilizer.csv
│   │   ├── usda_fertilizer_use.csv
│   │   ├── usda_crop_prices.csv
│   │   └── MANIFEST.json
│   ├── processed/
│   │   ├── feature_store.parquet  # Aligned, engineered monthly time series
│   │   └── backtest_results.parquet
│   └── models/
│       ├── xgb_urea_forecast.pkl
│       ├── xgb_dap_forecast.pkl
│       └── model_metadata.json    # residual_std, training window, feature list
│
├── src/
│   ├── __init__.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── eia.py                 # EIA API client
│   │   ├── worldbank.py           # World Bank xlsx parser
│   │   ├── usda.py                # USDA ERS parsers (fertilizer use + crop prices)
│   │   └── pipeline.py            # Orchestrator: pull, align, cache
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── engineer.py            # All feature engineering logic
│   │   ├── crop_costs.py          # Fertilizer cost-per-acre by crop type
│   │   └── store.py               # Read/write feature_store.parquet
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── forecaster.py          # XGBoost training, walk-forward CV, serialization
│   │   ├── baseline.py            # ARIMA baseline for comparison
│   │   └── evaluate.py            # Metrics: RMSE, MAE, directional accuracy
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   └── monte_carlo.py         # Monte Carlo engine over forecast residuals
│   │
│   ├── exposure/
│   │   ├── __init__.py
│   │   └── calculator.py          # Per-farm fertilizer cost impact estimation
│   │
│   ├── signals/
│   │   ├── __init__.py
│   │   └── engine.py              # Buy/wait signal generation + plain-English rationale
│   │
│   └── api/
│       ├── __init__.py
│       ├── main.py                # FastAPI app entrypoint
│       ├── routes/
│       │   ├── forecast.py
│       │   ├── monte_carlo.py
│       │   ├── exposure.py
│       │   ├── signal.py
│       │   └── historical.py
│       └── schemas.py             # All Pydantic request/response models
│
├── dashboard/
│   └── app.py                     # Streamlit farmer-facing UI
│
├── notebooks/
│   ├── 01_eda.ipynb               # Nat gas vs fertilizer EDA, lag analysis
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_evaluation.ipynb  # Walk-forward CV results, feature importance
│   └── 04_monte_carlo_demo.ipynb  # Monte Carlo output visualization
│
└── scripts/
    ├── seed_data.py               # Pull + cache all raw data (run first)
    └── train_models.py            # Train + serialize XGBoost models
```

---

## 7. Technology Stack

### Core Language
- **Python 3.11+**

### Data and ML
| Library | Version | Purpose |
|---|---|---|
| `pandas` | 2.2.x | All data manipulation, time series alignment |
| `numpy` | 1.26.x | Monte Carlo draws, numerical operations |
| `xgboost` | 2.0.x | Primary fertilizer price forecasting model |
| `scikit-learn` | 1.4.x | Preprocessing, `TimeSeriesSplit` for walk-forward CV |
| `statsmodels` | 0.14.x | ARIMA baseline, stationarity tests |
| `scipy` | 1.13.x | Fitting residual distributions for Monte Carlo |
| `pyarrow` | latest | Parquet read/write for feature store |
| `openpyxl` | 3.x | Reading World Bank and USDA xlsx files |

### API and Backend
| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.x | REST API framework |
| `uvicorn` | 0.29.x | ASGI server |
| `pydantic` | 2.x | Request/response schema validation |
| `httpx` | 0.27.x | Async HTTP for EIA API calls |
| `python-dotenv` | 1.x | `.env` file loading |

### Frontend
| Tool | Version | Purpose |
|---|---|---|
| `streamlit` | 1.33.x | Farmer-facing dashboard |
| `plotly` | 5.x | All interactive charts |

### Storage
- **Flat files only** — CSV for raw data, Parquet for processed feature store and model artifacts
- No database. For a 24-hour build, any database is overhead, not value.

---

## 8. Module Specifications

### 8.1 Data Ingestion Layer

**Orchestrator:** `src/ingestion/pipeline.py`

Pulls all external sources, normalizes to monthly frequency, caches to `data/raw/`, and returns a dict of clean DataFrames ready for feature engineering.

**Key design rules:**
- All functions are idempotent — calling them twice does not corrupt data
- Resample EIA daily prices to monthly mean (fertilizer decisions are monthly)
- Forward-fill up to 2 consecutive missing months (World Bank data has occasional gaps)
- Do not interpolate backward — never let future data fill past gaps

```python
# src/ingestion/pipeline.py

def run_ingestion(force_refresh: bool = False) -> dict[str, pd.DataFrame]:
    """
    Returns dict with keys:
      'ng_spot'       — monthly Henry Hub spot price, $/MMBtu, DatetimeIndex
      'ng_futures_1m' — monthly 1-month futures price
      'ng_futures_3m' — monthly 3-month futures price
      'urea'          — monthly urea price, $/mt
      'dap'           — monthly DAP price, $/mt
      'ammonia'       — monthly ammonia price, $/mt
      'crop_prices'   — monthly corn/wheat/soybean prices
    All DataFrames share a common monthly DatetimeIndex from 2018-01 to present.
    """
```

```python
# src/ingestion/eia.py

class EIAClient:
    BASE_URL = "https://api.eia.gov/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_series(self, series_id: str, start: str, end: str,
                   frequency: str = "monthly") -> pd.Series:
        """
        Fetches a single EIA series. Returns pd.Series with DatetimeIndex.
        Handles pagination automatically (EIA caps at 5000 rows per request).
        Caches result to data/raw/{series_id}.csv.
        """

    def get_ng_spot(self, start="2018-01", end="2024-12") -> pd.Series:
        return self.get_series("NG.RNGWHHD.D", start, end)

    def get_ng_futures(self, contract: int = 1,
                       start="2018-01", end="2024-12") -> pd.Series:
        series_map = {1: "NG.RNGC1.D", 3: "NG.RNGC3.D"}
        return self.get_series(series_map[contract], start, end)
```

```python
# src/ingestion/worldbank.py

def load_fertilizer_prices(filepath: str) -> pd.DataFrame:
    """
    Parses World Bank CMO Pink Sheet Excel file.
    Extracts Urea, DAP, Ammonia columns.
    Returns DataFrame with DatetimeIndex, columns: ['urea', 'dap', 'ammonia'].
    All values in $/metric ton.
    Handles the World Bank's non-standard header rows automatically.
    """
```

---

### 8.2 Feature Store

**File:** `src/features/engineer.py`

Takes the dict of raw DataFrames from ingestion and produces a single, wide, monthly-indexed DataFrame saved as `data/processed/feature_store.parquet`. This is the sole input to the forecasting model.

**Complete feature table:**

| Column | Type | Description |
|---|---|---|
| `ng_spot` | float | Henry Hub monthly mean spot price $/MMBtu |
| `ng_futures_1m` | float | 1-month futures price |
| `ng_futures_3m` | float | 3-month futures price |
| `urea` | float | Urea price $/mt |
| `dap` | float | DAP price $/mt |
| `ng_lag1` | float | `ng_spot.shift(1)` — 1 month ago |
| `ng_lag2` | float | `ng_spot.shift(2)` — 2 months ago |
| `ng_lag3` | float | `ng_spot.shift(3)` — 3 months ago |
| `ng_lag4` | float | `ng_spot.shift(4)` — 4 months ago |
| `ng_rolling_mean_3m` | float | `ng_spot.rolling(3).mean()` |
| `ng_rolling_mean_6m` | float | `ng_spot.rolling(6).mean()` |
| `ng_rolling_std_3m` | float | 3-month realized volatility |
| `ng_rolling_std_6m` | float | 6-month realized volatility |
| `ng_mom_1m` | float | `ng_spot.pct_change(1)` — 1-month % change |
| `ng_mom_3m` | float | `ng_spot.pct_change(3)` — 3-month % change |
| `ng_mom_6m` | float | `ng_spot.pct_change(6)` — 6-month % change |
| `futures_slope` | float | `(ng_futures_3m - ng_spot) / ng_spot` — contango indicator |
| `urea_ng_ratio` | float | `urea / ng_spot` — transmission ratio |
| `urea_lag1` | float | Urea price 1 month ago |
| `urea_rolling_mean_3m` | float | Urea 3-month rolling mean |
| `season_q1` | int | Quarter 1 dummy (Jan–Mar) — spring planting season |
| `season_q2` | int | Quarter 2 dummy (Apr–Jun) |
| `season_q3` | int | Quarter 3 dummy (Jul–Sep) |
| `season_q4` | int | Quarter 4 dummy (Oct–Dec) — fall pre-purchase season |
| `target_urea_t1` | float | Urea price 1 month forward — **training target** |
| `target_urea_t2` | float | Urea price 2 months forward — **training target** |
| `target_urea_t3` | float | Urea price 3 months forward — **training target** |

**Critical notes:**
- Target columns use `urea.shift(-1)`, `urea.shift(-2)`, `urea.shift(-3)` — negative shifts look forward in time
- Drop all rows where any target is NaN before training
- Never include target columns as input features — they would leak future information
- Features are computed from `ng_spot` and `urea` only; no target information is used in feature construction

---

### 8.3 Fertilizer Price Forecasting Model

**File:** `src/models/forecaster.py`

**Task:** Given the current feature vector (a single row from the feature store representing today), predict urea prices 1, 2, and 3 months forward. Train three separate XGBoost models — one per horizon.

#### Training Protocol

**Data splits:**
```
Full dataset:    2018-01 → 2024-12  (84 months)
Training window: 2018-01 → 2021-06  (42 months)
Validation:      2021-07 → 2022-12  (18 months) ← includes the 2022 spike
Test holdout:    2023-01 → 2024-12  (24 months) ← never touched until final evaluation
```

**Walk-forward cross-validation (mandatory — do not use random split):**

Time series data has temporal structure. A random train/test split leaks future information into the training set and produces artificially high accuracy scores. Use `TimeSeriesSplit` from scikit-learn, which always trains on past data and validates on future data.

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5, gap=1)
# gap=1 ensures at least 1 month between train end and validation start
# This prevents any overlap that could cause leakage at boundaries

scores = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train_val)):
    X_tr, X_val = X_train_val.iloc[train_idx], X_train_val.iloc[val_idx]
    y_tr, y_val = y_train_val.iloc[train_idx], y_train_val.iloc[val_idx]

    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val)
    mae  = mean_absolute_error(y_val, preds)
    rmse = root_mean_squared_error(y_val, preds)
    dir_acc = directional_accuracy(y_val, preds, y_val.shift(1))
    scores.append({"fold": fold, "mae": mae, "rmse": rmse, "dir_acc": dir_acc})
```

**XGBoost hyperparameters (starting point):**
```python
XGB_PARAMS = {
    "n_estimators":     300,
    "max_depth":        4,       # Shallow trees — prevents overfitting on small dataset
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "objective":        "reg:squarederror",
    "random_state":     42,
    "n_jobs":           -1
}
```

**ARIMA baseline (required for model credibility):**

Train a `SARIMAX(1,1,1)(1,1,1,12)` on urea prices alone. If XGBoost doesn't outperform ARIMA on both RMSE and directional accuracy by a meaningful margin, the added features are not helping and should be reviewed. Expected result: XGBoost should beat ARIMA by 10–20% on RMSE, especially on the 60 and 90 day horizons where the nat gas lag signal is most useful.

```python
from statsmodels.tsa.statespace.sarimax import SARIMAX

arima_model = SARIMAX(
    y_train,
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 12),
    enforce_stationarity=False
).fit(disp=False)
```

**Residual distribution (critical for Monte Carlo):**

After walk-forward CV, collect all out-of-sample prediction errors. Fit a normal distribution to these residuals. Save `residual_mean` and `residual_std` in `data/models/model_metadata.json`. The Monte Carlo engine draws from this distribution.

```python
residuals = y_val_all - preds_all   # Collected across all CV folds
residual_mean = residuals.mean()    # Should be near 0 if model is unbiased
residual_std  = residuals.std()     # This is the key uncertainty parameter

# Save alongside model
metadata = {
    "residual_mean_t1": ...,
    "residual_std_t1":  ...,
    "residual_mean_t2": ...,
    "residual_std_t2":  ...,
    "residual_mean_t3": ...,
    "residual_std_t3":  ...,
    "training_window_start": "2018-01",
    "training_window_end":   "2021-06",
    "val_rmse_t1": ...,
    "val_rmse_t2": ...,
    "val_rmse_t3": ...,
    "val_dir_acc_t2": ...,  # Most important metric — directional accuracy at 60 days
}
```

**Model output:**
```python
@dataclass
class PriceForecast:
    as_of_date:          date
    urea_current:        float   # Current observed price $/mt
    urea_forecast_t1:    float   # 1 month forward
    urea_forecast_t2:    float   # 2 months forward
    urea_forecast_t3:    float   # 3 months forward
    pct_change_t2:       float   # % change from current to t2 — primary signal
    directional_signal:  str     # "RISING" | "FALLING" | "STABLE"
    confidence:          float   # Based on directional accuracy from CV
    ng_spot_current:     float   # Henry Hub current price
    ng_change_30d:       float   # How much nat gas has moved recently
```

---

### 8.4 Monte Carlo Simulation Engine

**File:** `src/simulation/monte_carlo.py`

**Purpose:** The point forecast tells a farmer "urea will be $480/mt in 60 days." The Monte Carlo tells them "in 80% of simulated scenarios, urea will be between $420 and $540/mt." This is honest uncertainty quantification, not false precision.

**Method:**

The residual distribution from walk-forward CV represents the model's real-world forecast error, measured on data it was not trained on. Drawing from this distribution generates realistic price scenarios consistent with actual model performance.

```python
def run_monte_carlo(
    forecast: PriceForecast,
    model_metadata: dict,
    n_simulations: int = 10_000,
    random_seed: int = 42
) -> MonteCarloResult:
    """
    For each of n_simulations paths:
      1. Draw forecast error for t1 from N(residual_mean_t1, residual_std_t1)
      2. Draw forecast error for t2 from N(residual_mean_t2, residual_std_t2)
      3. Draw forecast error for t3 from N(residual_mean_t3, residual_std_t3)
      4. Add errors to point forecasts:
           sim_t1[i] = forecast.urea_forecast_t1 + error_t1[i]
           sim_t2[i] = forecast.urea_forecast_t2 + error_t2[i]
           sim_t3[i] = forecast.urea_forecast_t3 + error_t3[i]
      5. Clip to physically plausible range (price cannot go below ~$100/mt)

    Aggregate across all paths:
      Compute percentiles at each horizon: p10, p25, p50, p75, p90
      Compute probability of price being above current price at each horizon
      Compute probability of >10% increase (meaningful stress threshold)

    Implementation note: use vectorized numpy, NOT a Python for loop.
    10,000 draws with a loop is slow; vectorized is instantaneous.
    """
    rng = np.random.default_rng(random_seed)

    # Vectorized draws — all 10,000 at once
    errors_t1 = rng.normal(model_metadata["residual_mean_t1"],
                           model_metadata["residual_std_t1"], n_simulations)
    errors_t2 = rng.normal(model_metadata["residual_mean_t2"],
                           model_metadata["residual_std_t2"], n_simulations)
    errors_t3 = rng.normal(model_metadata["residual_mean_t3"],
                           model_metadata["residual_std_t3"], n_simulations)

    sim_t1 = np.clip(forecast.urea_forecast_t1 + errors_t1, 100, 2000)
    sim_t2 = np.clip(forecast.urea_forecast_t2 + errors_t2, 100, 2000)
    sim_t3 = np.clip(forecast.urea_forecast_t3 + errors_t3, 100, 2000)

    return MonteCarloResult(
        n_simulations=n_simulations,
        # T+1 (30 day)
        p10_t1=np.percentile(sim_t1, 10),
        p25_t1=np.percentile(sim_t1, 25),
        p50_t1=np.percentile(sim_t1, 50),
        p75_t1=np.percentile(sim_t1, 75),
        p90_t1=np.percentile(sim_t1, 90),
        # T+2 (60 day)
        p10_t2=np.percentile(sim_t2, 10),
        p25_t2=np.percentile(sim_t2, 25),
        p50_t2=np.percentile(sim_t2, 50),
        p75_t2=np.percentile(sim_t2, 75),
        p90_t2=np.percentile(sim_t2, 90),
        # T+3 (90 day)
        p10_t3=np.percentile(sim_t3, 10),
        p50_t3=np.percentile(sim_t3, 50),
        p90_t3=np.percentile(sim_t3, 90),
        # Probability metrics
        prob_rising_t2=float(np.mean(sim_t2 > forecast.urea_current)),
        prob_10pct_increase_t2=float(np.mean(sim_t2 > forecast.urea_current * 1.10)),
        prob_20pct_increase_t2=float(np.mean(sim_t2 > forecast.urea_current * 1.20)),
        # Raw distributions for plotting
        sim_t2_distribution=sim_t2,   # Full 10,000-value array
    )
```

**MonteCarloResult output:** The `sim_t2_distribution` array is passed to the dashboard to render a histogram showing the full spread of possible price outcomes. The percentile bands are used for the forecast cone on the price chart.

---

### 8.5 Farmer Exposure Calculator

**File:** `src/exposure/calculator.py`

**Purpose:** Translate an abstract fertilizer price forecast into a concrete dollar figure for a specific farm. This is what makes the product personally relevant to a farmer instead of just another commodity chart.

**Fertilizer intensity lookup (from USDA ERS):**
```python
# Approximate nitrogen application rates, lbs N per harvested acre
# Source: USDA ERS Fertilizer Use and Price data
NITROGEN_INTENSITY = {
    "corn":           150,
    "wheat":           90,
    "cotton":          80,
    "sorghum":         80,
    "rice":            95,
    "soybeans":         5,    # Biological N fixation — nearly immune to urea prices
    "hay_alfalfa":     20,
    "other_crops":     60,    # Default fallback
    "livestock_only":   0,
}

# Urea nitrogen content by weight
UREA_N_CONTENT = 0.46   # 46% nitrogen by weight — standard granular urea

def urea_cost_per_acre(crop: str, urea_price_per_mt: float) -> float:
    """
    Converts urea $/mt into fertilizer cost per acre for a given crop.
    
    Formula:
      lbs_n_needed = NITROGEN_INTENSITY[crop]
      lbs_urea_needed = lbs_n_needed / UREA_N_CONTENT
      tons_urea_needed = lbs_urea_needed / 2204.6   (lbs per metric ton)
      cost = tons_urea_needed * urea_price_per_mt
    """
    lbs_n = NITROGEN_INTENSITY.get(crop, NITROGEN_INTENSITY["other_crops"])
    if lbs_n == 0:
        return 0.0
    lbs_urea = lbs_n / UREA_N_CONTENT
    mt_urea = lbs_urea / 2204.6
    return mt_urea * urea_price_per_mt
```

**Exposure calculation:**
```python
def compute_farm_exposure(
    crop: str,
    acreage: int,
    urea_price_current: float,
    urea_price_forecast: float,
    pre_purchased_pct: float = 0.0    # Fraction of inputs already bought at current price
) -> FarmExposure:
    """
    Computes the dollar impact of the forecast price change on a specific farm.

    pre_purchased_pct: If a farmer already bought 40% of their inputs in the fall,
    only 60% of their acreage is exposed to the forecast price change.
    """
    current_cost_per_acre  = urea_cost_per_acre(crop, urea_price_current)
    forecast_cost_per_acre = urea_cost_per_acre(crop, urea_price_forecast)
    cost_increase_per_acre = forecast_cost_per_acre - current_cost_per_acre

    exposed_acreage        = acreage * (1.0 - pre_purchased_pct)
    total_cost_increase    = cost_increase_per_acre * exposed_acreage

    return FarmExposure(
        crop=crop,
        acreage=acreage,
        exposed_acreage=exposed_acreage,
        current_cost_per_acre=current_cost_per_acre,
        forecast_cost_per_acre=forecast_cost_per_acre,
        cost_increase_per_acre=cost_increase_per_acre,
        total_cost_increase=total_cost_increase,
        pct_increase=cost_increase_per_acre / current_cost_per_acre if current_cost_per_acre > 0 else 0.0
    )
```

**Monte Carlo exposure distribution:**

The exposure calculator also accepts the Monte Carlo distribution to produce a range of cost outcomes:

```python
def compute_exposure_distribution(
    crop: str,
    acreage: int,
    urea_price_current: float,
    mc_result: MonteCarloResult,
    pre_purchased_pct: float = 0.0
) -> ExposureDistribution:
    """
    Runs compute_farm_exposure over the full MC sim_t2_distribution.
    Returns p10, p50, p90 cost increase estimates.
    Gives farmer: "Your cost increase will likely be between $X and $Y."
    """
    exposed_acreage = acreage * (1.0 - pre_purchased_pct)
    cost_increases  = (
        (mc_result.sim_t2_distribution / 2204.6 / UREA_N_CONTENT
         * NITROGEN_INTENSITY.get(crop, 60) - urea_cost_per_acre(crop, urea_price_current))
        * exposed_acreage
    )
    return ExposureDistribution(
        p10_cost_increase=float(np.percentile(cost_increases, 10)),
        p50_cost_increase=float(np.percentile(cost_increases, 50)),
        p90_cost_increase=float(np.percentile(cost_increases, 90)),
        prob_any_increase=float(np.mean(cost_increases > 0)),
    )
```

---

### 8.6 Signal Engine

**File:** `src/signals/engine.py`

**Purpose:** Combine the forecast, Monte Carlo, and exposure into a single plain-English recommendation. This is the last step before the dashboard — it converts numbers into words.

```python
def generate_signal(
    forecast: PriceForecast,
    mc_result: MonteCarloResult,
    exposure: FarmExposure
) -> FarmerSignal:
    """
    Signal logic:

    BUY_NOW:
      forecast.pct_change_t2 > 0.08
      AND mc_result.prob_rising_t2 > 0.65
      Rationale: "Prices forecast to rise significantly with high confidence.
                  Consider purchasing inputs soon."

    CONSIDER_BUYING:
      forecast.pct_change_t2 > 0.04
      OR mc_result.prob_rising_t2 > 0.55
      Rationale: "Prices lean upward but uncertainty is moderate.
                  Partial pre-purchase may make sense."

    WAIT:
      forecast.pct_change_t2 < -0.04
      AND mc_result.prob_rising_t2 < 0.40
      Rationale: "Prices forecast to soften. Waiting may reduce input costs."

    NEUTRAL:
      Default — prices stable within noise range
      Rationale: "No strong price signal. Monitor weekly."
    """
```

**Output:**
```python
@dataclass
class FarmerSignal:
    signal:          str    # "BUY_NOW" | "CONSIDER_BUYING" | "WAIT" | "NEUTRAL"
    urgency:         str    # "HIGH" | "MEDIUM" | "LOW"
    rationale:       str    # Plain English, 1–2 sentences
    key_driver:      str    # "Nat gas up 18% in 30 days" — the one data point that matters
    forecast_summary: str   # "Urea forecast: $480/mt in 60 days (+14%)"
    exposure_summary: str   # "Estimated cost impact: +$18,400 for your 500-acre corn farm"
    confidence:      float  # 0.0 – 1.0, from model directional accuracy
    as_of_date:      date
```

---

### 8.7 API Layer

**File:** `src/api/main.py`

**Framework:** FastAPI, port 8000. Streamlit dashboard calls these endpoints.

**Endpoints:**

```
GET  /health
     Returns: model loaded status, last data pull time, current nat gas price

GET  /forecast
     Returns: PriceForecast — current nat gas price, urea forecasts t1/t2/t3,
              directional signal, confidence

GET  /monte-carlo
     Query params: n_simulations (default 10000)
     Returns: MonteCarloResult — percentile bands at t1/t2/t3,
              probability metrics, full t2 distribution as array

POST /exposure
     Body: { crop, acreage, pre_purchased_pct }
     Returns: FarmExposure + ExposureDistribution using current MC result

GET  /signal
     Query params: crop, acreage, pre_purchased_pct (optional)
     Returns: FarmerSignal — complete plain-English recommendation

GET  /historical
     Query params: start (default "2018-01"), end (default "2024-12")
     Returns: historical nat gas and urea prices for chart rendering
```

**Startup behavior:**
On startup, load `data/models/xgb_urea_forecast.pkl` and `data/models/model_metadata.json`. Pre-compute and cache the current forecast and Monte Carlo result. Subsequent requests use the cached result unless the data has been refreshed.

**CORS:** `allow_origins=["*"]` — needed for Streamlit to call the API.

---

### 8.8 Dashboard

**File:** `dashboard/app.py`

**Framework:** Streamlit — single file, farmer as primary user

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Gas Forecast | Fertilizer Price Intelligence             │
├──────────────────────────────┬──────────────────────────┤
│  SIDEBAR — Your Farm         │  MAIN PANEL              │
│  ─────────────────           │                          │
│  Crop type: [dropdown]       │  SIGNAL CARD             │
│  Acreage: [number input]     │  ┌────────────────────┐  │
│  Pre-purchased: [slider 0-1] │  │  BUY NOW           │  │
│                              │  │  Confidence: 74%   │  │
│  [Update My Estimate]        │  │  "Nat gas up 18%   │  │
│                              │  │  in 30 days.       │  │
│  ─────────────────           │  │  Urea likely to    │  │
│  NAT GAS TODAY               │  │  follow."          │  │
│  $3.84/MMBtu                 │  └────────────────────┘  │
│  +18% vs 30 days ago         │                          │
│                              │  YOUR COST ESTIMATE      │
│  UREA TODAY                  │  +$18,400 this season    │
│  $420/mt                     │  (80% range: $9k–$28k)   │
│  Forecast t60: $480/mt (+14%)│                          │
├──────────────────────────────┴──────────────────────────┤
│  PRICE CHART (Plotly, full width)                       │
│  Dual y-axis: nat gas (left) + urea (right)             │
│  Date range slider                                      │
│  Shaded forecast cone: p10/p50/p90 from Monte Carlo     │
│  Annotation: "2022 spike — urea hit $870/mt"            │
├─────────────────────────────────────────────────────────┤
│  MONTE CARLO HISTOGRAM (Plotly)                         │
│  X-axis: simulated urea price at 60 days                │
│  Y-axis: frequency across 10,000 paths                  │
│  Vertical lines: current price, p10, p50, p90           │
│  Subtitle: "10,000 simulated price paths"               │
├─────────────────────────────────────────────────────────┤
│  HISTORICAL CONTEXT                                     │
│  "When nat gas moved >15% in 30 days (happened 8 times  │
│  since 2018), urea was higher 60 days later in 7 of 8." │
│  Small table: date | ng_change | urea_change_60d        │
└─────────────────────────────────────────────────────────┘
```

**Key Streamlit implementation patterns:**
```python
import streamlit as st
import plotly.graph_objects as go
import httpx

API_BASE = "http://localhost:8000"

# Cache API calls — re-fetching on every slider move is slow
@st.cache_data(ttl=300)
def get_forecast():
    return httpx.get(f"{API_BASE}/forecast").json()

@st.cache_data(ttl=300)
def get_monte_carlo():
    return httpx.get(f"{API_BASE}/monte-carlo").json()

@st.cache_data(ttl=3600)
def get_historical():
    return httpx.get(f"{API_BASE}/historical").json()

# Sidebar inputs
with st.sidebar:
    st.header("Your farm")
    crop = st.selectbox("Primary crop", list(NITROGEN_INTENSITY.keys()))
    acreage = st.number_input("Acres planted", min_value=1, value=500, step=50)
    pre_pct = st.slider("Inputs pre-purchased (%)", 0, 100, 0) / 100

# Exposure call updates when sidebar changes — no caching here
exposure = httpx.post(f"{API_BASE}/exposure",
    json={"crop": crop, "acreage": acreage, "pre_purchased_pct": pre_pct}).json()
```

**Forecast cone chart (the most important visualization):**
```python
def build_price_chart(historical: dict, forecast: dict, mc: dict) -> go.Figure:
    fig = go.Figure()

    # Historical nat gas (left axis)
    fig.add_trace(go.Scatter(
        x=historical["dates"], y=historical["ng_spot"],
        name="Nat gas ($/MMBtu)", yaxis="y1",
        line=dict(color="#378ADD", width=1.5)
    ))

    # Historical urea (right axis)
    fig.add_trace(go.Scatter(
        x=historical["dates"], y=historical["urea"],
        name="Urea ($/mt)", yaxis="y2",
        line=dict(color="#1D9E75", width=1.5)
    ))

    # Forecast cone — p10/p90 shaded, p50 line
    future_dates = [forecast["as_of_date"] + timedelta(days=30*i) for i in [1,2,3]]
    fig.add_trace(go.Scatter(
        x=future_dates + future_dates[::-1],
        y=[mc["p90_t1"], mc["p90_t2"], mc["p90_t3"],
           mc["p10_t3"], mc["p10_t2"], mc["p10_t1"]],
        fill="toself", fillcolor="rgba(29,158,117,0.15)",
        line=dict(width=0), name="80% confidence band", yaxis="y2"
    ))
    fig.add_trace(go.Scatter(
        x=future_dates,
        y=[mc["p50_t1"], mc["p50_t2"], mc["p50_t3"]],
        name="Median forecast", yaxis="y2",
        line=dict(color="#1D9E75", width=2, dash="dash")
    ))

    fig.update_layout(
        yaxis=dict(title="Nat gas ($/MMBtu)"),
        yaxis2=dict(title="Urea ($/mt)", overlaying="y", side="right"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    return fig
```

---

## 9. Data Models and Schemas

```python
# src/api/schemas.py

from pydantic import BaseModel
from datetime import date
from typing import Optional
import numpy as np

class ExposureRequest(BaseModel):
    crop: str
    acreage: int
    pre_purchased_pct: float = 0.0    # 0.0 to 1.0

class ForecastResponse(BaseModel):
    as_of_date: date
    ng_spot_current: float
    ng_change_30d_pct: float
    urea_current: float
    urea_forecast_t1: float           # 30 days
    urea_forecast_t2: float           # 60 days
    urea_forecast_t3: float           # 90 days
    pct_change_t2: float
    directional_signal: str           # "RISING" | "FALLING" | "STABLE"
    confidence: float

class MonteCarloResponse(BaseModel):
    n_simulations: int
    p10_t1: float;  p25_t1: float;  p50_t1: float;  p75_t1: float;  p90_t1: float
    p10_t2: float;  p25_t2: float;  p50_t2: float;  p75_t2: float;  p90_t2: float
    p10_t3: float;  p50_t3: float;  p90_t3: float
    prob_rising_t2: float
    prob_10pct_increase_t2: float
    prob_20pct_increase_t2: float
    sim_t2_distribution: list[float]  # Full distribution for histogram

class ExposureResponse(BaseModel):
    crop: str
    acreage: int
    exposed_acreage: float
    current_cost_per_acre: float
    forecast_cost_per_acre: float
    cost_increase_per_acre: float
    total_cost_increase: float        # Point estimate
    p10_cost_increase: float          # MC-based optimistic
    p50_cost_increase: float          # MC-based median
    p90_cost_increase: float          # MC-based stress scenario
    prob_any_increase: float
    pct_increase: float

class SignalResponse(BaseModel):
    signal: str                       # "BUY_NOW" | "CONSIDER_BUYING" | "WAIT" | "NEUTRAL"
    urgency: str                      # "HIGH" | "MEDIUM" | "LOW"
    rationale: str
    key_driver: str
    forecast_summary: str
    exposure_summary: Optional[str]   # None if no farm profile provided
    confidence: float
    as_of_date: date

class HistoricalDataResponse(BaseModel):
    dates: list[str]
    ng_spot: list[float]
    urea: list[float]
    dap: list[float]
```

---

## 10. Build Order and Time Budget

> **Follow this sequence exactly.** Each step produces something demo-able even if you stop there.

### Hour 0–1: Environment and Data Pull
- [ ] Set up repo, create `.env`, install requirements
- [ ] Register EIA API key (free, instant at eia.gov)
- [ ] Run `scripts/seed_data.py` — pull and cache all 4 data sources
- [ ] Verify `data/raw/MANIFEST.json` shows all files pulled
- [ ] **Checkpoint:** All CSV/xlsx files in `data/raw/`. Open one in pandas — it has data.

### Hour 1–3: Feature Engineering
- [ ] Build `src/ingestion/pipeline.py` — align all sources to monthly DatetimeIndex
- [ ] Build `src/features/engineer.py` — compute all 23 features
- [ ] Build `src/features/crop_costs.py` — `urea_cost_per_acre()` for all crops
- [ ] Save `data/processed/feature_store.parquet`
- [ ] Open `notebooks/01_eda.ipynb` — plot nat gas vs urea, confirm the visual lag is there
- [ ] **Checkpoint:** Feature store is 84 rows (2018–2024), 26 columns (23 features + 3 targets), no NaN except trailing rows where targets are undefined.

### Hour 3–7: Forecasting Model
- [ ] Build `src/models/forecaster.py` — three XGBoost models (t1, t2, t3)
- [ ] Build `src/models/baseline.py` — ARIMA baseline
- [ ] Run walk-forward CV, compare XGBoost vs ARIMA
- [ ] Compute and save residual distributions to `model_metadata.json`
- [ ] Serialize models to `data/models/`
- [ ] **Checkpoint:** Walk-forward RMSE under $60/mt on urea, directional accuracy at t2 above 60%. XGBoost beats ARIMA on RMSE.

### Hour 7–10: Monte Carlo Engine
- [ ] Build `src/simulation/monte_carlo.py` — vectorized, 10,000 draws
- [ ] Test: run MC with current forecast, verify output percentiles are sensible (p10 < p50 < p90, all within plausible price range)
- [ ] Build `notebooks/04_monte_carlo_demo.ipynb` — histogram visualization
- [ ] **Checkpoint:** Monte Carlo runs in under 1 second (vectorized). Histogram looks like a plausible price distribution centered near the point forecast.

### Hour 10–13: Exposure Calculator and Signal Engine
- [ ] Build `src/exposure/calculator.py` — `compute_farm_exposure()` and `compute_exposure_distribution()`
- [ ] Test: 500 acres of corn, urea up $80/mt → should produce ~$13,500 cost increase
- [ ] Build `src/signals/engine.py` — `generate_signal()` with all four signal types
- [ ] Test signal logic with a few manual scenarios
- [ ] **Checkpoint:** A corn farmer with 500 acres in a rising price environment gets "BUY_NOW" with a plausible dollar estimate.

### Hour 13–16: FastAPI Backend
- [ ] Build `src/api/main.py` and all routes
- [ ] Run: `uvicorn src.api.main:app --reload --port 8000`
- [ ] Test every endpoint with `curl` or the FastAPI auto-docs at `http://localhost:8000/docs`
- [ ] **Checkpoint:** All endpoints return 200. `/signal?crop=corn&acreage=500` returns a complete FarmerSignal.

### Hour 16–22: Streamlit Dashboard
- [ ] Build `dashboard/app.py` — sidebar, signal card, cost estimate, price chart, Monte Carlo histogram, historical context table
- [ ] Run: `streamlit run dashboard/app.py`
- [ ] Polish: readable colors, axis labels, annotations on the 2022 spike
- [ ] **Checkpoint:** Full demo flow without errors. A non-technical farmer can understand what the dashboard is telling them.

### Hour 22–23: Historical Stress Test Annotation
- [ ] Add the "when nat gas moved >15% in 30 days" historical table to the dashboard
- [ ] Annotate 2022 spike on the price chart: "Urea peaked at $870/mt — Apr 2022"
- [ ] Write `README.md` for judges — 5 sentences on the problem, then `pip install + streamlit run`

### Hour 23–24: Demo Prep
- [ ] Run full demo cold from a fresh terminal
- [ ] Rehearse the 90-second pitch

---

## 11. Scope Reduction Guide

Cut in this order — each cut is survivable:

| Cut | What you lose | What you keep |
|---|---|---|
| Drop DAP/ammonia, keep urea only | Breadth of fertilizer coverage | Core pipeline intact — urea is the most important |
| Drop `ng_futures` from features | Futures slope feature | Lagged spot prices still carry the signal |
| Drop ARIMA baseline | Model comparison credibility | XGBoost still works fine |
| Drop ExposureDistribution (MC-based) | Probabilistic cost range | Point estimate cost increase still useful |
| Drop FastAPI, call functions directly from Streamlit | Clean API separation | Dashboard still fully functional |
| Reduce MC to 1,000 draws | Histogram smoothness | Percentile estimates still accurate |
| Drop signal engine, show raw numbers | Plain-English recommendation | Charts + numbers tell the story |
| Notebook demo only | Interactive UI | Plotly charts in Jupyter are entirely demo-able |

**Absolute minimum viable demo:**
A Jupyter notebook that: (1) loads EIA and World Bank data, (2) plots nat gas vs urea on a dual-axis chart with the 2022 spike annotated, (3) trains a simple XGBoost model and prints walk-forward RMSE, (4) shows a histogram of Monte Carlo simulated urea prices at 60 days. That is the entire intellectual contribution of this project in four cells.

---

## 12. Demo Script

**90-second pitch:**

> "Urea fertilizer — the most widely used nitrogen source in U.S. agriculture — is priced almost entirely off natural gas. When Henry Hub spikes, urea follows, with a 4 to 8 week lag that's consistent and predictable.
>
> Commodity desks track this. Farmers don't have a commodity desk.
>
> Gas Forecast ingests Henry Hub prices daily, forecasts urea and DAP prices 30, 60, and 90 days forward using an XGBoost model trained on 6 years of monthly data, and runs 10,000 Monte Carlo simulations over the forecast uncertainty to give farmers an honest range of outcomes — not false precision.
>
> A farmer with 500 acres of corn enters their profile and sees: 'Prices are forecast to rise 14% over the next 60 days. In 80% of simulated scenarios, your input costs will increase between $9,000 and $28,000 this season. Consider buying soon.'
>
> That's the commodity desk signal, translated into a dollar figure on their specific farm."

**Demo flow:**
1. Show price chart → point to the nat gas line, then the urea line → "See the lag? That's our signal."
2. Show the 2022 annotation → "This is the last major spike. Nat gas peaked in August. Urea peaked in April — six months earlier, because producers saw it coming."
3. Show signal card → "Right now: BUY NOW, 74% confidence."
4. Change sidebar to soybeans → signal drops to NEUTRAL → "Soybeans fix their own nitrogen. This farmer doesn't care about nat gas prices."
5. Switch back to corn, increase acreage to 2,000 → cost estimate updates → "Scale matters. 2,000 acres of corn exposed to a 14% price move is a $73,000 decision."
6. Show Monte Carlo histogram → "This isn't a single number. In 10% of scenarios prices actually fall. In 10% they go up over 30%. We show you the whole distribution."

---

## 13. Environment Setup

### Installation
```bash
git clone <repo-url>
cd gas_forecast
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### `.env`
```
EIA_API_KEY=your_key_here
ENVIRONMENT=development
```

### `.env.example`
```
EIA_API_KEY=
ENVIRONMENT=development
```

### `requirements.txt`
```
pandas==2.2.1
numpy==1.26.4
xgboost==2.0.3
scikit-learn==1.4.1
statsmodels==0.14.1
scipy==1.13.0
pyarrow==15.0.2
openpyxl==3.1.2
fastapi==0.110.0
uvicorn==0.29.0
pydantic==2.6.4
httpx==0.27.0
python-dotenv==1.0.1
streamlit==1.33.0
plotly==5.20.0
requests==2.31.0
```

### First-time setup (run once, in order)
```bash
python scripts/seed_data.py      # Pull and cache all external data
python scripts/train_models.py   # Train XGBoost models, save to data/models/
```

### Run the full stack
```bash
# Terminal 1 — API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — Dashboard
streamlit run dashboard/app.py
```

### Run the dashboard without the API (simpler, for early testing)
```bash
# Set STANDALONE_MODE=true in .env — dashboard calls Python functions directly
streamlit run dashboard/app.py
```

---

*This document is the source of truth for the next 24 hours. The product is fundamentally a data pipeline with a good explanation layer on top. Ingest honest data, produce honest forecasts, explain the uncertainty honestly, and translate it into something a farmer can act on. Everything in this spec serves that goal.*
