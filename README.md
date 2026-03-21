# AgriSignal

Fertilizer price intelligence for farmers — powered by natural gas market data.

## Setup

```powershell
# 1. Install Python dependencies (use the venv, not system Python)
.\.venv\Scripts\pip install -r requirements.txt
```

## Running the project

**Step 1 — Train the ML models (run once):**
```powershell
.\.venv\Scripts\python backend/train_models.py
```

**Step 2 — Generate forecasts (run any time you want fresh data):**
```powershell
.\.venv\Scripts\python backend/run_pipeline.py
```

**Step 3 — Start the web server:**
```powershell
node backend/server.js
```

Open http://localhost:8000 in your browser.

## Notes

- Always use `.\.venv\Scripts\python` instead of `python` — the venv contains all required packages (xgboost, pandas, etc.)
- Re-run `run_pipeline.py` to refresh forecasts without retraining
- The server reads `data/processed/cache.json` on every request — no restart needed after running the pipeline
