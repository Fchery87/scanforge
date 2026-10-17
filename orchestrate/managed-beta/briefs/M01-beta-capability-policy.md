# M01 — Disable deferred capabilities behind one server-side beta policy

Depends on: M00 (integration branch, venvs, fixtures ready). Status: brief ready, spawn blocked until the pilot contract confirms worker write/commit mechanics.

## GOAL

Make the eight deferred capability classes (AI investigation, PR execution/publication, export generation, suppression automation, scan scheduling, grades, numeric scores, enforcement webhooks) unexecutable server-side in the initial beta, with UI visibility aligned, while manual full scans, automatic default-branch push scans, and required triage keep working.

## SCOPE

Work in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform` on branch `managed-beta/integration`.

- Create `apps/api/app/services/beta_capabilities.py` (the one explicit policy authority) plus its test `apps/api/tests/test_beta_capability_contract.py`.
- Guard the deferred routes: `apps/api/app/api/v1/routes/{exports,suppression_rules,scan_schedules,scorecard,webhooks}.py`, wired through `apps/api/app/api/v1/router.py`.
- Guard internal triggers: extend `apps/api/tests/test_internal_scheduled_scans.py` and whatever the scheduler route uses.
- Worker side: `apps/worker/app/services/ai_investigation/stage.py` refuses with the policy's unavailable contract when reached defensively.
- Web visibility: `apps/web/lib/dashboard-navigation.ts` plus affected dashboard pages, `apps/web/lib/api.ts`, extend `apps/web/lib/dashboard-navigation.test.ts`.
- Extend `apps/api/tests/test_dashboard_routes_rbac.py` for the guard's interaction with roles.

Do not touch scan lifecycle services, the lease, dispatch, or any Alembic revision. No route removals if historical reads are safe to keep; unsupported operations return a documented unavailable response with zero side effects.

## CONTEXT

- Plan authority: task M01 in `docs/plans/2026-10-16-managed-beta-implementation-plan.md` (shared tree path). Its deferral table and rules bind.
- Convention map: `orchestrate/managed-beta/reports/exp-api.md`. Router at `app/api/v1/router.py`, middleware chain SecurityHeaders → Audit → RedisRateLimit → CORS. No conftest.py exists; route tests use `app.dependency_overrides` plus httpx ASGITransport.
- Deferred capability list is closed. Anything not listed stays as-is.
- Environment: the fixture script `scripts/dev_fixtures.sh print-env` exports `DATABASE_URL` and `REDIS_URL` for collection runs; the api venv carries `psycopg[binary]` after the M00 completion commit. Confirm that commit is HEAD before starting; if it is not, stop and report.
- Never commit credential-looking literals; never retype SHAs (use `git rev-parse HEAD`).

## ACCEPTANCE

1. Regression-first: `test_beta_capability_contract.py` first fails against current code, proving at least one deferred capability executes or is exposed today (AI stage run, export generation, scheduled scan creation, or enforcement webhook dispatch). Capture the failing output before fixing.
2. After the fix: every deferred direct route returns the documented unavailable response, and no job row, queue message, mutation, or audit event with side effects results from those requests.
3. Trigger paths are covered, not only links: internal scheduled-scan creation is refused; the worker AI stage refuses when invoked; webhook enforcement dispatch is refused.
4. Manual full scan creation, automatic default-branch push scan path, and triage endpoints demonstrably still work (at least one positive test each).
5. `dashboard-navigation.test.ts` proves deferred surfaces are absent from navigation for a beta-tenant viewer, and `lib/api.ts` types the unavailable response.
6. Focused suites green: API pytest set below, plus web node/vitest for the navigation test.
7. One commit containing only the enumerated paths, descriptive message, SHA reported.

## VERIFY

- Pre-fix capture: `cd apps/api && .venv/bin/python -m pytest tests/test_beta_capability_contract.py -q` (expect failures) — paste into report.
- Post-fix: `cd apps/api && .venv/bin/python -m pytest tests/test_beta_capability_contract.py tests/test_dashboard_routes_rbac.py tests/test_internal_scheduled_scans.py -q`.
- Web: `cd apps/web && npm run test:node && npm run test:vitest -- --maxWorkers=1` (or the narrow vitest invocation for the nav test if the full run stalls; record which).
- `git show --stat HEAD` pasted into the report.

## TIMEBOX

90 minutes. FORBIDDEN: disabling manual scans, push scans, or triage; touching lifecycle meaning; Alembic revisions; edits outside the enumerated paths; staging unrelated files.

## REPORT

Status, branch, head SHA, pre-fix failure evidence, post-fix suite outputs, positive-path proof lines, deviations, follow-ups.
