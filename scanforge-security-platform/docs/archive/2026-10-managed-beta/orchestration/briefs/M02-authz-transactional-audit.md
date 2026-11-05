# M02 — Authorize target resources before writes; persist audit atomically

Depends on: M00 (fixtures, venvs, branch). Serialized after M01 in the API track (one writer per track). Status: brief ready; spawn gated on the pilot contract and M01 completion.

## GOAL

Every sensitive mutation verifies authority on the exact target resource before any write lands, sensitive audit records commit in the same transaction as the domain mutation, and membership lifecycle gains verified pending invitations plus atomic owner transfer.

## SCOPE

Work in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform` on branch `managed-beta/integration`.

- Services: `apps/api/app/services/access_policies.py`, `organizations.py`, `memberships.py`, `users.py`, `findings.py`, `audit_logs.py`, `worker_identities.py`.
- Middleware: `apps/api/app/middleware/auth.py`, `audit.py`, `service_auth.py`; the relevant routes and `apps/api/app/schemas/memberships.py`.
- Alembic: one additive revision for invitation and owner-transfer records, ONLY if the existing models cannot carry them. Inspect `alembic history` first; the current head is `0022_webhook_event_digest` unless M01 landed anything after. You are the single migration writer while spawned.
- Tests: extend `test_authorization_regressions.py`, `test_route_integration_authorization.py`, `test_internal_service_org_boundaries.py`, `test_worker_identity_auth.py`; create `test_transactional_audit.py` and `test_membership_lifecycle.py`.

## CONTEXT

- Plan authority: task M02 in the managed-beta plan, plus ADR-015 at `/home/nochaserz/Documents/Coding Projects/scanforge/scanforge-security-platform/docs/adr/ADR-015-beta-access-and-data-erasure.md`. The ADR set 010–017 lives only in the shared tree. Read it freely; never write there.
- Convention map: `orchestrate/managed-beta/reports/exp-api.md`. No conftest.py exists; route tests use `app.dependency_overrides` plus httpx ASGITransport. Real PostgreSQL is env-gated per test (`R04_POSTGRES_URL` pattern) against the M00 fixture at `postgresql://scanforge@localhost:5433/<db>`.
- Preserved acceptance details binding this task: JWT checks need configured issuer and audience; audit actor context stays request-local, never process-global; project audit queries return only that project's events; worker-originated mutations record the verified worker actor.
- Environment: `scripts/dev_fixtures.sh print-env` exports `DATABASE_URL` and `REDIS_URL`. Never commit credential-looking literals; never retype SHAs (use `git rev-parse HEAD`).

## ACCEPTANCE

1. Regression-first repro: a privileged org-A actor mutating an org-B finding currently fails its permission check only AFTER the write (or otherwise proves the ordering defect). Capture the repro before fixing. Add direct-service variants of the same scenario.
2. The ADR-015 matrix is implemented: verified resource scope on every sensitive mutation, active-user/active-member/worker checks, and no admin shortcut for owner-only operations. Every role and target combination in the matrix has an explicit test.
3. Audit writes for sensitive mutations join the domain transaction. Inject audit-write failure and prove zero mutations persist (both route and service level). Services compose without hidden intermediate commits.
4. Stale revision rejection: concurrent-update scenarios reject with a documented error; a bulk operation rolls back entirely when any item is unauthorized or stale.
5. Pending invitations verify before acceptance; owner transfer is atomic (exactly one owner before and after; failed transfer mutates nothing). Operator worker credentials stay outside ordinary tenant administration.
6. Concurrent requests cannot exchange audit actors or organizations (request-local context test).
7. Focused suites green; per-invariant commits (3–5 commits), each containing only its enumerated paths; SHAs reported.

## VERIFY

- `cd apps/api && R04_POSTGRES_URL=postgresql://scanforge@localhost:5433/scanforge_m02 .venv/bin/python -m pytest tests/test_authorization_regressions.py tests/test_transactional_audit.py tests/test_membership_lifecycle.py -q` (create the db first via the fixture script or createdb).
- `.venv/bin/python -m pytest tests/test_route_integration_authorization.py tests/test_internal_service_org_boundaries.py tests/test_worker_identity_auth.py -q`.
- Audit-failure injection output pasted; `git log --oneline` for the unit's commits plus `git show --stat` per commit.

## TIMEBOX

2.5 hours. FORBIDDEN: hidden commits inside service calls, process-global actor state, admin bypass of owner-only operations, production credentials, edits outside enumerated paths, staging unrelated files, more than one migration writer.

## REPORT

Status, branch, per-commit SHAs with one-line intent each, repro evidence (pre-fix), matrix coverage summary, suite outputs, deviations, follow-ups.
