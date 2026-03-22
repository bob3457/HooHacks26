# Gas Forecast

Fertilizer price intelligence for farmers — powered by natural gas market data.

## Setup

```powershell
# Install Python dependencies (use the venv, not system Python)
.\.venv\Scripts\pip install -r requirements.txt
```

## Running the project

**Step 1 — Train the ML models (run once):**
```powershell
.\.venv\Scripts\python backend/train_models.py
```
Only needs to be re-run if you change training data or model code.

**Step 2 — Ingest data & generate forecasts (run any time you want fresh data):**
```powershell
.\.venv\Scripts\python backend/run_pipeline.py
```

Open http://localhost:8000 in your browser.

## Running the UI
    inside the venv, call streamlit run login.py
    
## Running with Docker

The easiest way to run the app — no Python setup required.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

```bash
# 1. Copy the env file and add your API key
cp .env.example .env
# Edit .env and set EIA_API_KEY=your_key_here

# 2. Build and start
docker-compose up --build

# 3. Open http://localhost:8501
```

User accounts persist across restarts via Docker volumes. To stop: `docker-compose down`.

---

## Notes

- Always use `.\.venv\Scripts\python` instead of `python` — the venv contains all required packages (xgboost, pandas, etc.)
- Re-run `run_pipeline.py` to refresh forecasts without retraining
- The server reads `data/processed/cache.json` on every request — no restart needed after running the pipeline
