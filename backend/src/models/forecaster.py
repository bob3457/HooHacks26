"""
XGBoost fertilizer price forecasting model.
Trains three separate models — one per horizon (t1=30d, t2=60d, t3=90d).
Uses walk-forward (time-series) cross-validation to prevent data leakage.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error
import xgboost as xgb

from src.features.engineer import FEATURE_COLS, TARGET_COLS

_THIS      = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.normpath(os.path.join(_THIS, "..", "..", ".."))
MODELS_DIR = os.path.join(ROOT, "data", "models")

XGB_PARAMS = {
    "n_estimators":     300,
    "max_depth":        4,       # Shallow — prevents overfitting on small dataset
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "objective":        "reg:squarederror",
    "random_state":     42,
    "n_jobs":           -1,
}


def _rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((np.array(y_true) - np.array(y_pred)) ** 2)))


def _directional_accuracy(y_true, y_pred, y_prev):
    """Fraction of periods where the predicted direction matches the actual direction."""
    actual_dir = np.sign(np.array(y_true) - np.array(y_prev))
    pred_dir   = np.sign(np.array(y_pred) - np.array(y_prev))
    mask = actual_dir != 0
    if mask.sum() == 0:
        return 0.5
    return float(np.mean(actual_dir[mask] == pred_dir[mask]))


def train(feature_store: pd.DataFrame) -> dict:
    """
    Trains 3 XGBoost models using walk-forward CV. Saves models + metadata.

    Data splits (per spec):
      Training window : 2018-01 -> 2021-06  (42 months)
      Validation       : 2021-07 -> 2022-12  (includes the 2022 spike)
      Test holdout     : 2023-01 -> 2024-12  (final evaluation only)
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Only rows where ALL features AND ALL targets are defined
    df_train = feature_store.dropna(subset=FEATURE_COLS + TARGET_COLS)

    metadata = {
        "training_window_start": "2018-01",
        "training_window_end":   "2024-12",
        "feature_cols":          FEATURE_COLS,
    }

    for horizon, target_col in enumerate(TARGET_COLS, start=1):
        y = df_train[target_col]
        X = df_train[FEATURE_COLS]

        train_val_mask = df_train.index <= "2022-12-01"
        X_tv = X[train_val_mask]
        y_tv = y[train_val_mask]

        # Walk-forward CV — gap=1 prevents boundary leakage
        tscv = TimeSeriesSplit(n_splits=5, gap=1)
        cv_residuals = []
        cv_preds_all = []
        cv_true_all  = []

        for tr_idx, vl_idx in tscv.split(X_tv):
            X_tr, X_vl = X_tv.iloc[tr_idx], X_tv.iloc[vl_idx]
            y_tr, y_vl = y_tv.iloc[tr_idx], y_tv.iloc[vl_idx]

            m = xgb.XGBRegressor(**XGB_PARAMS)
            m.fit(X_tr, y_tr, eval_set=[(X_vl, y_vl)], verbose=False)
            preds = m.predict(X_vl)

            cv_residuals.extend((y_vl.values - preds).tolist())
            cv_preds_all.extend(preds.tolist())
            cv_true_all.extend(y_vl.values.tolist())

        # Final model trained on all train+val data
        model = xgb.XGBRegressor(**XGB_PARAMS)
        model.fit(X_tv, y_tv)

        # Persist
        model_path = os.path.join(MODELS_DIR, f"xgb_urea_t{horizon}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Residual distribution (for Monte Carlo draws)
        residuals = np.array(cv_residuals)
        metadata[f"residual_mean_t{horizon}"] = float(residuals.mean())
        metadata[f"residual_std_t{horizon}"]  = float(residuals.std())

        # Test-set metrics (2023-2024 holdout)
        test_mask = df_train.index >= "2023-01-01"
        if test_mask.sum() > 0:
            X_test, y_test = X[test_mask], y[test_mask]
            test_preds = model.predict(X_test)
            y_prev     = df_train.loc[test_mask, "urea"].shift(1).values
            metadata[f"test_rmse_t{horizon}"] = _rmse(y_test, test_preds)
            metadata[f"test_mae_t{horizon}"]  = float(mean_absolute_error(y_test, test_preds))
            metadata[f"test_dir_acc_t{horizon}"] = _directional_accuracy(
                y_test.values, test_preds, y_prev
            )

        print(
            f"  t{horizon}: residual_std=${residuals.std():.1f} | "
            f"test_rmse=${metadata.get(f'test_rmse_t{horizon}', 0):.1f}"
        )

    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Models saved -> {MODELS_DIR}")
    return metadata


def load_models() -> tuple[dict, dict]:
    """Returns (models_dict, metadata). models_dict keys: 't1', 't2', 't3'."""
    models = {}
    for h in [1, 2, 3]:
        path = os.path.join(MODELS_DIR, f"xgb_urea_t{h}.pkl")
        with open(path, "rb") as f:
            models[f"t{h}"] = pickle.load(f)

    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(meta_path) as f:
        metadata = json.load(f)

    return models, metadata


def predict(models: dict, feature_row: pd.DataFrame) -> dict:
    """
    Given a single-row DataFrame with FEATURE_COLS, returns point forecasts.
    """
    X = feature_row[FEATURE_COLS]
    return {
        "t1": float(models["t1"].predict(X)[0]),
        "t2": float(models["t2"].predict(X)[0]),
        "t3": float(models["t3"].predict(X)[0]),
    }
