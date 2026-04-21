# SAFE DSS Backend

Backend API for the SAFE sepsis decision support system.

## Scope

- PostgreSQL-friendly relational schema aligned to HW6/HW7 entities.
- Two-stage risk workflow:
  - Stage 1: early sepsis screening (6-12h horizon).
  - Stage 2: rapid deterioration prioritization on flagged cohort.
- Alert acknowledgment / override logging.
- Admin dashboard aggregate endpoints (4-5 lightweight charts).

## Stack

- FastAPI
- SQLAlchemy
- Pydantic
- Uvicorn

## Run

```bash
cd backend
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg2://safe_user:safe_pass@localhost:5432/safe_dss
STAGE1_MODEL_PATH=../analysis/outputs/sepsis_6_12h/rf_stage1_holdout.joblib
STAGE2_MODEL_PATH=../analysis/outputs/risk_severity_flagged/rf_stage2_holdout.joblib
STAGE1_HIGH_THRESHOLD=0.70
STAGE1_MODERATE_THRESHOLD=0.45
```

## Notes

- This backend now defaults to PostgreSQL for local development.
- If you need a quick local fallback, you can still use SQLite:
  `DATABASE_URL=sqlite:///./safe_dss.db`
