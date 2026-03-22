# Docker Containerization Design

**Date:** 2026-03-22
**Project:** AgriSignal / Gas Forecast (HooHacks26)
**Scope:** Containerize the Streamlit app for local use and easy sharing

---

## Context

AgriSignal is a Streamlit web app that forecasts natural gas and fertilizer (urea) prices for farmers. It uses pre-trained XGBoost models and a cached forecast pipeline. The goal is to make it trivially runnable on any machine via Docker.

---

## Approach

Single container, everything baked in. Models, data, and code are all included in the image. SQLite databases are mounted as named volumes for persistence across restarts.

---

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the image from `python:3.13-slim` |
| `docker-compose.yml` | Wires up ports, volumes, and env file |
| `.dockerignore` | Excludes `.venv`, `.git`, `__pycache__`, etc. |

### Dockerfile

- Base: `python:3.13-slim`
- Install deps from `requirements.txt` first (layer caching)
- Copy all project source files
- Bake in `data/models/` (trained `.pkl` files) and `data/processed/cache.json`
- Expose port `8501`
- Entrypoint: `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`

### docker-compose.yml

- Service: `agrisignal`
- Build from local `Dockerfile`
- Port: `8501:8501`
- Named volumes:
  - `users_db` → `/app/users.db` (user accounts persist across restarts)
  - `agrisignal_db` → `/app/backend/agrisignal.db`
- `env_file: .env` for secrets (EIA_API_KEY, SMTP, etc.)
- `restart: unless-stopped`

### .dockerignore

Excludes: `.venv/`, `.git/`, `__pycache__/`, `*.pyc`, `users.db`, `backend/agrisignal.db`, `.env`

---

## Data Flow

1. User copies `.env.example` → `.env` and fills in secrets
2. `docker-compose up --build` builds the image and starts the container
3. Streamlit app starts on `http://localhost:8501`
4. `users.db` and `agrisignal.db` live in named Docker volumes — persist across `docker-compose down` / `up`

---

## Usage Instructions (for README)

```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up --build
# Open http://localhost:8501
```

---

## Trade-offs & Constraints

- **Image size**: Will be ~2–3 GB due to ML dependencies (numpy, xgboost, scikit-learn, etc.). Acceptable for hackathon use.
- **Static models**: Forecast models are baked in at build time. To refresh, rebuild the image after running `train_models.py` + `run_pipeline.py` locally.
- **No FastAPI server**: FastAPI is in requirements but has no running server in the codebase — not included in the container entrypoint.
