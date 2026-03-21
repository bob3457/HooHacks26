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

FEATURE_COLS = [
    "ng_spot",
    "ng_lag1", "ng_lag2", "ng_lag3", "ng_lag4",
    "ng_rolling_mean_3m", "ng_rolling_mean_6m",
    "ng_rolling_std_3m",  "ng_rolling_std_6m",
    "ng_mom_1m", "ng_mom_3m", "ng_mom_6m",
    "urea_lag1", "urea_rolling_mean_3m", "urea_ng_ratio",
    "dap_lag1",
    "storage_zscore",
    "season_q1", "season_q2", "season_q3", "season_q4",
]

TARGET_COLS = ["target_urea_t1", "target_urea_t2", "target_urea_t3"]


def build_features(data: dict) -> pd.DataFrame:
    """
    Takes dict from run_ingestion(), returns wide feature-store DataFrame.
    Rows with all-NaN targets (last 3 rows) are kept — they are used for
    out-of-sample prediction; drop them only during model training.
    """
    df = pd.DataFrame(data)

    # ── Nat gas lags
    for lag in [1, 2, 3, 4]:
        df[f"ng_lag{lag}"] = df["ng_spot"].shift(lag)

    # ── Rolling stats
    df["ng_rolling_mean_3m"] = df["ng_spot"].rolling(3).mean()
    df["ng_rolling_mean_6m"] = df["ng_spot"].rolling(6).mean()
    df["ng_rolling_std_3m"]  = df["ng_spot"].rolling(3).std()
    df["ng_rolling_std_6m"]  = df["ng_spot"].rolling(6).std()

    # ── Momentum (% change)
    df["ng_mom_1m"] = df["ng_spot"].pct_change(1)
    df["ng_mom_3m"] = df["ng_spot"].pct_change(3)
    df["ng_mom_6m"] = df["ng_spot"].pct_change(6)

    # ── Urea features
    df["urea_lag1"]            = df["urea"].shift(1)
    df["urea_rolling_mean_3m"] = df["urea"].rolling(3).mean()
    df["urea_ng_ratio"]        = df["urea"] / df["ng_spot"]

    # ── DAP lag (correlated with urea — adds signal)
    df["dap_lag1"] = df["dap"].shift(1)

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
