# ScanForge

ScanForge is a repository security operations platform. It connects GitHub repositories to organizations and projects, runs multiple security scanners through a background worker, normalizes scanner output into one finding model, and exposes triage, scan history, scorecards, notifications, exports, and audit data through a web app and REST API.

The current product focus is centralized security triage for internal engineering and security teams. GitHub pull request feedback is implemented as advisory feedback, not blocking enforcement.

## What ScanForge Does

ScanForge reduces scanner fragmentation by giving teams one workflow for repository security review.

- Onboard organizations, projects, and GitHub repositories.
- Trigger manual scans and scheduled scans through one scan lifecycle path.
- Run Trivy, Gitleaks, OSV-Scanner, Semgrep, Syft, Checkov, and Grype.
- Normalize scanner results into durable findings, finding instances, references, and events.
- Track scanner-level health separately from overall scan status.
- Triage findings with explicit workflow states instead of overloaded suppression semantics.
- Prioritize work with transparent risk score, repository importance, and SLA preview signals.
- View scorecards for exposure, trend direction, SLA pressure, scanner reliability, and advisory policy status.
- Generate deterministic remediation guidance from scanner evidence and references.
- Store raw artifacts in S3-compatible object storage and expose downloads through presigned API redirects.
- Process GitHub webhook and pull request events into advisory diff-scan feedback.

## Monorepo Layout

```text
scanforge-security-platform/
├── apps/
│   ├── api/      FastAPI service, SQLAlchemy models, Alembic migrations, services, routes, tests
│   ├── web/      Next.js dashboard, onboarding, auth, and security operations UI
│   └── worker/   queue consumer, scanner adapters, normalizers, scheduler, maintenance tools
├── docs/         operational docs, ADRs, and implementation plans
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
  -> Postgres system of record
  -> Upstash Redis REST queue
  -> GitHub App and webhook APIs
  -> Cloudflare R2 / S3-compatible artifact storage

Worker
  -> Upstash Redis REST queue
  -> internal API endpoints protected by service auth
  -> temporary repository clone
  -> scanner binaries on disk
  -> Cloudflare R2 / MinIO artifact storage
```

The API owns durable state and authorization. The worker consumes queue jobs, asks the API for authoritative scan execution context, clones repositories, runs scanners, uploads artifacts, normalizes results, and persists findings through internal API routes.

## Stack

- Frontend: Next.js 16, React 19, Tailwind 4, Radix UI, Framer Motion, Recharts
- API: FastAPI, SQLAlchemy async, Alembic, Pydantic v2, PyJWT, boto3
- Worker: Python async orchestration around subprocess-driven scanners
- Database: Neon Postgres in hosted environments, Docker Postgres locally
- Queue: Upstash Redis REST API client
- Storage: Cloudflare R2 in hosted environments, MinIO locally
- Auth: Neon Auth JWT verification in the API and Neon auth client usage in the web app
- Hosting target: Vercel for web, Render for API and worker services

## Applications

### Web App

The web app is the user-facing control plane. It includes authentication/account pages, onboarding, dashboard navigation, organization and project surfaces, repository pages, scan history and scan detail pages, findings triage, scorecard, suppressions, exports, audit logs, notifications, profile, and GitHub callback handling.

Key UI surfaces include scanner health indicators, scan summary cards, finding tables, finding details, risk score display, remediation guidance, saved finding filters, suppression impact previews, and responsive dashboard components.

### API

The API owns the system-of-record domain model and public/internal HTTP surface.

- User identity and Neon Auth JWT verification
- Organizations, memberships, projects, repositories, repository integrations, and onboarding state
- Scan creation, scan schedules, scan status, scanner runs, and artifact downloads
- Finding persistence, finding detail, workflow transitions, triage metadata, suppressions, trends, and exports
- Risk scoring, SLA preview, scorecard data, advisory policy evaluation, and remediation guidance
- GitHub App installation support, webhook verification, webhook replay protection, and pull request advisory scan creation
- Internal worker endpoints for execution context, repository clone credentials, scanner-run updates, scan status updates, and finding persistence
- Rate limiting, security headers, RBAC, audit middleware, and sanitized error responses

### Worker

The worker owns scan execution.

- Poll queue jobs using the Upstash Redis REST client.
- Validate queue payloads that carry a minimal execution identity.
- Load scan execution context from the API instead of trusting duplicated queue data.
- Clone repositories using API-issued GitHub App credentials.
- Select scanners based on scan mode.
- Run scanners concurrently, record per-scanner status, timeout, duration, version, errors, and artifacts.
- Upload raw outputs and scanner artifacts to S3-compatible storage.
- Normalize scanner-specific output into canonical finding candidates.
- Filter diff scan findings to changed files when applicable.
- Persist findings through internal API routes.
- Finalize scan summaries with scanner health, seen fingerprints, scope, changed files, duration, and artifact references.
- Retry failed jobs and move exhausted jobs to the dead-letter queue path.

## Scan Lifecycle

All scan triggers use the same lifecycle service.

```text
queued -> running -> completed
                  -> failed
                  -> canceled
```

Scan creation enqueues a minimal queue payload containing the scan identity. The worker then retrieves authoritative context from the API, including organization, project, repository, branch, commit, expected scanners, and coverage scope.

End-to-end scan flow:

1. A user, schedule, webhook, or pull request event creates a scan.
2. The API persists the scan and enqueues a scan job.
3. The worker claims the job and marks the scan running.
4. The worker loads execution context from the internal API.
5. The worker requests clone credentials and clones the repository.
6. Diff scans collect changed files.
7. The worker runs the selected scanners and records scanner runs.
8. Raw outputs and artifacts are uploaded to object storage.
9. Normalizers produce canonical finding candidates.
10. Findings are persisted through the internal API.
11. The scan is finalized with scanner health and summary metadata.
12. Notifications may be sent.

### Scan Types

- `full`: full repository scan, queued as `scan.repo.full`
- `diff`: pull request or changed-file scan, queued as `scan.repo.diff`
- `dependencies`: dependency-focused scan, queued as `scan.dependencies`
- `secrets`: secret-focused scan, queued as `scan.secrets`

### Scanner Mapping

- `scan.repo.full`: `trivy`, `gitleaks`, `osv`, `semgrep`, `syft`, `checkov`, `grype`
- `scan.repo.diff`: `gitleaks`, `semgrep`, `checkov`
- `scan.dependencies`: `trivy`, `osv`, `syft`, `grype`
- `scan.secrets`: `gitleaks`

## Finding Lifecycle

Findings are long-lived records deduplicated from normalized scanner output. Finding instances record scan-specific occurrences, and finding events record user or system actions.

Workflow states are explicit:

- `open`
- `reviewing`
- `to_fix`
- `accepted_risk`
- `false_positive`
- `duplicate`
- `not_observed`
- `fixed`

`not_observed` means a finding was previously seen but was absent from a later relevant scan. It is not the same as fixed. ScanForge only marks missing findings as not observed when the relevant scanner completed with comparable coverage. Fixed promotion requires policy evidence, currently repeated not-observed evidence, rather than a single disappearance.

Risk score is intentionally transparent. It combines severity, scanner confidence, workflow state, and repository importance into a 0-100 score. Repository importance can be `critical`, `high`, `normal`, or `low`.

SLA preview is advisory. Accepted risk, false positive, duplicate, and fixed findings are exempt. Active findings with due dates are classified as overdue, due soon, or on track.

Remediation guidance is deterministic and evidence-driven. Dependency findings with fixed versions produce upgrade-oriented guidance; other findings produce scanner-evidence review steps and reference links.

## Scorecards And Policy Evaluation

Scorecards summarize repository security operations for an organization or project. They include exposure, trend direction, SLA pressure, scanner health, noisy scanner indicators, high-risk repositories or projects, and advisory policy results.

Policy evaluation is read-only and non-blocking. Advisory policy results can fail when risk score averages are high, SLA-overdue work exists, or scans have partial scanner health. These results are designed to build trust before any future merge-blocking policy gates.

## GitHub Workflow

GitHub is the primary SCM integration. ScanForge supports GitHub App installation metadata, repository connection, clone credential issuance, webhook verification, webhook replay protection, and pull request advisory scan creation.

Pull request workflows currently create advisory diff scans and policy feedback. They do not block merges. The project intentionally prioritizes GitHub depth before adding GitLab or Bitbucket support.

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

- Users join organizations through role-based membership.
- Organizations contain projects.
- Projects contain repositories.
- Repositories produce scans.
- Scans contain scanner runs and summary metadata.
- Scanner runs expose health, errors, durations, versions, and downloadable artifacts.
- Findings are durable deduplicated issue records.
- Finding instances and events preserve scan evidence and lifecycle history.

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.11+ or 3.12+
- Docker
- Scanner binaries if you want real scan execution

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

### Queue Note

The worker uses the Upstash Redis REST API client, not a raw Redis TCP client. Docker Redis is useful for local infrastructure parity, but queue-backed worker behavior still depends on valid `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` unless the queue implementation is changed.

## Environment Variables

Start from `.env.example`.

Key groups:

- App: `APP_ENV`, `APP_NAME`, `APP_URL`, `PORT`, `CORS_ORIGINS`
- Frontend runtime: `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_API_BASE_URL` when configured
- Database: `DATABASE_URL`
- Auth: `NEON_AUTH_ISSUER`, `NEON_AUTH_AUDIENCE`, `NEON_AUTH_JWKS_URL`, `NEON_AUTH_CLIENT_ID`, `NEON_AUTH_CLIENT_SECRET`
- Queue: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
- Storage: `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PUBLIC_BASE_URL`
- GitHub: `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_STATE_SIGNING_SECRET`
- Internal service auth: `INTERNAL_API_KEY`
- Notifications: `SMTP_*`, `SLACK_WEBHOOK_URL`
- Scanner binaries: `TRIVY_BINARY`, `GITLEAKS_BINARY`, `OSV_SCANNER_BINARY`, `SYFT_BINARY`, `GRYPE_BINARY`, `SEMGREP_BINARY`, `CHECKOV_BINARY`

## Common Commands

```bash
make help
make install
make db-up
make migrate
make api-dev
make web-dev
make worker-dev
make scanner-check
make lint
make test
```

For direct Python test runs, run from the app directory with `PYTHONPATH=.`:

```bash
cd apps/api && PYTHONPATH=. pytest tests
cd apps/worker && PYTHONPATH=. pytest tests
```

## Current Verification Status

Fresh verification from the completed module-first roadmap pass:

- API tests: `119 passed`
- Worker tests: `40 passed`

The broad test suites cover scan lifecycle contracts, scanner health, finding workflow transitions, not-observed and fixed promotion policy, risk scoring, SLA preview, scorecard policy output, GitHub PR advisory behavior, remediation guidance, artifact download contracts, queue contracts, authorization, rate limiting, webhook security, scanner registry behavior, worker orchestration, normalizers, notifications, scheduler, and maintenance commands.

## Implementation Status

ScanForge is not a scaffold. The repository contains a working domain model, API surface, worker orchestration layer, Next.js dashboard surfaces, migrations, and broad automated tests.

The module-first security operations roadmap is implemented through its final reliability pass. Completed capabilities include stable scan creation, scan execution context, scanner health, explicit finding workflow states, safe not-observed handling, fixed promotion policy, risk scoring, repository importance, SLA preview, upgraded scorecards, advisory policy evaluation, GitHub PR advisory foundation, remediation guidance, and end-to-end reliability verification.

Still-deferred areas include hard merge blocking, AI-generated fixes, MCP exposure, manual arbitrary scan import, broader vulnerability-management asset modeling, and non-GitHub SCM integrations.

## Recommended Reading

- `docs/README.md`
- `docs/SYSTEM_OVERVIEW.md`
- `docs/development-setup.md`
- `docs/scanner-setup.md`
- `RUNNING_LOCALLY.md`
- `docs/adr/ADR-004-finding-lifecycle-policy.md`
- `docs/plans/2026-05-02-module-first-security-operations-roadmap.md`
- `spec/README.md`
