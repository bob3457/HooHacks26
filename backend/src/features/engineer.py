"""
Feature engineering — takes the ingestion dict and produces the feature store.
All features are derived exclusively from ng_spot, urea, dap, and storage.
Targets use negative shifts (look-forward) and are never used as input features.
"""

import os
import pandas as pd
import numpy as np

_THIS = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.normpath(os.path.join(_THIS, "..", "..", ".."))
DATA  = os.path.join(ROOT, "data")

FEATURE_COLS = [
    # Raw + lags
    "ng_spot",
    "ng_lag1", "ng_lag2", "ng_lag3", "ng_lag4", "ng_lag5", "ng_lag6",
    "ng_lag9", "ng_lag12",
    # Monthly rolling stats
    "ng_rolling_mean_3m", "ng_rolling_mean_6m", "ng_rolling_mean_12m",
    "ng_rolling_std_3m",  "ng_rolling_std_6m",  "ng_rolling_std_12m",
    # Monthly momentum
    "ng_mom_1m", "ng_mom_3m", "ng_mom_6m",
    # Daily-derived MA features (computed from Henry Hub daily data)
    "ng_ma30_eom", "ng_ma60_eom", "ng_ma90_eom",
    "ng_ma_cross_30_60", "ng_ma_cross_30_90",
    "ng_daily_vol_1m",
    # Urea features
    "urea_lag1", "urea_rolling_mean_3m", "urea_ng_ratio",
    "urea_mom_1m", "urea_mom_3m",
    # Mean-reversion features (key directional signals for commodities)
    "urea_zscore_12m", "urea_zscore_24m",
    "urea_vs_12m_high", "urea_vs_12m_low",
    "ng_zscore_12m",
    # DAP features
    "dap_lag1", "dap_urea_ratio",
    # Storage
    "storage_zscore",
    # Seasonality
    "season_q1", "season_q2", "season_q3", "season_q4",
]

TARGET_COLS = ["target_urea_t1", "target_urea_t2", "target_urea_t3"]


def _load_daily_ng_features() -> pd.DataFrame:
    """
    Load daily Henry Hub data and return monthly-aggregated MA features.
    All three MA files contain identical raw daily data — we just use the 30-day file.
    Returns empty DataFrame if file is missing.
    """
    path = os.path.join(DATA, "RNGWHHDd_henry_hub_nat_gas_spot_price_30_day_moving.xls")
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Data 1", header=2)
        df.columns = ["date", "price"]
        df["date"]  = pd.to_datetime(df["date"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna().set_index("date").sort_index()

        # Daily rolling MAs (calendar-day windows, min_periods = half window)
        df["ma30"] = df["price"].rolling(30,  min_periods=15).mean()
        df["ma60"] = df["price"].rolling(60,  min_periods=30).mean()
        df["ma90"] = df["price"].rolling(90,  min_periods=45).mean()

        # Aggregate to month-start: end-of-month value for MAs, std for volatility
        monthly = pd.DataFrame({
            "ng_ma30_eom":    df["ma30"].resample("MS").last(),
            "ng_ma60_eom":    df["ma60"].resample("MS").last(),
            "ng_ma90_eom":    df["ma90"].resample("MS").last(),
            "ng_daily_vol_1m": df["price"].resample("MS").std(),
        })

        # MA crossover signals: >0 = short-term trend above long-term (bullish)
        monthly["ng_ma_cross_30_60"] = monthly["ng_ma30_eom"] / monthly["ng_ma60_eom"] - 1
        monthly["ng_ma_cross_30_90"] = monthly["ng_ma30_eom"] / monthly["ng_ma90_eom"] - 1

        return monthly
    except Exception as exc:
        print(f"     [features] Daily NG load failed ({exc}) — skipping daily features.")
        return pd.DataFrame()


def build_features(data: dict) -> pd.DataFrame:
    """
    Takes dict from run_ingestion(), returns wide feature-store DataFrame.
    Rows with all-NaN targets (last 3 rows) are kept — they are used for
    out-of-sample prediction; drop them only during model training.
    """
    df = pd.DataFrame(data)

    # ── Nat gas lags (1–6 monthly + 9 and 12 for seasonality)
    for lag in [1, 2, 3, 4, 5, 6, 9, 12]:
        df[f"ng_lag{lag}"] = df["ng_spot"].shift(lag)

    # ── Rolling stats (3m, 6m, 12m)
    df["ng_rolling_mean_3m"]  = df["ng_spot"].rolling(3).mean()
    df["ng_rolling_mean_6m"]  = df["ng_spot"].rolling(6).mean()
    df["ng_rolling_mean_12m"] = df["ng_spot"].rolling(12).mean()
    df["ng_rolling_std_3m"]   = df["ng_spot"].rolling(3).std()
    df["ng_rolling_std_6m"]   = df["ng_spot"].rolling(6).std()
    df["ng_rolling_std_12m"]  = df["ng_spot"].rolling(12).std()

    # ── Momentum (% change)
    df["ng_mom_1m"] = df["ng_spot"].pct_change(1)
    df["ng_mom_3m"] = df["ng_spot"].pct_change(3)
    df["ng_mom_6m"] = df["ng_spot"].pct_change(6)

    # ── Daily-derived MA features — join by month-start index
    daily_feats = _load_daily_ng_features()
    if not daily_feats.empty:
        df = df.join(daily_feats, how="left")
    else:
        # Fall back to monthly proxies so training rows aren't dropped
        df["ng_ma30_eom"]      = df["ng_rolling_mean_3m"]
        df["ng_ma60_eom"]      = df["ng_rolling_mean_6m"]
        df["ng_ma90_eom"]      = df["ng_rolling_mean_6m"]
        df["ng_ma_cross_30_60"] = df["ng_rolling_mean_3m"] / df["ng_rolling_mean_6m"] - 1
        df["ng_ma_cross_30_90"] = df["ng_rolling_mean_3m"] / df["ng_rolling_mean_6m"] - 1
        df["ng_daily_vol_1m"]  = df["ng_rolling_std_3m"]

    # ── Urea features
    df["urea_lag1"]            = df["urea"].shift(1)
    df["urea_rolling_mean_3m"] = df["urea"].rolling(3).mean()
    df["urea_ng_ratio"]        = df["urea"] / df["ng_spot"]
    df["urea_mom_1m"]          = df["urea"].pct_change(1)
    df["urea_mom_3m"]          = df["urea"].pct_change(3)

    # ── Mean-reversion features — where is urea/NG relative to recent history?
    # High z-score = overextended high → more likely to fall (and vice versa)
    urea_mean_12m = df["urea"].rolling(12).mean()
    urea_std_12m  = df["urea"].rolling(12).std()
    urea_mean_24m = df["urea"].rolling(24).mean()
    urea_std_24m  = df["urea"].rolling(24).std()
    df["urea_zscore_12m"]  = (df["urea"] - urea_mean_12m) / urea_std_12m
    df["urea_zscore_24m"]  = (df["urea"] - urea_mean_24m) / urea_std_24m
    df["urea_vs_12m_high"] = df["urea"] / df["urea"].rolling(12).max()   # 1.0 = at 12m high
    df["urea_vs_12m_low"]  = df["urea"] / df["urea"].rolling(12).min()   # 1.0 = at 12m low
    ng_mean_12m = df["ng_spot"].rolling(12).mean()
    ng_std_12m  = df["ng_spot"].rolling(12).std()
    df["ng_zscore_12m"] = (df["ng_spot"] - ng_mean_12m) / ng_std_12m

    # ── DAP features
    df["dap_lag1"]      = df["dap"].shift(1)
    df["dap_urea_ratio"] = df["dap"] / df["urea"]

    # ── Storage z-score (low = tight supply = upward price pressure)
    storage_mean = df["storage_mmcf"].mean()
    storage_std  = df["storage_mmcf"].std()
    df["storage_zscore"] = (df["storage_mmcf"] - storage_mean) / storage_std

    # ── Season dummies (quarter indicators)
    df["season_q1"] = df.index.month.isin([1, 2, 3]).astype(int)
    df["season_q2"] = df.index.month.isin([4, 5, 6]).astype(int)
    df["season_q3"] = df.index.month.isin([7, 8, 9]).astype(int)
    df["season_q4"] = df.index.month.isin([10, 11, 12]).astype(int)

    # ── Targets — negative shifts look FORWARD in time
    # These are NaN for the last 1/2/3 rows respectively
    df["target_urea_t1"] = df["urea"].shift(-1)
    df["target_urea_t2"] = df["urea"].shift(-2)
    df["target_urea_t3"] = df["urea"].shift(-3)

    return df


def save_feature_store(df: pd.DataFrame) -> str:
    out_dir = os.path.join(ROOT, "data", "processed")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "feature_store.parquet")
    df.to_parquet(path)
    return path


def load_feature_store() -> pd.DataFrame:
    path = os.path.join(ROOT, "data", "processed", "feature_store.parquet")
    return pd.read_parquet(path)
