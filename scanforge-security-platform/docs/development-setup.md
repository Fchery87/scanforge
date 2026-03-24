# Development Setup Guide

This guide walks you through setting up ScanForge locally for development.

## Prerequisites

- [Docker & Docker Compose](https://docs.docker.com/get-docker/) — for Postgres, Redis, MinIO
- [Node.js 20+](https://nodejs.org/) — for the Next.js frontend
- [Python 3.12+](https://www.python.org/downloads/) — for the FastAPI backend and worker
- [pipx](https://pipx.pypa.io/) or `pip` — for Python package management
- A terminal — you'll run services in multiple terminals

## Quick Start

> **Database options:** The project is pre-configured to use **Neon** (cloud Postgres). If you want a fully local setup, update `DATABASE_URL` in `.env` to point to the local Docker Postgres instance (see Environment Configuration). Either way, run `make migrate` after choosing.

```bash
# 1. Clone and enter the project
cd scanforge-security-platform

# 2. Copy environment config
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL (Neon or local Docker)

# 3. Start local infrastructure (Postgres, Redis, MinIO)
make db-up

# 4. Install all dependencies
make install
# Note: on Ubuntu/Debian with system Python, you may need to use a virtualenv
# or run: pip install --break-system-packages -e ".[dev]" inside apps/api and apps/worker

# 5. Install scanner binaries (see Scanner Binaries section below)
make scanner-install

# 6. Run database migrations
make migrate

# 7. Start all services (in separate terminals)
make api-dev    # Terminal 1 → http://localhost:8000
make web-dev    # Terminal 2 → http://localhost:3000
make worker-dev # Terminal 3 → background worker
```

## Environment Configuration

Edit the `.env` file in the project root with the following local values:

```env
# ── Application ─────────────────────────────────────────────
APP_ENV=development
APP_NAME=ScanForge
APP_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000

# ── Database (local Postgres via Docker) ────────────────────
DATABASE_URL=postgresql+asyncpg://scanforge:scanforge_local@localhost:5432/scanforge

# ── Auth ───────────────────────────────────────────────────
# For local dev, you can use a mock JWT or set up Neon Auth
# See Auth section below for options

# ── Queue (local Redis via Docker) ─────────────────────────
# Note: the worker uses the Upstash HTTP REST client, not raw TCP.
# For local dev, leave these empty or point to a real Upstash free-tier instance.
# Raw Redis at localhost:6379 will NOT work with the Upstash REST client.
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-dev-token

# ── Storage (local MinIO via Docker) ───────────────────────
R2_ENDPOINT=http://localhost:9000
R2_BUCKET=scanforge-artifacts
R2_ACCESS_KEY_ID=scanforge
R2_SECRET_ACCESS_KEY=scanforge_local_storage
R2_PUBLIC_BASE_URL=http://localhost:9000/scanforge-artifacts

# ── CORS ───────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000
```

### Auth Options for Local Development

**Option A — Neon Auth (recommended for production parity)**
1. Create a project at [neon.tech](https://neon.tech)
2. Enable Auth in your Neon dashboard
3. Fill in `NEON_AUTH_*` variables in `.env`

**Option B — Mock Auth (fastest for pure local dev)**
Replace the auth middleware in `apps/api/app/middleware/auth.py` to accept a hardcoded test token, or skip auth entirely in dev mode by modifying the middleware to check `APP_ENV=development`.

**Option C — Auth0 / Clerk / Better Auth**
Set up any OIDC-compatible provider and configure the `auth` block in `apps/api/app/core/config.py`.

## Service Details

### API — FastAPI (port 8000)

```bash
make api-dev
# or directly:
cd apps/api && uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health
- Readiness: http://localhost:8000/api/v1/ready

Key files:
- `apps/api/app/main.py` — FastAPI app, middleware, exception handlers
- `apps/api/app/api/v1/router.py` — all route registrations
- `apps/api/app/db/models/` — SQLAlchemy ORM models
- `apps/api/app/services/` — business logic layer
- `apps/api/app/schemas/` — Pydantic request/response schemas

### Web — Next.js (port 3000)

```bash
make web-dev
# or directly:
cd apps/web && npm run dev
```

- Frontend: http://localhost:3000
- Redirects to `/dashboard` after auth

Key files:
- `apps/web/app/` — Next.js App Router pages
- `apps/web/app/(dashboard)/` — authenticated pages
- `apps/web/lib/api.ts` — typed API client (note: `lib/` is at `apps/web/lib/`, not inside `app/`)
- `apps/web/app/globals.css` — design system CSS variables

### Worker — Python background processor

```bash
make worker-dev
# or directly:
cd apps/worker && python -m app.worker.main
```

The worker:
- Polls the Redis queue for scan jobs
- Runs trivy, gitleaks, and osv-scanner
- Persists findings via the internal API
- Sends notifications on completion

Key files:
- `apps/worker/app/worker/main.py` — main worker loop
- `apps/worker/app/worker/scheduler.py` — cron-based scheduled scans
- `apps/worker/app/services/scan_orchestrator.py` — scan coordination
- `apps/worker/app/scanners/` — individual scanner wrappers

## Database

### Start / Stop

```bash
make db-up      # Start Postgres, Redis, MinIO
make db-down    # Stop all
make db-logs    # Tail container logs
```

### Migrations

```bash
make migrate              # Run all pending migrations
make migrate-generate name=my_change  # Generate a new migration
make migrate-status       # Show current state
make migrate-rollback     # Roll back one step
make migrate-reset        # Wipe all tables (DEV ONLY!)
```

### Direct Postgres Access

```bash
psql postgresql://scanforge:scanforge_local@localhost:5432/scanforge
```

## Scanner Binaries

Install these for local vulnerability and secret scanning:

### macOS (Homebrew)

```bash
brew install trivy gitleaks
go install github.com/google/osv-scanner/cmd/osv-scanner@latest
brew install anchore/syft/syft anchore/grype/grype
```

### Linux

```bash
# Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin trivy

# Gitleaks
curl -sfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_amd64.tar.gz | tar -xz -C /usr/local/bin

# osv-scanner
go install github.com/google/osv-scanner/cmd/osv-scanner@latest

# Syft
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh /dev/stdin -b /usr/local/bin

# Grype
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh /dev/stdin -b /usr/local/bin
```

### Verify Installation

```bash
make scanner-check
```

Expected output:
```
trivy: v0.x.x
gitleaks: v8.x.x
osv-scanner: v1.x.x
syft: v1.x.x
grype: v0.x.x
```

## Storage (MinIO Console)

MinIO provides S3-compatible object storage locally:

- **API**: http://localhost:9000
- **Console**: http://localhost:9001 (user: `scanforge`, pass: `scanforge_local_storage`)

Create a bucket named `scanforge-artifacts` in the MinIO console to match the `R2_BUCKET` env var.

## Common Tasks

### Add a new database model

1. Create `apps/api/app/db/models/your_model.py`
2. Add to `apps/api/app/db/models/__init__.py`
3. Run `make migrate-generate name=add_your_model`
4. Review the generated migration file
5. Run `make migrate`

### Add a new API endpoint

1. Create `apps/api/app/services/your_service.py` — business logic
2. Create `apps/api/app/api/v1/routes/your_endpoint.py` — FastAPI routes
3. Register in `apps/api/app/api/v1/router.py`
4. Add request/response schemas in `apps/api/app/schemas/`

### Add a new frontend page

1. Create `apps/web/app/(dashboard)/[org_id]/your-page/page.tsx`
2. Add navigation link in `apps/web/app/(dashboard)/layout.tsx` sidebar

## Troubleshooting

### Postgres connection refused

```bash
# Ensure Docker is running
docker ps | grep scanforge-db

# Restart the container
docker restart scanforge-db

# Check logs
docker logs scanforge-db
```

### "Module not found" errors on API/Worker

```bash
# Reinstall dependencies
cd apps/api && pip install -e ".[dev]"
cd apps/worker && pip install -e ".[dev]"
```

### Frontend build errors

```bash
cd apps/web && rm -rf .next && npm install && npm run dev
```

### Worker not picking up jobs

- Check Redis is running: `make db-logs | grep redis`
- Check queue length: the queue client has a `get_queue_length()` method
- Verify env vars: `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`

### Migrations out of sync

```bash
make migrate-status
# If head is behind, run:
make migrate
```

## Project Structure

```
scanforge-security-platform/
├── apps/
│   ├── api/                  # FastAPI backend
│   │   ├── alembic/          # Database migrations
│   │   │   └── versions/     # Migration files
│   │   └── app/
│   │       ├── main.py       # App entry point
│   │       ├── core/         # Config, security, webhook
│   │       ├── db/           # Models, session, enums
│   │       ├── schemas/      # Pydantic schemas
│   │       ├── services/     # Business logic
│   │       ├── middleware/   # Auth, RBAC, rate limiting
│   │       └── api/v1/       # Route handlers
│   ├── web/                  # Next.js frontend
│   │   ├── app/              # App Router pages
│   │   │   └── (dashboard)/  # Authenticated routes
│   │   ├── lib/              # API client, utils
│   │   └── public/           # Static assets
│   └── worker/               # Python background worker
│       ├── app/
│       │   ├── clients/       # Redis queue, R2 storage
│       │   ├── scanners/     # trivy, gitleaks, osv
│       │   ├── normalizers/   # Parse scanner output
│       │   ├── services/     # Orchestrator, notifications
│       │   └── worker/       # Main loop, scheduler
│       └── pyproject.toml
├── docs/                     # Architecture & ADR docs
├── infra/                    # Deployment configs (Render, Vercel)
├── docker-compose.yml        # Local dev services
├── render.yaml               # Render Blueprint
└── .env.example              # Environment template
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `make dev` | Show all services to start |
| `make install` | Install all dependencies |
| `make lint` | Run linting on all apps |
| `make test` | Run tests (if any exist) |
| `make scanner-check` | Verify scanner binaries |
| `make migrate-status` | Show migration state |
| `docker compose ps` | Show running containers |
| `docker compose logs -f` | Tail all container logs |
