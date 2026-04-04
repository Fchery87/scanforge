# API

FastAPI backend for ScanForge.

## Responsibilities

- JWT authentication and user bootstrap
- organization, membership, project, repository, scan, finding, export, notification, and audit APIs
- GitHub integration and webhook handling
- internal worker coordination routes
- scan artifact download redirects

## Main Entry Points

- app: `app.main:app`
- router: `app/api/v1/router.py`
- services: `app/services/`
- models: `app/db/models/`

## Run Locally

```bash
PYTHONPATH="$(pwd)/apps/api" apps/api/.venv/bin/uvicorn app.main:app --reload --port 8000
```
