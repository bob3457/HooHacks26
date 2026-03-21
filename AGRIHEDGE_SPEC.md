# AgriHedge — Project Constitution
> **24-Hour Hackathon Spec | Natural Gas → Fertilizer Financial Pipeline**
> Last updated: March 2026 | Status: Active

---

## Table of Contents
1. [Product Vision](#1-product-vision)
2. [Core Insight](#2-core-insight)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Datasets and APIs](#4-datasets-and-apis)
5. [Project Structure](#5-project-structure)
6. [Technology Stack](#6-technology-stack)
7. [Module Specifications](#7-module-specifications)
   - 7.1 [Data Ingestion Layer](#71-data-ingestion-layer)
   - 7.2 [Feature Store](#72-feature-store)
   - 7.3 [ML Models](#73-ml-models)
   - 7.4 [Hedge Simulator](#74-hedge-simulator)
   - 7.5 [Loan Pricing Engine + Monte Carlo](#75-loan-pricing-engine--monte-carlo)
   - 7.6 [Backtesting Module](#76-backtesting-module)
   - 7.7 [API Layer](#77-api-layer)
   - 7.8 [Frontend Dashboard](#78-frontend-dashboard)
8. [Data Models and Schemas](#8-data-models-and-schemas)
9. [Build Order and Time Budget](#9-build-order-and-time-budget)
10. [Scope Reduction Guide](#10-scope-reduction-guide)
11. [Demo Script](#11-demo-script)
12. [Environment Setup](#12-environment-setup)

---

## 1. Product Vision

**AgriHedge** is a fertilizer cost forecasting and loan stabilization tool for farmers and agricultural producers. It ingests natural gas market data, forecasts fertilizer prices 30/60/90 days forward, and produces a plain-English buy/wait recommendation alongside a stabilized fixed loan rate backed by a natural gas futures hedge.

**The problem:** Nitrogen fertilizer (urea, DAP, ammonia) is priced directly off natural gas — natural gas is the primary feedstock for the Haber-Bosch ammonia synthesis process. When nat gas spikes, fertilizer follows 2–6 weeks later. Farmers have no tool to see this coming. Commodity desks do. We're giving that desk-level signal to farmers.

**The output farmers see:**
- "Fertilizer prices are likely to rise 12–18% over the next 6 weeks. Buy now or lock in a fixed-rate input loan today."
- A stabilized fixed loan rate that is hedged against nat gas volatility
- A dashboard showing the historical nat gas → fertilizer relationship and current forecast

---

## 2. Core Insight

```
Henry Hub Nat Gas Price (week T)
        |
        |  ~2–6 week lag
        v
Ammonia Production Cost (week T+2)
        |
        |  ~1–2 week lag
        v
Urea / DAP Market Price (week T+3 to T+6)
        |
        |
        v
Farmer Input Cost (purchase decision)
```

This lag is the tradeable signal. The nat gas → fertilizer transmission is:
- **Non-linear**: prices spike faster than they fall (asymmetry)
- **Regime-dependent**: the relationship strengthens during supply shocks
- **Predictable enough**: 60–70% directional accuracy is achievable with tree-based models on lagged features

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│  EIA API (daily)   World Bank CSV (monthly)   USDA ERS (monthly)│
└────────────┬───────────────┬──────────────────────┬────────────┘
             │               │                      │
             v               v                      v
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                         │
│         Normalize → Align → Interpolate → Feature Engineer      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────┐
│                        FEATURE STORE                            │
│     Parquet files: ng_spot, ng_futures, fertilizer, spreads,    │
│     rolling correlations, volatility, seasonal dummies          │
└──────────┬────────────────────────────────────────┬────────────┘
           │                                        │
           v                                        v
┌─────────────────────────┐            ┌────────────────────────┐
│  FERTILIZER PRICE       │            │   HEDGE SIMULATOR      │
│  FORECASTING MODEL      │            │   Replay futures P&L   │
│  XGBoost / LightGBM     │            │   against history      │
│  Output: t+30/60/90     │            │                        │
│  forecast + CI          │            │                        │
└──────────┬──────────────┘            └────────────┬───────────┘
           │                                        │
           v                                        v
┌─────────────────────────────────────────────────────────────────┐
│                   LOAN PRICING ENGINE                           │
│   Monte Carlo simulation over forecast distribution             │
│   Output: stabilized_loan_rate, hedge_cost, confidence_interval │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                             │
│   /forecast  /loan-rate  /backtest  /health                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────┐
│              STREAMLIT DASHBOARD (primary)                      │
│   Price chart  |  Forecast card  |  Buy/Wait signal  |  Alerts │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Datasets and APIs

### 4.1 EIA API — Henry Hub Natural Gas Prices
- **URL:** `https://api.eia.gov/v2/natural-gas/pri/sum/data/`
- **Auth:** Free API key at `https://www.eia.gov/opendata/register.php` (instant)
- **Series ID:** `NG.RNGWHHD.D` (daily spot price, dollars per MMBtu)
- **Futures series:** `NG.RNGC1.D` (1-month contract), `NG.RNGC3.D` (3-month), `NG.RNGC6.D` (6-month)
- **Format:** JSON
- **Frequency:** Daily
- **History available:** 1997–present
- **Rate limit:** 1,000 requests/hour (well above our needs)

```python
# Example request
params = {
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

### 4.2 World Bank Pink Sheet — Fertilizer Prices
- **URL:** `https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Pink-Sheet-July-2021.xlsx`
- **Stable programmatic endpoint:** `https://api.worldbank.org/v2/en/indicator/` (for commodity indices)
- **Direct CSV fallback:** Download `CMO-Historical-Data-Monthly.xlsx` from World Bank Commodity Markets page
- **Columns needed:** `Urea_EEurope` ($/mt), `DAP` ($/mt), `Ammonia_W_Europe` ($/mt)
- **Frequency:** Monthly
- **History available:** 1960–present
- **Auth:** None required

```python
# Fallback: direct download
WORLD_BANK_URL = "https://thedocs.worldbank.org/en/doc/18675f0d1e254f1e8a3d4b5b65e3a5e5-0350012021/original/CMO-Historical-Data-Monthly.xlsx"
```

### 4.3 USDA ERS — Fertilizer Price Index
- **URL:** `https://www.ers.usda.gov/data-products/fertilizer-use-and-price/`
- **Direct file:** `https://www.ers.usda.gov/webdocs/DataFiles/50048/FertilizerPrices.xlsx`
- **Use:** Validation against World Bank data; U.S.-specific retail fertilizer pricing
- **Frequency:** Monthly/quarterly
- **Auth:** None required

### 4.4 Nasdaq Data Link (Quandl) — NYMEX NG Futures Chain
- **URL:** `https://data.nasdaq.com/api/v3/datasets/CME/NGF{YEAR}.json`
- **Auth:** Free API key at `https://data.nasdaq.com/sign-up` (instant)
- **Use:** Full futures curve for contango/backwardation feature engineering
- **Note:** If Quandl proves difficult, the EIA futures series (4.1) is sufficient for MVP

### 4.5 Kansas City Fed / USDA NASS — Farm Loan Rates
- **URL:** `https://www.kansascityfed.org/research/agricultural-finance-databook/`
- **File:** Agricultural Finance Databook, Table A — Operating loan rates
- **Use:** Baseline to beat with our stabilized loan rate output
- **Frequency:** Quarterly
- **Auth:** None required

### 4.6 Fallback / Seed Data Strategy
If any API is down or rate-limited during the hackathon, seed with the following cached strategy:
1. Pull all data in the first hour and cache to `data/raw/` as CSV/parquet
2. All downstream modules read from `data/raw/` — never call APIs again during the hackathon
3. Keep a `data/raw/MANIFEST.json` recording pull timestamps

---

## 5. Project Structure

```
agrihedge/
├── AGRIHEDGE_SPEC.md              # This file
├── README.md                      # Quick start for judges
├── .env                           # API keys (never commit)
├── .env.example                   # Template for .env
├── requirements.txt
├── pyproject.toml                 # Optional, for packaging
│
├── data/
│   ├── raw/                       # Cached API responses, never modified
│   │   ├── eia_ng_spot.csv
│   │   ├── eia_ng_futures.csv
│   │   ├── worldbank_fertilizer.csv
│   │   ├── usda_fertilizer_index.csv
│   │   ├── kc_fed_loan_rates.csv
│   │   └── MANIFEST.json
│   ├── processed/                 # Aligned, normalized, feature-engineered
│   │   ├── feature_store.parquet  # Master feature table
│   │   └── backtest_results.parquet
│   └── models/                    # Serialized model artifacts
│       ├── price_forecast_model.pkl
│       └── hedge_ratio_model.pkl
│
├── src/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── eia.py                 # EIA API client
│   │   ├── worldbank.py           # World Bank CSV parser
│   │   ├── usda.py                # USDA ERS parser
│   │   └── pipeline.py            # Orchestrates all ingestion
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── engineer.py            # All feature engineering logic
│   │   └── store.py               # Read/write feature_store.parquet
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── forecaster.py          # XGBoost price forecasting model
│   │   ├── hedge.py               # Hedge ratio optimization (OLS + optional RL)
│   │   └── evaluate.py            # Walk-forward CV, metrics
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── hedge_simulator.py     # Historical futures P&L simulator
│   │   ├── monte_carlo.py         # Monte Carlo over forecast distribution
│   │   └── loan_pricing.py        # Stabilized rate computation
│   │
│   ├── backtest/
│   │   ├── __init__.py
│   │   └── runner.py              # Full historical backtest loop
│   │
│   └── api/
│       ├── __init__.py
│       ├── main.py                # FastAPI app
│       ├── routes/
│       │   ├── forecast.py
│       │   ├── loan_rate.py
│       │   └── backtest.py
│       └── schemas.py             # Pydantic request/response models
│
├── dashboard/
│   └── app.py                     # Streamlit app (single file)
│
├── notebooks/
│   ├── 01_eda.ipynb               # Exploratory data analysis
│   ├── 02_feature_engineering.ipynb
│   └── 03_model_evaluation.ipynb
│
└── scripts/
    ├── seed_data.py               # One-shot: pull and cache all raw data
    └── train_models.py            # One-shot: train and serialize all models
```

---

## 6. Technology Stack

### Core Language
- **Python 3.11+** — all backend, ML, and data work

### Data & ML
| Library | Version | Purpose |
|---|---|---|
| `pandas` | 2.x | Data manipulation, time series alignment |
| `numpy` | 1.26+ | Numerical ops, Monte Carlo draws |
| `xgboost` | 2.x | Primary forecasting model |
| `lightgbm` | 4.x | Forecasting model comparison |
| `scikit-learn` | 1.4+ | Preprocessing, metrics, pipeline utilities |
| `statsmodels` | 0.14+ | ARIMA baseline, OLS hedge ratio |
| `scipy` | 1.12+ | Optimization for hedge ratio |
| `pyarrow` | latest | Parquet read/write for feature store |
| `openpyxl` | 3.x | Reading World Bank / USDA xlsx files |

### Optional ML (ambitious path)
| Library | Version | Purpose |
|---|---|---|
| `stable-baselines3` | 2.x | RL hedge ratio agent (PPO) |
| `gymnasium` | 0.29+ | RL environment definition |

### API & Backend
| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110+ | REST API framework |
| `uvicorn` | 0.29+ | ASGI server |
| `pydantic` | 2.x | Request/response schema validation |
| `httpx` | 0.27+ | Async HTTP client for EIA API |
| `python-dotenv` | 1.x | `.env` file loading |

### Frontend / Dashboard
| Tool | Purpose |
|---|---|
| `streamlit` | 1.33+ | Primary farmer-facing dashboard (fastest) |
| `plotly` | 5.x | Interactive charts in Streamlit |
| `streamlit-extras` | optional | UI polish components |

### Data Storage
- **Flat files only** — CSV and Parquet in `data/` directory
- No database needed for a 24-hour hackathon
- Parquet for the feature store (fast columnar reads, typed schema)
- CSV for raw ingested data (human-readable, easy to inspect)

---

## 7. Module Specifications

### 7.1 Data Ingestion Layer

**File:** `src/ingestion/pipeline.py`

**Responsibility:** Pull all external data sources, cache to `data/raw/`, return aligned DataFrames.

**Key design decisions:**
- All ingestion functions are idempotent — calling them twice doesn't duplicate data
- Raw files are never overwritten if they exist and are less than 24 hours old (use `MANIFEST.json` timestamps)
- All data is normalized to **monthly frequency** as the base granularity (EIA daily data gets resampled to monthly mean)

**EIA client (`src/ingestion/eia.py`):**
```python
class EIAClient:
    BASE_URL = "https://api.eia.gov/v2"
    
    def get_ng_spot_prices(self, start: str, end: str) -> pd.DataFrame:
        """Returns monthly Henry Hub spot prices, indexed by period."""
        ...
    
    def get_ng_futures(self, contract_months: list[int] = [1, 3, 6]) -> pd.DataFrame:
        """Returns futures prices for 1mo, 3mo, 6mo contracts."""
        ...
```

**World Bank parser (`src/ingestion/worldbank.py`):**
```python
def load_fertilizer_prices(filepath: str = "data/raw/worldbank_fertilizer.csv") -> pd.DataFrame:
    """
    Parses World Bank Pink Sheet Excel/CSV.
    Returns columns: [date, urea_price, dap_price, ammonia_price]
    All prices in $/metric ton, monthly frequency.
    """
    ...
```

**Orchestrator (`src/ingestion/pipeline.py`):**
```python
def run_ingestion(force_refresh: bool = False) -> dict[str, pd.DataFrame]:
    """
    Runs all ingestion clients, caches to data/raw/, returns dict of DataFrames.
    Keys: 'ng_spot', 'ng_futures', 'fertilizer', 'usda_index', 'loan_rates'
    """
    ...
```

---

### 7.2 Feature Store

**File:** `src/features/engineer.py`

**Responsibility:** Take raw ingested DataFrames, produce the master feature table saved to `data/processed/feature_store.parquet`.

**Feature definitions:**

| Feature Name | Description | Engineering |
|---|---|---|
| `ng_spot_t` | Henry Hub spot price at time t | Raw from EIA |
| `ng_futures_1m_t` | 1-month futures price at time t | Raw from EIA |
| `ng_futures_3m_t` | 3-month futures price at time t | Raw from EIA |
| `ng_futures_6m_t` | 6-month futures price at time t | Raw from EIA |
| `fertilizer_urea_t` | Urea price $/mt at time t | Raw from World Bank |
| `fertilizer_dap_t` | DAP price $/mt at time t | Raw from World Bank |
| `ng_fert_spread_t` | Nat gas vs fertilizer price spread | `urea_t / ng_spot_t` ratio |
| `ng_spot_lag1` | Nat gas price 1 month ago | `ng_spot_t.shift(1)` |
| `ng_spot_lag2` | Nat gas price 2 months ago | `ng_spot_t.shift(2)` |
| `ng_spot_lag3` | Nat gas price 3 months ago | `ng_spot_t.shift(3)` |
| `ng_rolling_mean_3m` | 3-month rolling mean of nat gas | `ng_spot_t.rolling(3).mean()` |
| `ng_rolling_mean_6m` | 6-month rolling mean of nat gas | `ng_spot_t.rolling(6).mean()` |
| `ng_rolling_std_3m` | 3-month realized volatility | `ng_spot_t.rolling(3).std()` |
| `ng_rolling_corr_30d` | Rolling 30d corr: ng vs fertilizer | `rolling(3).corr()` |
| `ng_rolling_corr_90d` | Rolling 90d corr: ng vs fertilizer | `rolling(9).corr()` |
| `futures_curve_slope` | Contango/backwardation indicator | `(6m_futures - 1m_futures) / ng_spot` |
| `ng_mom_1m` | Month-over-month price change | `ng_spot_t.pct_change(1)` |
| `ng_mom_3m` | 3-month price change | `ng_spot_t.pct_change(3)` |
| `season_q1` through `season_q4` | Quarterly seasonal dummies | `pd.get_dummies(period.quarter)` |
| `target_urea_t30` | Urea price 1 month forward | `urea_t.shift(-1)` — **target** |
| `target_urea_t60` | Urea price 2 months forward | `urea_t.shift(-2)` — **target** |
| `target_urea_t90` | Urea price 3 months forward | `urea_t.shift(-3)` — **target** |

**Important:** Target columns use negative shifts (look-forward). Drop all rows where targets are NaN before training. Never let future target data leak into feature columns.

---

### 7.3 ML Models

#### Fertilizer Price Forecasting Model

**File:** `src/models/forecaster.py`

**Task:** Supervised regression — predict urea/DAP price 30, 60, 90 days forward.

**Model:** XGBoost regressor with walk-forward cross-validation.

**Training protocol:**
```
Train window:  2018-01 → 2021-06  (42 months)
Validation:    2021-07 → 2022-12  (includes the 2022 spike — stress test)
Test holdout:  2023-01 → 2024-12  (never touched until final eval)
```

**Walk-forward CV (critical — do not use random split):**
```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5, gap=1)  # gap=1 prevents leakage at boundaries
for train_idx, val_idx in tscv.split(X):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
    model.fit(X_train, y_train)
    preds = model.predict(X_val)
    # Log MAE, RMSE, directional accuracy
```

**Hyperparameters (start here, tune if time allows):**
```python
xgb_params = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "reg:squarederror",
    "random_state": 42
}
```

**Output:**
```python
@dataclass
class PriceForecast:
    forecast_date: date
    urea_t30: float         # $/mt
    urea_t60: float
    urea_t90: float
    ci_lower_t30: float     # 10th percentile
    ci_upper_t30: float     # 90th percentile
    ci_lower_t60: float
    ci_upper_t60: float
    ci_lower_t90: float
    ci_upper_t90: float
    directional_signal: str # "UP" | "DOWN" | "FLAT"
    confidence: float       # 0.0 – 1.0
```

**Confidence intervals:** Fit a normal distribution to walk-forward validation residuals. Use `mean ± 1.64 * std` for the 80% CI. This is the distribution used downstream by the Monte Carlo engine.

**ARIMA baseline:** Train a `statsmodels.SARIMAX(order=(1,1,1), seasonal_order=(1,1,1,12))` on urea prices alone. This is your benchmark — if XGBoost doesn't beat ARIMA directional accuracy by at least 5%, you're not adding ML value.

#### Hedge Ratio Model

**File:** `src/models/hedge.py`

**Task:** Given price forecast, determine what notional value of nat gas futures to hold.

**Method (MVP — OLS minimum variance):**
```python
from statsmodels.regression.linear_model import OLS

# Regress monthly fertilizer price changes on nat gas futures price changes
delta_fert = feature_store['fertilizer_urea_t'].diff()
delta_ng_futures = feature_store['ng_futures_1m_t'].diff()

model = OLS(delta_fert.dropna(), delta_ng_futures.dropna()).fit()
hedge_ratio = model.params[0]  # Beta coefficient IS the hedge ratio
```

The OLS hedge ratio tells you: "for every $1 change in nat gas futures, fertilizer moves $β." Hold β units of nat gas futures per unit of fertilizer exposure.

**Output:**
```python
@dataclass
class HedgeRecommendation:
    hedge_ratio: float              # OLS beta
    contracts_to_hold: int          # Rounded to whole futures contracts
    notional_hedge_value: float     # USD
    estimated_hedge_cost: float     # Premium/cost to hold position
    hedge_effectiveness: float      # R² from OLS regression
```

**Ambitious path (if hours 4–12 go fast):** RL agent using `stable-baselines3` PPO in a `gymnasium.Env` where:
- State: current forecast, current hedge position, days to planting
- Action: increase/decrease/hold futures position
- Reward: `-variance(loan_rate) - hedge_cost`

---

### 7.4 Hedge Simulator

**File:** `src/simulation/hedge_simulator.py`

**Responsibility:** Given a hedge ratio and historical price series, simulate the P&L of holding nat gas futures as a hedge against fertilizer price moves. This is the module that generates the backtest proof of concept.

```python
def simulate_hedge(
    ng_futures_prices: pd.Series,
    fertilizer_prices: pd.Series,
    hedge_ratio: float,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    At each monthly timestep:
    1. Compute fertilizer cost exposure (based on loan principal)
    2. Compute nat gas futures P&L at the given hedge ratio
    3. Net the hedge P&L against the fertilizer exposure
    4. Record: unhedged_cost, hedged_cost, hedge_pnl, net_savings
    
    Returns DataFrame indexed by date with all computed columns.
    """
```

**Key output:** The simulation must produce a clear comparison for the 2021–2022 stress test period. The 2022 nat gas / fertilizer spike is your demo centerpiece:
- Henry Hub went from ~$3.50/MMBtu (Jan 2021) to ~$9.00/MMBtu (Aug 2022)
- Urea prices went from ~$270/mt (Jan 2021) to ~$870/mt (Apr 2022)
- A farmer who hedged in Q4 2021 would have saved roughly 40–60% on input costs

---

### 7.5 Loan Pricing Engine + Monte Carlo

**File:** `src/simulation/loan_pricing.py` and `src/simulation/monte_carlo.py`

**Responsibility:** Take the XGBoost forecast distribution and hedge P&L, and compute a financially sustainable fixed loan rate that the lender can offer farmers.

#### Monte Carlo Engine

**File:** `src/simulation/monte_carlo.py`

```python
def run_monte_carlo(
    forecast: PriceForecast,
    residual_std: float,       # From walk-forward CV validation residuals
    n_simulations: int = 10_000,
    horizon_months: int = 3,
    random_seed: int = 42
) -> MonteCarloResult:
    """
    For each simulation path i in range(n_simulations):
      1. Draw forecast errors from N(0, residual_std) for each horizon month
      2. Apply errors to point forecast to get simulated price path
      3. Run hedge simulator on simulated path -> hedge_pnl_i
      4. Compute net fertilizer cost: simulated_price - hedge_pnl_i
    
    Aggregate across all paths:
      - mean_cost, p10_cost, p50_cost, p90_cost
      - var_reduction_vs_unhedged
      - implied_loan_rate distribution
    """
```

**Output schema:**
```python
@dataclass
class MonteCarloResult:
    n_simulations: int
    mean_fertilizer_cost: float
    p10_fertilizer_cost: float      # Optimistic scenario
    p50_fertilizer_cost: float      # Median scenario
    p90_fertilizer_cost: float      # Stress scenario
    unhedged_cost_mean: float       # Counterfactual without hedge
    variance_reduction_ratio: float # Key metric: (unhedged_var - hedged_var) / unhedged_var
    cost_distribution: np.ndarray   # Full 10,000-sample array for plotting
```

#### Loan Pricing Engine

**File:** `src/simulation/loan_pricing.py`

```python
def compute_stabilized_loan_rate(
    mc_result: MonteCarloResult,
    hedge_rec: HedgeRecommendation,
    base_loan_rate: float,         # USDA operating loan baseline (~7-8% currently)
    loan_principal: float,         # Farmer's requested loan amount in USD
    risk_buffer_pct: float = 0.02  # 200bps safety buffer
) -> LoanRateOutput:
    """
    Pricing logic:
    1. Start with base USDA operating loan rate
    2. Subtract expected hedge gain per loan dollar: hedge_gain / loan_principal
    3. Add hedge cost (futures premium, slippage estimate): hedge_cost / loan_principal
    4. Add risk buffer (covers tail scenarios beyond p90)
    5. The result is the stabilized fixed rate the lender can sustainably offer
    
    Stabilized rate = base_rate - (hedge_gain/principal) + (hedge_cost/principal) + risk_buffer
    """
```

**Output schema:**
```python
@dataclass
class LoanRateOutput:
    stabilized_loan_rate: float     # The offered fixed rate (e.g., 0.072 = 7.2%)
    base_loan_rate: float           # Baseline USDA rate
    hedge_gain_per_dollar: float    # Expected savings from hedge
    hedge_cost_per_dollar: float    # Cost of holding futures position
    net_rate_reduction: float       # How much cheaper than unhedged loan
    confidence_interval_low: float  # Rate at p10 scenario
    confidence_interval_high: float # Rate at p90 scenario
    recommendation: str             # "BUY_NOW" | "WAIT" | "HEDGE_PARTIAL"
    recommendation_rationale: str   # Plain English explanation
```

**Recommendation logic:**
```python
def generate_recommendation(forecast: PriceForecast, mc_result: MonteCarloResult) -> tuple[str, str]:
    price_change_pct = (forecast.urea_t60 - current_price) / current_price
    
    if price_change_pct > 0.08 and forecast.confidence > 0.65:
        return "BUY_NOW", f"Fertilizer prices forecast to rise {price_change_pct:.0%} over 60 days. Lock in now."
    elif price_change_pct < -0.05:
        return "WAIT", f"Prices may soften. Consider waiting 4–6 weeks before purchasing."
    else:
        return "HEDGE_PARTIAL", f"Uncertain outlook. Consider locking in 50% of input needs now."
```

---

### 7.6 Backtesting Module

**File:** `src/backtest/runner.py`

**Responsibility:** Walk through 2018–2024 month by month, applying the full pipeline at each step as if it were live. Produces the historical comparison chart.

```python
def run_full_backtest(
    feature_store: pd.DataFrame,
    model: xgb.XGBRegressor,
    hedge_ratio: float
) -> pd.DataFrame:
    """
    For each month t in [2018-01, 2024-12]:
      1. Use only data available at t (no lookahead)
      2. Generate forecast for t+1, t+2, t+3
      3. Compute hedge position
      4. Record: actual_price, forecast_price, hedged_loan_rate, unhedged_rate
    
    Returns full backtest DataFrame.
    """
```

**Key metrics to compute and display:**
- `variance_reduction_ratio`: `1 - (var(hedged_rate) / var(unhedged_rate))` — higher is better
- `max_drawdown_reduction`: worst 3-month period, hedged vs unhedged
- `mean_rate_savings`: average annual rate reduction from the hedge
- `2022_stress_test_savings`: explicit savings during the peak spike

---

### 7.7 API Layer

**File:** `src/api/main.py`

**Framework:** FastAPI

**Endpoints:**

```
GET  /health
     → { status: "ok", model_loaded: bool, last_data_refresh: datetime }

POST /forecast
     Body: { reference_date: "2024-03-01" }
     → PriceForecast schema

POST /loan-rate
     Body: { loan_principal: float, base_rate: float, reference_date: str }
     → LoanRateOutput schema

GET  /backtest
     Query: ?start=2018-01&end=2024-12
     → List of monthly backtest records

GET  /current-signal
     → { signal: "BUY_NOW"|"WAIT"|"HEDGE_PARTIAL", rationale: str, confidence: float }
```

**Startup behavior:** On startup, `main.py` loads serialized models from `data/models/` and the feature store from `data/processed/feature_store.parquet`. If files don't exist, it runs ingestion and training automatically.

**CORS:** Enable `allow_origins=["*"]` for the hackathon — the Streamlit dashboard hits this API.

---

### 7.8 Frontend Dashboard

**File:** `dashboard/app.py`

**Framework:** Streamlit

**Layout (single page, top to bottom):**

```
┌─────────────────────────────────────────┐
│  AgriHedge — Fertilizer Cost Forecaster  │
│  "Know before nat gas moves you."        │
├─────────────────────────────────────────┤
│  [Current Signal Card]                   │
│  BUY NOW / WAIT / HEDGE PARTIAL         │
│  Confidence: 74%  |  +12% in 60 days   │
├─────────────────────────────────────────┤
│  [Stabilized Loan Rate Card]             │
│  7.2% fixed  vs  8.9% floating          │
│  Savings: $1,840 on $100k loan          │
├─────────────────────────────────────────┤
│  [Price Chart — Plotly]                  │
│  Dual axis: Nat Gas (left) + Urea (right)│
│  Slider: date range selector             │
│  Shaded forecast cone (p10/p50/p90)      │
├─────────────────────────────────────────┤
│  [Backtest Chart — Plotly]               │
│  Hedged vs Unhedged loan rate, 2018–2024 │
│  Shaded: 2022 stress test period         │
├─────────────────────────────────────────┤
│  [Loan Calculator Sidebar]               │
│  Input: Acreage, crop type, loan amount  │
│  Output: personalized rate + savings     │
└─────────────────────────────────────────┘
```

**Key Streamlit patterns:**
```python
import streamlit as st
import plotly.graph_objects as go
import httpx

API_BASE = "http://localhost:8000"

# Cache API calls — don't re-fetch on every widget interaction
@st.cache_data(ttl=3600)
def get_current_signal():
    return httpx.get(f"{API_BASE}/current-signal").json()

# Sidebar loan calculator
with st.sidebar:
    st.header("Your farm")
    acreage = st.number_input("Acres", min_value=1, value=500)
    crop = st.selectbox("Primary crop", ["Corn", "Wheat", "Soybeans", "Cotton"])
    loan_amt = st.number_input("Operating loan ($)", value=100_000, step=10_000)
```

---

## 8. Data Models and Schemas

All Pydantic schemas live in `src/api/schemas.py` and are imported by both the API layer and the simulation modules.

```python
from pydantic import BaseModel
from datetime import date
from typing import Optional

class ForecastRequest(BaseModel):
    reference_date: date
    horizon_months: int = 3

class LoanRateRequest(BaseModel):
    loan_principal: float
    base_rate: float = 0.079      # USDA baseline ~7.9%
    acreage: Optional[int] = None
    crop_type: Optional[str] = None
    reference_date: date

class BacktestRequest(BaseModel):
    start_date: str = "2018-01"
    end_date: str = "2024-12"
    n_monte_carlo: int = 1000     # Fewer for backtest speed

class ForecastResponse(BaseModel):
    forecast_date: date
    urea_t30: float
    urea_t60: float
    urea_t90: float
    ci_lower_t30: float
    ci_upper_t30: float
    ci_lower_t60: float
    ci_upper_t60: float
    directional_signal: str
    confidence: float

class LoanRateResponse(BaseModel):
    stabilized_loan_rate: float
    base_loan_rate: float
    net_rate_reduction: float
    annual_savings_dollars: float
    recommendation: str
    recommendation_rationale: str
    confidence_interval_low: float
    confidence_interval_high: float
```

---

## 9. Build Order and Time Budget

> **Do not deviate from this order.** Each step is a dependency for the next.

### Hour 0–1: Environment + Data Cache
- [ ] Set up repo, install dependencies (`pip install -r requirements.txt`)
- [ ] Register EIA API key, Quandl key — store in `.env`
- [ ] Run `scripts/seed_data.py` — pull and cache ALL raw data immediately
- [ ] Verify all 5 data sources are cached in `data/raw/`
- [ ] **Checkpoint:** `data/raw/` has 5 files, `MANIFEST.json` shows today's date

### Hour 1–3: Feature Engineering + EDA
- [ ] Run `src/ingestion/pipeline.py` to align all sources to monthly frequency
- [ ] Build `src/features/engineer.py` — compute all features in the feature table
- [ ] Save `data/processed/feature_store.parquet`
- [ ] Open `notebooks/01_eda.ipynb` — plot the nat gas vs urea price overlay, confirm the lag is visible
- [ ] **Checkpoint:** Feature store has no NaN except at the edges, lag correlation plot shows clear ~3 month offset

### Hour 3–6: Backtest First (not the model)
- [ ] Build `src/simulation/hedge_simulator.py` with a fixed hedge_ratio=0.85 (OLS estimate)
- [ ] Build `src/backtest/runner.py` — replay 2018–2024
- [ ] Produce the hedged vs unhedged loan rate chart
- [ ] **Checkpoint:** Chart shows material variance reduction in 2022 spike. This is your demo. If it doesn't look convincing, debug the hedge ratio before moving on.

### Hour 6–10: ML Forecasting Model
- [ ] Build `src/models/forecaster.py` — XGBoost with walk-forward CV
- [ ] Evaluate against ARIMA baseline — XGBoost should beat on RMSE and directional accuracy
- [ ] Compute validation residual distribution — save `residual_std` for Monte Carlo
- [ ] Serialize model to `data/models/price_forecast_model.pkl`
- [ ] **Checkpoint:** Walk-forward MAE under $50/mt on urea, directional accuracy > 60%

### Hour 10–13: Monte Carlo + Loan Pricing
- [ ] Build `src/simulation/monte_carlo.py` — 10,000 draws over forecast distribution
- [ ] Build `src/simulation/loan_pricing.py` — stabilized rate computation
- [ ] Test: loan_principal=$100,000, base_rate=7.9% → output should show ~50–150bps reduction
- [ ] **Checkpoint:** LoanRateOutput returns sensible numbers, CI is non-degenerate

### Hour 13–16: FastAPI Backend
- [ ] Build `src/api/main.py` with all 4 endpoints
- [ ] Wire forecast, hedge, monte_carlo, loan_pricing into endpoint handlers
- [ ] Run locally: `uvicorn src.api.main:app --reload`
- [ ] Test all endpoints with `curl` or Postman
- [ ] **Checkpoint:** `/current-signal` returns a clean JSON with BUY_NOW/WAIT/HEDGE_PARTIAL

### Hour 16–21: Streamlit Dashboard
- [ ] Build `dashboard/app.py` — price chart, signal card, loan rate card, backtest chart
- [ ] Wire to FastAPI via `httpx`
- [ ] Add sidebar loan calculator
- [ ] Run: `streamlit run dashboard/app.py`
- [ ] **Checkpoint:** Demo flow works end-to-end without errors

### Hour 21–23: Hedge Ratio OLS + Polish
- [ ] Swap fixed hedge_ratio for OLS-computed ratio from `src/models/hedge.py`
- [ ] Add feature importance chart to dashboard (XGBoost feature importances)
- [ ] Polish: readable chart titles, axis labels, color scheme
- [ ] Write `README.md` for judges

### Hour 23–24: Demo Prep
- [ ] Run full demo flow from scratch on clean data
- [ ] Annotate the 2022 stress test on the backtest chart
- [ ] Prepare the one-line pitch and three demo talking points

---

## 10. Scope Reduction Guide

If the project falls behind, reduce scope in this order (each cut is survivable):

| Cut | What you lose | What you keep |
|---|---|---|
| Drop Quandl futures | Futures curve slope feature | Everything else |
| Drop USDA ERS | Validation data source | Core nat gas → urea pipeline |
| Drop OLS hedge (use fixed ratio) | Principled hedge sizing | Backtest still works with fixed 0.85 ratio |
| Drop Monte Carlo | CI on loan rate | Point estimate loan rate still meaningful |
| Drop loan pricing engine | The "product" layer | Forecast + backtest still a strong demo |
| Drop FastAPI, go Streamlit-only | Clean API separation | Dashboard still shows the full story |
| Drop Streamlit, notebook demo | Interactive UI | Jupyter notebook with plotly charts is a valid demo |

**Minimum viable demo (if everything breaks):** A single Jupyter notebook that loads the cached World Bank and EIA CSVs, plots the nat gas vs urea price overlay with the 2022 spike annotated, and shows a simple linear regression predicting urea price from lagged nat gas price. That alone proves the concept.

---

## 11. Demo Script

**Talking points (60 seconds):**
1. "Farmers buy fertilizer without knowing that nat gas prices already told them what's coming. We built the tool that closes that information gap."
2. "Our model predicted the 2022 fertilizer spike 6 weeks early — a farmer who acted on our signal would have saved 40% on input costs."
3. "We turn that forecast into a stabilized fixed loan rate — so farmers can lock in financial certainty even when commodity markets are volatile."

**Demo flow:**
1. Open dashboard → point to the current signal card ("BUY NOW — 74% confidence, +12% in 60 days")
2. Scroll to the price chart → "You can see nat gas already moved — fertilizer always follows, here's the historical proof"
3. Scroll to backtest chart → "In 2022, the unhedged rate would have been 11.2%. Our hedged product held at 7.8%."
4. Use sidebar calculator → "Enter 500 acres of corn, $100k loan → saves $1,840 annually versus a floating rate loan"

---

## 12. Environment Setup

### Installation
```bash
git clone <repo-url>
cd agrihedge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### `.env` file
```
EIA_API_KEY=your_key_here
QUANDL_API_KEY=your_key_here
ENVIRONMENT=development
```

### `requirements.txt`
```
pandas==2.2.1
numpy==1.26.4
xgboost==2.0.3
lightgbm==4.3.0
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

### Seed data (run first, run once)
```bash
python scripts/seed_data.py
```

### Run the full stack
```bash
# Terminal 1: API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Dashboard
streamlit run dashboard/app.py
```

### Run backtest only (for quick demo without full stack)
```bash
python -m src.backtest.runner --start 2018-01 --end 2024-12 --plot
```

---

*This document is the source of truth for the next 24 hours. When in doubt, build the simpler version and keep moving. The backtest chart is your demo — protect it.*
