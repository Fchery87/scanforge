# ScanForge Code Review

Last reviewed: 2026-04-04
Reviewer: OpenCode

> Superseded note: This file is a historical April 2026 code review snapshot. The current project overview and latest broad API/worker verification status are maintained in `../README.md` and `SYSTEM_OVERVIEW.md`.

## Project Understanding

ScanForge is a repository security operations platform for teams that want one workflow around code scanning instead of juggling raw output from multiple tools.

The current codebase is built around three main responsibilities:

- `apps/web`: authenticated product UI for onboarding, dashboards, findings, notifications, schedules, exports, scorecards, and settings
- `apps/api`: FastAPI service for auth, RBAC, persistence, queue handoff, GitHub integration, internal worker coordination, and domain APIs
- `apps/worker`: asynchronous job processor that clones repositories, runs multiple scanners, uploads artifacts, normalizes outputs, persists findings, and emits notifications

At a product level, the intended user flow is:

1. A user creates or joins an organization.
2. The user creates a project.
3. The organization connects a GitHub installation.
4. The user connects repositories into a project.
5. The user triggers manual scans or configures schedules.
6. The worker runs scanners and writes normalized findings.
7. The team triages findings, tracks trends, exports data, and reviews audit logs.

## Architecture Summary

- Auth: Neon Auth JWT validation in the API and Neon auth client usage in the web app
- Persistence: SQLAlchemy async models and Alembic migrations on Postgres
- Queueing: Upstash Redis REST API client for scan jobs and job status metadata
- Storage: S3-compatible object storage through Cloudflare R2 in hosted environments and MinIO locally
- Integrations: GitHub App installation and OAuth-assisted repository onboarding
- Scan execution: worker-side scanner adapters plus normalizers for Trivy, Gitleaks, OSV, Semgrep, Syft, Checkov, and Grype

## High-Confidence Findings

### High

1. `apps/worker/app/services/scan_orchestrator.py:85-93`
   Finding: `process_job` requires `org_id` in the queue payload, but worker tests still construct jobs without it, and one test now fails with `KeyError`.
   Impact: the queue contract between API, worker, and tests is drifting.
   Recommendation: centralize the queue payload schema and update tests to match the current contract.

2. `apps/api/app/api/v1/routes/github.py:77-91`
   Finding: invalid OAuth state handling now queries organizations before state validation finishes, and an authorization regression test fails because the route reaches the database path too early.
   Impact: broken contract coverage around a security-sensitive OAuth callback flow.
   Recommendation: make state parsing or validation fail fast before organization lookup where possible, or update the contract and tests deliberately.

3. `Makefile:188-195`
   Finding: the main validation targets swallow failures with `|| true`.
   Impact: local validation can look healthy even when checks fail, and these targets are unsafe as quality gates.
   Recommendation: make primary validation targets fail on errors and keep forgiving wrappers separate.

### Medium

4. `Makefile:140-147` and `apps/web/package.json:5-10`
   Finding: `make lint` invokes `next lint`, but the current Next 16 setup errors instead of providing useful frontend lint coverage.
   Impact: frontend linting is effectively absent.
   Recommendation: replace `next lint` with the intended ESLint command once configured.

5. `apps/worker/app/services/scan_orchestrator.py` and `apps/worker/tests/test_scan_orchestrator.py`
   Finding: the scan context contract changed and tests no longer reflect the live worker behavior.
   Impact: worker regressions are easier to ship because tests are not aligned with the runtime path.
   Recommendation: update tests together with queue and context schema changes.

6. `docs/SYSTEM_OVERVIEW.md`, `spec/API_OVERVIEW.md`, `spec/SCANNER_PIPELINE.md`, and removed top-level planning files
   Finding: parts of the documentation were still describing scaffold-era or intermediate implementation states.
   Impact: onboarding and architecture understanding were slowed by conflicting sources of truth.
   Recommendation: keep the root README and `docs/` as the active documentation surface and retire stale planning files when superseded.

### Low

7. `apps/api/app/core/security.py:92-103`
   Finding: non-production JWT diagnostics log selected token claims.
   Impact: acceptable for local debugging, but should remain tightly limited to non-production environments.
   Recommendation: keep production logging disabled and avoid expanding the claim set.

8. `apps/api/app/api/v1/routes/internal.py:176-210`
   Finding: the internal clone URL endpoint returns an authorization header for Git over HTTPS.
   Impact: acceptable only because the route is internal and worker-side redaction exists.
   Recommendation: preserve strict service auth and redaction controls on all related paths.

## Security Posture Snapshot

The repo shows solid baseline intent:

- JWT verification is centralized.
- internal routes require service auth.
- security headers and rate limiting middleware are wired in.
- worker logs redact internal API keys and Git auth headers.
- authorization checks exist across organization and project surfaces.

The main current security concern is correctness drift in security-sensitive flows such as OAuth callbacks, internal worker contracts, and validation enforcement, not an obvious critical exploit in the reviewed code.

## Validation Snapshot

Observed on this review run:

- API tests: `82 passed, 1 failed`
- Worker tests: `28 passed, 2 failed`
- API lint: multiple Ruff violations
- Worker lint: multiple Ruff violations
- Web lint: currently not functioning through `next lint`

## Recommended Next Actions

1. Fix the GitHub OAuth callback regression and the worker queue contract test failures.
2. Replace the web lint command with a working lint path.
3. Make `make lint` and `make test` fail loudly for true validation use.
4. Keep documentation centered on current runtime behavior, not historical implementation plans.
