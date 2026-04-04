# ScanForge

ScanForge is a monorepo for a repository security operations platform. It connects source repositories to organizations and projects, runs multiple scanners through background workers, normalizes the output into one findings model, and exposes the results through a web application and REST API.

## What The Product Is For

The main use case is reducing scanner fragmentation for internal engineering and security teams.

Instead of asking teams to read separate outputs from tools like Trivy, Gitleaks, OSV, Semgrep, Syft, Checkov, and Grype, ScanForge gives them one place to:

- organize repositories by organization and project
- trigger manual scans and configure recurring schedules
- review normalized findings and per-scan scanner runs
- triage findings through suppression, resolution, accept-risk, duplicate, assignment, and due-date actions
- track notifications, scorecards, audit history, exports, and trend views

## Monorepo Layout

```text
scanforge-security-platform/
├── apps/
│   ├── api/      FastAPI service, models, services, routes, migrations, tests
│   ├── web/      Next.js 16 dashboard and onboarding UI
│   └── worker/   queue consumer, scanner adapters, normalizers, scheduler, maintenance
├── docs/         current operational documentation and code review notes
├── infra/        deployment and provider-specific notes
├── packages/     shared package space
├── spec/         compact product and technical specifications
├── docker-compose.yml
├── Makefile
├── render.yaml
└── README.md
```

## Runtime Architecture

```text
Browser
  -> Next.js web app
  -> FastAPI API

FastAPI API
  -> Postgres
  -> Upstash Redis REST queue
  -> GitHub APIs
  -> Cloudflare R2 / S3-compatible storage

Worker
  -> Upstash Redis REST queue
  -> internal API endpoints
  -> temporary repository clone
  -> scanner binaries
  -> Cloudflare R2 / MinIO
```

## Stack

- Frontend: Next.js 16, React 19, Tailwind 4, Radix UI, Framer Motion
- API: FastAPI, SQLAlchemy async, Alembic, Pydantic v2, PyJWT
- Worker: Python async coordination around subprocess-driven scanners
- Database: Neon Postgres in hosted environments, Docker Postgres locally
- Queue: Upstash Redis REST API client
- Storage: Cloudflare R2 in hosted environments, MinIO locally
- Auth: Neon Auth JWT verification in the API and Neon auth client usage in the web app
- Hosting target: Vercel for web, Render for API and worker services

## Applications

### `apps/web`

The web app is the user-facing control plane. It currently includes:

- dashboard shell and navigation
- onboarding flow
- GitHub callback flow
- project, repository, findings, scans, notifications, and profile surfaces
- a client API layer in `apps/web/lib/api.ts` mirroring backend routes

### `apps/api`

The API owns:

- JWT-based user identification and user record creation
- organization, membership, project, repository, schedule, scan, finding, export, and notification services
- GitHub App installation and OAuth-related endpoints
- internal worker endpoints for scan status, scanner runs, clone URLs, and finding persistence
- rate limiting, security headers, and audit middleware

The API router is registered in `apps/api/app/api/v1/router.py`.

### `apps/worker`

The worker owns:

- queue polling and job status updates
- repository cloning through internal API-issued credentials
- scanner selection by scan type
- artifact upload to S3-compatible storage
- scanner output normalization
- internal API persistence of findings and scan state
- notification dispatch, scheduled work, and maintenance utilities

The main worker entrypoint is `apps/worker/app/worker/main.py`.

## Scan Flow

1. A user triggers a scan from the UI.
2. The API creates a `Scan` record and enqueues a queue job.
3. The worker dequeues the job and marks the scan running.
4. The worker requests an authenticated clone URL from the internal API.
5. The repository is cloned into a temporary directory.
6. The worker selects scanners based on the requested scan type.
7. Raw outputs and generated artifacts are uploaded to object storage.
8. Normalizers map scanner-specific output into the shared finding shape.
9. Findings are persisted through internal API routes.
10. The scan summary is finalized and notifications may be sent.

### Current Scan Type Mapping

- `scan.repo.full`: `trivy`, `gitleaks`, `osv`, `semgrep`, `syft`, `checkov`, `grype`
- `scan.repo.diff`: `gitleaks`, `semgrep`, `checkov`
- `scan.dependencies`: `trivy`, `osv`, `syft`, `grype`
- `scan.secrets`: `gitleaks`

## Core Domain Model

The main persisted entities are:

- `users`
- `organizations`
- `organization_members`
- `projects`
- `repositories`
- `repository_integrations`
- `scans`
- `scanner_runs`
- `findings`
- `finding_instances`
- `finding_references`
- `finding_events`
- `suppression_rules`
- `finding_suppressions`
- `scan_artifacts`
- `exports`
- `notifications`
- `audit_logs`
- `scan_schedules`
- `webhook_deliveries`

Conceptually:

- users join organizations with role-based access
- organizations contain projects
- projects contain repositories
- repositories produce scans
- scans contain scanner runs and summary metadata
- findings are the long-lived deduplicated issue record
- finding instances and events track scan-to-scan occurrence and user actions over time

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.11+ or 3.12+
- Docker
- scanner binaries if you want real scan execution

### Setup

```bash
cp .env.example .env
make install
make db-up
make migrate
```

Then run the three main processes in separate terminals:

```bash
make api-dev
make web-dev
make worker-dev
```

Useful URLs:

- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API ReDoc: `http://localhost:8000/redoc`
- MinIO console: `http://localhost:9001`

### Important Local Note

The worker uses the Upstash REST API client, not a raw Redis TCP client. Local Redis from Docker is useful for compatibility context, but queue-backed worker behavior still depends on valid `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` unless you change the queue implementation.

## Environment Variables

Start from `.env.example`.

Key groups:

- App: `APP_ENV`, `APP_NAME`, `APP_URL`, `CORS_ORIGINS`
- Frontend runtime: `NEXT_PUBLIC_API_BASE_URL`
- Database: `DATABASE_URL`
- Auth: `NEON_AUTH_ISSUER`, `NEON_AUTH_AUDIENCE`, `NEON_AUTH_JWKS_URL`, `NEON_AUTH_CLIENT_ID`, `NEON_AUTH_CLIENT_SECRET`
- Queue: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
- Storage: `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PUBLIC_BASE_URL`
- GitHub: `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_STATE_SIGNING_SECRET`
- Internal and notifications: `INTERNAL_API_KEY`, `SMTP_*`, `SLACK_WEBHOOK_URL`
- Scanner binaries: `TRIVY_BINARY`, `GITLEAKS_BINARY`, `OSV_SCANNER_BINARY`, `SYFT_BINARY`, `GRYPE_BINARY`, `SEMGREP_BINARY`, `CHECKOV_BINARY`

## Validation Status From This Review

Observed during the 2026-04-04 review pass:

- API tests: `82 passed, 1 failed`
- Worker tests: `28 passed, 2 failed`
- API lint: failing Ruff checks
- Worker lint: failing Ruff checks
- Web lint: `next lint` is not currently functioning as configured in this repo

Current high-confidence issues are recorded in `docs/CODE_REVIEW.md`.

## Recommended Reading

- `docs/README.md`
- `docs/CODE_REVIEW.md`
- `docs/SYSTEM_OVERVIEW.md`
- `docs/development-setup.md`
- `docs/scanner-setup.md`
- `RUNNING_LOCALLY.md`
- `spec/README.md`

## Current Status

This is not a scaffold anymore. The repo contains a working domain model, a substantial API surface, a functional worker orchestration layer, UI surfaces for the main product flows, and a meaningful test suite.

It is also still an actively evolving codebase. Documentation in this repository aims to describe current behavior, known gaps, and integration expectations rather than present the system as fully finished.
