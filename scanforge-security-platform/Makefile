.PHONY: help install dev lint test migrate migrate-generate migrate-rollback migrate-status migrate-reset \
        web-install web-dev web-build web-lint \
        api-install api-dev \
        worker-install worker-dev worker-prod \
        db-up db-down db-logs \
        scanner-install scanner-check

help:
	@echo "ScanForge — Available commands"
	@echo ""
	@echo "  Setup"
	@echo "    make install           Install all dependencies (web + api + worker)"
	@echo "    make scanner-install  Install scanner binaries (trivy, gitleaks, osv-scanner)"
	@echo "    make db-up            Start local database with docker-compose"
	@echo "    make db-down          Stop local database"
	@echo ""
	@echo "  Development"
	@echo "    make dev              Run all services (see individual targets below)"
	@echo "    make web-dev          Next.js dev server on :3000"
	@echo "    make api-dev          FastAPI dev server on :8000"
	@echo "    make worker-dev       Worker process (foreground)"
	@echo ""
	@echo "  Migrations"
	@echo "    make migrate                  Run pending migrations"
	@echo "    make migrate-generate name=X Generate new migration"
	@echo "    make migrate-status          Show migration status"
	@echo "    make migrate-rollback        Roll back one migration"
	@echo "    make migrate-reset           Roll back all migrations (DEV ONLY)"
	@echo ""
	@echo "  Build"
	@echo "    make web-build        Build Next.js app"
	@echo "    make lint             Lint all apps"
	@echo ""
	@echo "  Production"
	@echo "    make worker-prod      Run worker in production mode"

# ─── Venv helpers ────────────────────────────────────────────────────
# Each Python app gets its own .venv inside its directory.
API_VENV   = apps/api/.venv
WORKER_VENV = apps/worker/.venv
API_PIP    = $(API_VENV)/bin/pip
WORKER_PIP  = $(WORKER_VENV)/bin/pip
API_PYTHON  = $(API_VENV)/bin/python
WORKER_PYTHON = $(WORKER_VENV)/bin/python
API_ALEMBIC = $(API_VENV)/bin/alembic
API_UVICORN = $(API_VENV)/bin/uvicorn
API_GUNICORN = $(API_VENV)/bin/gunicorn
API_RUFF    = $(API_VENV)/bin/ruff
WORKER_RUFF = $(WORKER_VENV)/bin/ruff

# ─── Setup ───────────────────────────────────────────────────────────

install:
	cd apps/web && npm install
	python3 -m venv $(API_VENV)
	$(API_PIP) install --upgrade pip
	$(API_PIP) install -e "apps/api[dev]"
	python3 -m venv $(WORKER_VENV)
	$(WORKER_PIP) install --upgrade pip
	$(WORKER_PIP) install -e "apps/worker[dev]"

scanner-install:
	@echo "Installing scanner binaries..."
	@echo ""
	@echo "macOS (Homebrew):"
	@echo "  brew install trivy gitleaks"
	@echo "  go install github.com/google/osv-scanner/cmd/osv-scanner@latest"
	@echo "  brew install anchore/syft/syft anchore/grype/grype"
	@echo ""
	@echo "Linux:"
	@echo "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin trivy"
	@echo "  curl -sfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_amd64.tar.gz | tar -xz -C /usr/local/bin"
	@echo "  go install github.com/google/osv-scanner/cmd/osv-scanner@latest"
	@echo "  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh /dev/stdin -b /usr/local/bin"
	@echo "  curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh /dev/stdin -b /usr/local/bin"

scanner-check:
	@echo "Checking scanner versions..."
	@for bin in trivy gitleaks osv-scanner syft grype; do \
		version=$$($$bin version 2>/dev/null | head -1 || echo "NOT FOUND"); \
		echo "  $$bin: $$version"; \
	done

# ─── Database ────────────────────────────────────────────────────────

db-up:
	docker compose up -d postgres redis minio
	@echo "Waiting for services..."
	@sleep 5
	@echo "Postgres:   localhost:5432 (user: scanforge / pass: scanforge_local)"
	@echo "Redis:      localhost:6379"
	@echo "MinIO:      localhost:9000 (user: scanforge / pass: scanforge_local_storage)"
	@echo "MinIO Console: http://localhost:9001"

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres redis

# ─── Migrations ───────────────────────────────────────────────────────

migrate:
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini upgrade head

migrate-generate:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make migrate-generate name=your_migration_name"; \
		exit 1; \
	fi
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini revision --autogenerate -m "$(name)"

migrate-rollback:
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini downgrade -1

migrate-rollback-to:
	@if [ -z "$(revision)" ]; then \
		echo "Usage: make migrate-rollback-to revision=0001_identity_and_access"; \
		exit 1; \
	fi
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini downgrade $(revision)

migrate-status:
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini current
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini history

migrate-reset:
	@echo "WARNING: This will drop ALL tables. Development only!"
	PYTHONPATH="$(PWD)/apps/api" $(API_ALEMBIC) -c apps/api/alembic.ini downgrade base

# ─── Web ──────────────────────────────────────────────────────────────

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build

web-lint:
	cd apps/web && npm run lint

# ─── API ─────────────────────────────────────────────────────────────

api-install:
	python3 -m venv $(API_VENV)
	$(API_PIP) install --upgrade pip
	$(API_PIP) install -e "apps/api[dev]"

api-dev:
	PYTHONPATH="$(PWD)/apps/api" $(API_UVICORN) app.main:app --reload --port 8000

api-prod:
	PYTHONPATH="$(PWD)/apps/api" $(API_GUNICORN) app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# ─── Worker ──────────────────────────────────────────────────────────

worker-install:
	python3 -m venv $(WORKER_VENV)
	$(WORKER_PIP) install --upgrade pip
	$(WORKER_PIP) install -e "apps/worker[dev]"

worker-dev:
	PYTHONPATH="$(PWD)/apps/worker" $(WORKER_PYTHON) -m app.worker.main

worker-prod:
	PYTHONPATH="$(PWD)/apps/worker" $(WORKER_PYTHON) -m app.worker.main --concurrency=4

# ─── All-in-one dev ─────────────────────────────────────────────────

dev: db-up
	@echo ""
	@echo "Starting all services in separate terminals:"
	@echo "  Terminal 1: make web-dev    → http://localhost:3000"
	@echo "  Terminal 2: make api-dev    → http://localhost:8000"
	@echo "  Terminal 3: make worker-dev → (background worker)"
	@echo ""

lint:
	cd apps/web && npm run lint || true
	$(API_RUFF) check apps/api/app || true
	$(WORKER_RUFF) check apps/worker/app || true

test:
	PYTHONPATH="$(PWD)/apps/api" $(API_PYTHON) -m pytest apps/api || true
	PYTHONPATH="$(PWD)/apps/worker" $(WORKER_PYTHON) -m pytest apps/worker || true
