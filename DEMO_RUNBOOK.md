# SAFE Demo Runbook

This runbook is for teammates to run the SAFE demo locally with:
- PostgreSQL (Docker)
- FastAPI backend
- Streamlit frontend

It uses commands and defaults already used in this repo.

## 1) Prerequisites

- Python 3.11+ (3.12 works)
- Docker Desktop (or Docker Engine) running
- 3 terminal windows/tabs

Repo root assumed as:

```bash
cd /path/to/safe_dss
```

---

## 2) Start PostgreSQL (Docker)

### Option A (recommended): single `docker run`

```bash
docker rm -f safe-postgres 2>/dev/null || true
docker run -d \
  --name safe-postgres \
  -e POSTGRES_DB=safe_dss \
  -e POSTGRES_USER=safe_user \
  -e POSTGRES_PASSWORD=safe_pass \
  -p 5432:5432 \
  postgres:16
```

Check DB is up:

```bash
docker ps --filter "name=safe-postgres"
```

### Option B: docker compose (if your team prefers compose)

If your local clone does not already include a compose file, create one:

```bash
cat > docker-compose.yml <<'EOF'
services:
  db:
    image: postgres:16
    container_name: safe-postgres
    environment:
      POSTGRES_DB: safe_dss
      POSTGRES_USER: safe_user
      POSTGRES_PASSWORD: safe_pass
    ports:
      - "5432:5432"
    volumes:
      - safe_pg_data:/var/lib/postgresql/data
volumes:
  safe_pg_data:
EOF
```

Start it:

```bash
docker compose up -d
```

Stop it:

```bash
docker compose down
```

---

## 3) Start Backend API (Terminal 1)

From repo root:

```bash
cd deployment/backend_dev/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend should be available at:

- API root: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

Notes:
- Backend default DB connection is:
  `postgresql+psycopg2://safe_user:safe_pass@localhost:5432/safe_dss`
- If your teammate uses a different DB host/port, set env vars as needed before launch.

---

## 4) Start Frontend App (Terminal 2)

From repo root:

```bash
cd deployment/frontend/SAFE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set backend URL (optional, default already points to localhost:8000):

```bash
export SAFE_API_BASE_URL=http://127.0.0.1:8000
```

Run Streamlit:

```bash
streamlit run app.py
```

Frontend should open at:

- `http://localhost:8501`

---

## 5) Demo Login Credentials

Use role matching these users:

- Admin login:
  - username: `admin`
  - password: `demo`
  - role: `admin`

- Clinician login:
  - username: `clinician`
  - password: `demo`
  - role: `clinician`

---

## 6) Quick Demo Script (5-10 min)

1. Login as `clinician`.
2. Open a low-risk/moderate patient, click **Update**, enter abnormal vitals/labs, save.
3. Confirm patient moves to **High** tier and alert workflow appears.
4. Acknowledge 1-2 high-risk alerts.
5. Discharge a patient and confirm they disappear from clinician queue.
6. Login as `admin`, verify:
   - High-risk count
   - Avg risk score
   - Alert response rate reflects acknowledged high-risk alerts

---

## 7) Troubleshooting

- Frontend cannot connect to backend:
  - verify backend terminal is running `uvicorn app.main:app --reload`
  - verify `SAFE_API_BASE_URL` points to `http://127.0.0.1:8000`

- DB connection errors in backend:
  - verify Postgres container is running
  - verify DB credentials match:
    `safe_user` / `safe_pass` / `safe_dss`

- Port already in use:
  - Backend (`8000`) or frontend (`8501`) may be occupied.
  - Stop old process or run on different port.

---

## 8) Stop Everything

Terminal 1/2:
- `Ctrl+C` to stop backend/frontend.

If using Docker run:

```bash
docker rm -f safe-postgres
```

If using docker compose:

```bash
docker compose down
```

