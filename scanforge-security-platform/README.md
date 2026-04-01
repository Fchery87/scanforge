# ScanForge

ScanForge is a repository security platform for running multi-scanner code and dependency analysis, normalizing the results into a single finding model, and exposing the outcome through a web dashboard, REST API, and background workers.

It is built as a three-application monorepo:

- `apps/web`: Next.js 16 dashboard and onboarding flow
- `apps/api`: FastAPI backend, auth, persistence, and public/internal APIs
- `apps/worker`: Python workers that clone repositories, run scanners, upload artifacts, and persist findings

## What ScanForge Does

ScanForge is designed to solve the operational problem of security tooling fragmentation. Instead of making teams interpret separate outputs from different scanners, it:

- connects repositories to projects inside organizations
- triggers manual and scheduled scans
- runs multiple security scanners in the background
- normalizes scanner-specific JSON into a unified finding schema
- deduplicates findings across scans using canonical fingerprints
- stores scan history, scanner run metadata, raw artifacts, and triage state
- exposes findings, scorecards, notifications, exports, schedules, and audit data in one product surface

The codebase already includes support for:

- organization and project management
- repository onboarding, including GitHub integration
- full, diff, dependency, and secret-focused scan modes
- finding triage actions such as suppress, resolve, reopen, accept risk, duplicate marking, assignment, and due dates
- recurring scan schedules
- notifications
- export records and download endpoints
- scorecard and trend endpoints
- audit logs

## Architecture

ScanForge is structured as a web app, API, worker tier, and supporting infrastructure.

### Runtime Topology

```text
Browser
  -> Next.js web app
  -> FastAPI API
  -> Postgres

FastAPI API
  -> Redis queue
  -> Postgres
  -> GitHub APIs

Worker
  -> Redis queue
  -> repository clone
  -> scanners
  -> Cloudflare R2 / S3-compatible storage
  -> FastAPI internal endpoints
```

### Primary Infrastructure

- Frontend: Next.js 16, React 19, Tailwind 4, Radix UI primitives
- API: FastAPI, SQLAlchemy async, Alembic, Pydantic v2
- Worker: Python async orchestration with scanner adapters and normalizers
- Database: Neon Postgres in hosted environments, local Postgres via Docker
- Queue/cache: Upstash Redis in hosted environments, local Redis via Docker
- Artifact storage: Cloudflare R2 in hosted environments, MinIO locally
- Auth: Neon Auth JWT validation in the API, Neon client auth in the web app
- Hosting: Vercel for web, Render for API, worker, scheduler, and maintenance jobs

## Scan Pipeline

The scan execution path is split between the API and the worker.

### Request and Processing Flow

1. A user triggers a scan from the dashboard.
2. The API creates the `Scan` record and enqueues a Redis job.
3. The worker claims the job and fetches an authenticated clone URL from the internal API.
4. The worker clones the target repository into a temporary directory.
5. The worker selects scanners based on scan type.
6. Scanners run, generally in parallel, and each creates a `ScannerRun`.
7. Raw outputs and generated artifacts are uploaded to object storage.
8. Scanner-specific outputs are normalized into a common finding structure.
9. Findings are persisted through internal API endpoints.
10. The scan is marked completed or failed, and notifications can be emitted.

### Supported Scan Types

The current worker maps scan types to scanners as follows:

- `scan.repo.full`: `trivy`, `gitleaks`, `osv`, `semgrep`, `syft`, `checkov`, `grype`
- `scan.repo.diff`: `gitleaks`, `semgrep`, `checkov`
- `scan.dependencies`: `trivy`, `osv`, `syft`, `grype`
- `scan.secrets`: `gitleaks`

### Supported Scanners

The repo contains adapters and normalizers for:

- Trivy
- Gitleaks
- OSV-Scanner
- Semgrep
- Syft
- Checkov
- Grype

These scanners contribute different categories of findings, including:

- dependency vulnerabilities
- secrets exposure
- infrastructure misconfiguration
- code-level security issues
- SBOM-driven package analysis

## Core Domain Model

At a high level, ScanForge organizes data like this:

- users belong to organizations through memberships and role-based access
- organizations contain projects
- projects contain repositories
- repositories produce scans
- scans contain per-scanner runs and summary metadata
- normalized findings are stored and updated over time
- finding events, triage state, suppression/acceptance actions, and references are tracked separately

Important persisted concepts in the API include:

- organizations and members
- projects
- repositories
- scans
- scanner runs
- findings
- artifacts
- exports
- notifications
- audit events
- scan schedules
- organization integrations such as GitHub

## Monorepo Layout

```text
scanforge-security-platform/
├── apps/
│   ├── api/          FastAPI app, models, services, routes, migrations, tests
│   ├── web/          Next.js app, dashboard pages, auth client, UI components
│   └── worker/       scanner adapters, result normalizers, queue clients, worker entrypoints
├── docs/             architecture notes, setup docs, ADRs, rollout plans
├── infra/            deployment and infrastructure notes
├── packages/
│   └── contracts/    shared package placeholder for cross-app contracts/types
├── spec/             product, API, schema, roadmap, and workflow specifications
├── docker-compose.yml
├── Makefile
├── render.yaml
├── RUNNING_LOCALLY.md
└── README.md
```

## Application Overview

### `apps/web`

The web app is a Next.js 16 App Router application that provides:

- authentication entry points
- onboarding flow
- organization dashboard
- project and repository views
- scans list and scan detail pages
- findings list and finding drawer
- scorecard, audit logs, exports, notifications, and settings pages

The main client API wrapper lives in `apps/web/lib/api.ts` and mirrors the FastAPI routes the UI consumes.

### `apps/api`

The API app owns:

- authentication and RBAC
- persistence and database migrations
- organization, project, repository, scan, finding, schedule, export, and notification services
- GitHub integration endpoints
- public REST routes under `/api/v1`
- internal service endpoints used by workers

The route registry in `apps/api/app/api/v1/router.py` currently includes health, internal, webhooks, github, organizations, memberships, projects, repositories, schedules, scans, findings, exports, scorecard, suppression rules, notifications, audit logs, and findings trend endpoints.

### `apps/worker`

The worker app handles:

- claiming and updating queue jobs
- cloning repositories
- running scanners
- creating and updating scanner-run records through the internal API
- uploading raw outputs and artifacts to object storage
- normalizing scanner outputs
- persisting findings through the API
- sending completion or failure notifications

Additional worker entrypoints exist for:

- scheduled scan dispatch: `apps/worker/app/worker/scheduler.py`
- maintenance operations and queue cleanup: `apps/worker/app/worker/maintenance.py`

## Local Development

ScanForge supports local development with Docker-backed infrastructure and separate processes for each app.

### Prerequisites

- Node.js and npm
- Python 3.11+ or 3.12+
- Docker
- scanner binaries installed locally if you want to execute real scans

### 1. Create Local Environment File

```bash
cp .env.example .env
```

Then update `.env` with values that make sense for your environment.

### 2. Install Dependencies

```bash
make install
```

This installs:

- `apps/web` npm dependencies
- `apps/api` Python virtual environment and editable package install
- `apps/worker` Python virtual environment and editable package install

### 3. Start Local Infrastructure

```bash
make db-up
```

This starts local development infrastructure defined in `docker-compose.yml`:

- Postgres on `localhost:5432`
- Redis on `localhost:6379`
- MinIO on `localhost:9000`
- MinIO console on `http://localhost:9001`

LocalStack is also defined in `docker-compose.yml` as an optional service for S3-style API testing.

### 4. Run Migrations

```bash
make migrate
```

### 5. Start the Applications

Use separate terminals:

```bash
make api-dev
make web-dev
make worker-dev
```

Useful local URLs:

- web app: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API redoc: `http://localhost:8000/redoc`

### Local Development Commands

```bash
make help
make install
make db-up
make db-down
make scanner-install
make scanner-check
make migrate
make migrate-status
make web-dev
make api-dev
make worker-dev
make worker-purge-queue
make lint
make test
```

## Scanner Installation

Real scan execution requires the scanner CLIs to be available on the machine running the worker.

The repo includes helper documentation and install hints for:

- Trivy
- Gitleaks
- OSV-Scanner
- Syft
- Grype
- Checkov

See:

- `make scanner-install`
- `make scanner-check`
- [`docs/scanner-setup.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/docs/scanner-setup.md)

## Environment Variables

The canonical starter file is `.env.example`.

### Core Variables

- `DATABASE_URL`: async SQLAlchemy connection string for Postgres
- `APP_ENV`: development or production-style environment label
- `APP_URL`: base URL used by the API
- `CORS_ORIGINS`: comma-separated allowed frontend origins

### Frontend Runtime Variable

- `NEXT_PUBLIC_API_BASE_URL`: optional frontend base URL override used by the web app and Vercel deployment; if omitted locally, the web app falls back to `http://localhost:8000`

### Auth

- `NEON_AUTH_ISSUER`
- `NEON_AUTH_AUDIENCE`
- `NEON_AUTH_JWKS_URL`
- `NEON_AUTH_CLIENT_ID`
- `NEON_AUTH_CLIENT_SECRET`

### Queue

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

### Storage

- `R2_ENDPOINT`
- `R2_BUCKET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_PUBLIC_BASE_URL`

### GitHub Integration

- `GITHUB_APP_ID`
- `GITHUB_APP_SLUG`
- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `GITHUB_PRIVATE_KEY`
- `GITHUB_WEBHOOK_SECRET`

### Internal Service Auth and Notifications

- `INTERNAL_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SLACK_WEBHOOK_URL`

### Scanner Binary Overrides

- `TRIVY_BINARY`
- `GITLEAKS_BINARY`
- `OSV_SCANNER_BINARY`
- `SYFT_BINARY`
- `GRYPE_BINARY`

## API Surface

The public API is rooted at `/api/v1`. Major areas include:

- organizations and memberships
- projects
- repositories
- scans
- scan schedules
- findings and finding events
- exports
- scorecards
- notifications
- audit logs
- GitHub installation and integration endpoints
- health and webhook endpoints

Worker-only internal coordination happens through internal routes used to:

- fetch authenticated clone URLs
- update scan status
- create and update scanner runs
- persist normalized findings

## GitHub Integration

ScanForge includes GitHub App and OAuth integration support for repository onboarding.

The API contains flows for:

- generating GitHub App install URLs
- generating OAuth authorization URLs
- handling OAuth callback exchange
- saving organization-level GitHub integrations
- listing repositories available to the installation
- removing the stored integration

If you are wiring GitHub locally, also read [`RUNNING_LOCALLY.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/RUNNING_LOCALLY.md), which includes callback and setup guidance.

## Deployment

The repo ships with a `render.yaml` blueprint that defines:

- `scanforge-api`: FastAPI web service
- `scanforge-worker`: background worker
- `scanforge-scheduler`: cron job for due schedules
- `scanforge-maintenance`: cron job for cleanup and operational tasks

The intended hosted layout is:

- Vercel for `apps/web`
- Render for API and worker processes
- Neon Postgres
- Upstash Redis
- Cloudflare R2

## Testing and Quality

The repo includes:

- API tests in `apps/api/tests`
- worker tests in `apps/worker/tests`
- web library tests in `apps/web/lib/*.test.ts`
- lint commands via `make lint`
- migration commands via `make migrate*`

Examples:

```bash
make lint
make test
PYTHONPATH="$(pwd)/apps/api" apps/api/.venv/bin/pytest apps/api
PYTHONPATH="$(pwd)/apps/worker" apps/worker/.venv/bin/pytest apps/worker
```

## Recommended Reading

If you are new to the repo, these files are the best next steps:

- [`RUNNING_LOCALLY.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/RUNNING_LOCALLY.md)
- [`docs/SYSTEM_OVERVIEW.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/docs/SYSTEM_OVERVIEW.md)
- [`docs/development-setup.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/docs/development-setup.md)
- [`spec/PRD.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/spec/PRD.md)
- [`spec/API_OVERVIEW.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/spec/API_OVERVIEW.md)
- [`spec/SCANNER_PIPELINE.md`](/home/nochaserz/Documents/Coding%20Projects/scanforge/scanforge-security-platform/spec/SCANNER_PIPELINE.md)

## Current Status

This repository is beyond a skeleton. It contains working app surfaces, domain models, worker orchestration, migrations, and route coverage for the core ScanForge product. It is still an actively evolving codebase, so the README should be treated as a current orientation guide rather than a frozen contract.
