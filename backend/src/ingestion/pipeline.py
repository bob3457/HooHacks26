"""
Data ingestion layer — loads all data sources, normalizes to a monthly
DatetimeIndex, and returns a clean dict of pd.Series ready for feature engineering.

For natural gas spot price and storage, the EIA API v2 is tried first so the
pipeline picks up the latest available month automatically.  If the API call
fails (no key, network error, rate-limit) the code falls back to the local
static files that ship with the repo.

Urea and DAP still come from the World Bank Pink Sheet Excel file — no free
live source exists for those commodities.
"""

import os
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Resolve paths relative to this file regardless of cwd
_THIS  = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.normpath(os.path.join(_THIS, "..", "..", ".."))
DATA   = os.path.join(ROOT, "data")

# Load .env from project root (picks up EIA_API_KEY)
load_dotenv(os.path.join(ROOT, ".env"))

_EIA_KEY = os.getenv("EIA_API_KEY", "")


# ── EIA API helpers ────────────────────────────────────────────────────────────

def _fetch_eia_ng_spot() -> pd.Series | None:
    """
    Fetch US natural gas wellhead price ($/MCF ≈ $/MMBtu) from EIA API v2.
    Uses duoarea=NUS + process=FWA (Wellhead Acquisition Price) — the correct
    v2 facet equivalent of the retired v1 series RNGWHHD.
    Returns None on any failure.
    """
    if not _EIA_KEY:
        return None
    try:
        r = requests.get(
            "https://api.eia.gov/v2/natural-gas/pri/sum/data/",
            params={
                "api_key":              _EIA_KEY,
                "frequency":            "monthly",
                "data[0]":              "value",
                "facets[duoarea][]":    "NUS",
                "facets[process][]":    "FWA",
                "facets[product][]":    "EPG0",
                "sort[0][column]":      "period",
                "sort[0][direction]":   "desc",
                "length":               360,
            },
            timeout=25,
        )
        r.raise_for_status()
        rows = r.json()["response"]["data"]
        if not rows:
            print("     [EIA] NG spot — empty response, using local file.")
            return None
        s = pd.Series(
            {pd.Timestamp(row["period"] + "-01"): float(row["value"]) for row in rows},
            name="ng_spot",
        ).sort_index()
        print(f"     [EIA] NG spot fetched — latest: {s.index[-1].strftime('%Y-%m')} (${s.iloc[-1]:.2f}/MCF)")
        return s
    except Exception as exc:
        print(f"     [EIA] NG spot fetch failed ({exc}) — using local file.")
        return None


def _fetch_eia_ng_storage() -> pd.Series | None:
    """
    Fetch US underground working gas storage (MMcf) from EIA API v2.
    Route: natural-gas/stor/sum/dcu/nus/m  — returns None on any failure.
    EIA returns values in Bcf; we convert to MMcf (* 1000) to match local file.
    """
    if not _EIA_KEY:
        return None
    try:
        r = requests.get(
            "https://api.eia.gov/v2/natural-gas/stor/sum/dcu/nus/m/data/",
            params={
                "api_key":              _EIA_KEY,
                "frequency":            "monthly",
                "data[0]":              "value",
                "sort[0][column]":      "period",
                "sort[0][direction]":   "desc",
                "length":               360,
            },
            timeout=25,
        )
        r.raise_for_status()
        rows = r.json()["response"]["data"]
        s = pd.Series(
            {pd.Timestamp(row["period"] + "-01"): float(row["value"]) * 1000
             for row in rows},
            name="storage_mmcf",
        ).sort_index()
        print(f"     [EIA] Storage fetched — latest: {s.index[-1].strftime('%Y-%m')} ({s.iloc[-1]:,.0f} MMcf)")
        return s
    except Exception as exc:
        print(f"     [EIA] Storage fetch failed ({exc}) — using local file.")
        return None


# ── Local file loaders (fallback) ─────────────────────────────────────────────

def load_ng_monthly() -> pd.Series:
    """Henry Hub monthly spot price ($/MMBtu) — local CSV fallback."""
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
    path = os.path.join(DATA, "raw", "CMO-Historical-Data-Monthly-2026.xlsx")
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
    """EIA underground storage working gas (MMcf), monthly — local XLS fallback."""
    path = os.path.join(DATA, "series_data", "NG_SUM_LSUM_DCU_NUS_M.xls")
    df = pd.read_excel(path, sheet_name="Data 4", header=2)
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")
    df.index = df.index.to_period("M").to_timestamp()

    col = next(c for c in df.columns if "Working Gas" in str(c))
    series = pd.to_numeric(df[col], errors="coerce").rename("storage_mmcf")
    return series


def run_ingestion(start: str = "2018-01", end: str | None = None) -> dict:
    """
    Returns dict with keys:
      'ng_spot'      — monthly Henry Hub spot price ($/MMBtu)
      'urea'         — monthly urea price ($/mt)
      'dap'          — monthly DAP price ($/mt)
      'storage_mmcf' — monthly underground storage working gas (MMcf)

    EIA API is tried first for NG spot and storage so the latest available
    month is always included.  Falls back to local static files on failure.

    If end is None, the index extends to the latest month present in the data
    so no observations are left on the table.
    """
    # Natural gas spot — EIA live, then local CSV
    ng = _fetch_eia_ng_spot() or load_ng_monthly()

    # Storage — EIA live, then local XLS
    stor = _fetch_eia_ng_storage() or load_ng_storage()

    # Fertilizer prices — World Bank only (no free live source)
    fert = load_fertilizer_prices()

    # Determine end date: use latest month present across all series
    if end is None:
        end = min(
            ng.dropna().index.max(),
            fert["urea"].dropna().index.max(),
            fert["dap"].dropna().index.max(),
            stor.dropna().index.max(),
        ).strftime("%Y-%m")

    idx = pd.date_range(start=start, end=end, freq="MS")

    return {
        "ng_spot":      ng.reindex(idx).rename("ng_spot"),
        "urea":         fert["urea"].reindex(idx).rename("urea"),
        "dap":          fert["dap"].reindex(idx).rename("dap"),
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
