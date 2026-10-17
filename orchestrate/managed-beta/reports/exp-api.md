# apps/api convention map (coordinator-persisted from explorer report 62f0e81f)

1. Project root in the worktree is `scanforge-managed-beta/scanforge-security-platform/` (the git root is the parent repo). FastAPI app in `app/main.py`, router at `/api/v1` via `app/api/v1/router.py`.
2. Middleware order: SecurityHeaders → Audit → RedisRateLimit (120 rpm, burst 20, Upstash) → CORS; global 500 handler returns a generic message.
3. Scan lifecycle: `scan_lifecycle.py` (creation/dispatch), `scan_completion.py` (evidence/receipts), `scan_lease.py` (R09 lease). Access policy in `access_policies.py`; audit in `audit_logs.py`; GitHub in `github.py` plus pure `github_checks.py`/`github_pr_advisory.py`; findings in `findings.py` plus pure `finding_lifecycle.py`.
4. Identity/provenance today: Scan carries commit_sha, base_sha, attempt_id, lease fields. Finding has uq (repository_id, canonical_fingerprint). ScanArtifact has storage_uri + checksum_sha256. Repository has provider/full_name/external_repo_id.
5. Alembic: script at `apps/api/alembic`, linear chain, single head `0022_webhook_event_digest`.
6. Queue contract (`QueueJob`, `SCAN_JOB_TYPES`, scan_id as idempotency key) is manually duplicated between apps/api and apps/worker; only a one-word comment differs; no automated sync check.
7. Tests: no `conftest.py` anywhere; zero shared fixtures. Test style is SimpleNamespace/AsyncMock/monkeypatch unit tests; route tests use `app.dependency_overrides[get_current_user]` plus httpx ASGITransport; real infra only env-gated per test (e.g. `R04_POSTGRES_URL`). All plan-named suites exist including both queue-contract suites.
8. Auth: JWT via PyJWKClient against `NEON_AUTH_JWKS_URL` with issuer/audience settings (config.py lines 31–33, default empty; audience enforced in beta/production). Worker auth via `X-Worker-Credential` → peppered `WorkerIdentityService` → org-scoped `WorkerPrincipal`. Scheduler via constant-time `X-Scheduler-Key`.
9. OpenAPI: `python scripts/emit_openapi.py` writes `apps/api/openapi.json`; route-publishing contract tests keep it in sync.
10. Gap for briefs: no conftest means new integration suites must create their own fixtures or introduce a shared conftest deliberately.
