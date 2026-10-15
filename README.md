# GLC Zone CRM + ERP

FastAPI + MongoDB backend (`backend/server.py`) and a React frontend (`frontend/`), served by nginx under `/crm`.

## Run locally
```
cd backend && pip install -r requirements-dev.txt && cp .env.example .env   # fill in the values
uvicorn server:app --reload
cd frontend && yarn install && yarn start
```

## Tests
```
cd backend && python -m pytest -p no:cacheprovider -o addopts="" tests/ --ignore=tests/backend_test.py
```
They use an in-memory MongoDB; nothing touches a real database.

## Deploy (server)
```
cd /var/www/crm-glc-source && git pull --ff-only origin main
pip install -r backend/requirements.txt      # only when requirements changed
systemctl restart crm-backend
cd frontend && cp -r build build.bak && npm run build    # only when the UI changed
```
Do not open the CRM while the build runs (nginx has no `index.html` for a minute).

## Health
`GET /api/health` returns `{"status":"ok","db":"ok"}` when the API and database answer (503 otherwise). Use it for uptime monitoring.

## Gaps and status
See `docs/CRM_ERP_GAP_ANALYSIS.md`.
