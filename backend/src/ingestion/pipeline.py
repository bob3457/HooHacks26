"""
Data ingestion layer — loads all local data sources, normalizes to a monthly
DatetimeIndex, and returns a clean dict of pd.Series ready for feature engineering.
"""

import os
import pandas as pd
import numpy as np

# Resolve paths relative to this file regardless of cwd
_THIS  = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.normpath(os.path.join(_THIS, "..", "..", ".."))
DATA   = os.path.join(ROOT, "data")


def load_ng_monthly() -> pd.Series:
    """Henry Hub monthly spot price ($/MMBtu)."""
    path = os.path.join(DATA, "natural-gas-prices", "monthly.csv")
    df = pd.read_csv(path)
    df["Month"] = pd.to_datetime(df["Month"])
    df = df.set_index("Month").sort_index()
    series = df["Price"].ffill()
    series.index = series.index.to_period("M").to_timestamp()
    return series.rename("ng_spot")


def load_fertilizer_prices() -> pd.DataFrame:
    """
    World Bank Pink Sheet — Urea and DAP monthly prices ($/mt).
    Returns DataFrame with columns ['urea', 'dap'], DatetimeIndex (month-start).
    """
    path = os.path.join(DATA, "raw", "CMO-Historical-Data-Monthly.xlsx")
    raw = pd.read_excel(path, sheet_name="Monthly Prices", header=4, index_col=0)
    # Row 0 after the header is the units row — drop it
    raw = raw.iloc[1:]

    fert = raw[["Urea ", "DAP"]].copy()
    fert.columns = ["urea", "dap"]
    fert = fert.apply(pd.to_numeric, errors="coerce")

    # Index format: '1960M01' → parse to Timestamp
    def _parse(s):
        try:
            year, month = str(s).strip().split("M")
            return pd.Timestamp(f"{year}-{month}-01")
        except Exception:
            return pd.NaT

    fert.index = fert.index.map(_parse)
    fert = fert[fert.index.notna()].sort_index()
    # Forward-fill up to 2 consecutive missing months (World Bank has occasional gaps)
    fert = fert.ffill(limit=2)
    return fert


def load_ng_storage() -> pd.Series:
    """EIA underground storage working gas (MMcf), monthly."""
    path = os.path.join(DATA, "series_data", "NG_SUM_LSUM_DCU_NUS_M.xls")
    df = pd.read_excel(path, sheet_name="Data 4", header=2)
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")
    df.index = df.index.to_period("M").to_timestamp()

    col = next(c for c in df.columns if "Working Gas" in str(c))
    series = pd.to_numeric(df[col], errors="coerce").rename("storage_mmcf")
    return series


def run_ingestion(start: str = "2018-01", end: str = "2024-12") -> dict:
    """
    Returns dict with keys:
      'ng_spot'  — monthly Henry Hub spot price ($/MMBtu)
      'urea'     — monthly urea price ($/mt)
      'dap'      — monthly DAP price ($/mt)
      'storage'  — monthly underground storage working gas (MMcf)
    All series share a common monthly DatetimeIndex from start to end.
    """
    ng   = load_ng_monthly()
    fert = load_fertilizer_prices()
    stor = load_ng_storage()

    idx = pd.date_range(start=start, end=end, freq="MS")

    return {
        "ng_spot": ng.reindex(idx).rename("ng_spot"),
        "urea":    fert["urea"].reindex(idx).rename("urea"),
        "dap":     fert["dap"].reindex(idx).rename("dap"),
        "storage_mmcf": stor.reindex(idx).rename("storage_mmcf"),
    }


def load_full_history() -> dict:
    """
    Same as run_ingestion but returns all available history (no date clipping).
    Used to build the historical chart payload.
    """
    ng   = load_ng_monthly()
    fert = load_fertilizer_prices()
    return {"ng_spot": ng, "urea": fert["urea"], "dap": fert["dap"]}
