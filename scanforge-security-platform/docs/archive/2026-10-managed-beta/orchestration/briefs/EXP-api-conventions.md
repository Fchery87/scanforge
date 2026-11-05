# EXP-API — Convention map of apps/api for the managed-beta API track

Read-only investigation. GOAL: give the coordinator everything needed to author precise M01–M03, M06–M11, M13, M14 briefs without re-reading the codebase.

Map, in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/apps/api` (branch `managed-beta/integration`):

1. Entry and wiring: `app/main.py`, how `app/api/v1/router.py` assembles routes, middleware order (auth, audit, service auth).
2. Services inventory: one line each for files in `app/services/`, noting which own scan lifecycle, access policy, audit, GitHub, findings.
3. Models and enums: `app/db/models/` files and `app/db/enums.py`, one line each. Flag where scans, findings, artifacts, repositories store identity/provenance fields today.
4. Alembic: `alembic history` head chain and `alembic.ini` script location; name the current single head revision.
5. Contracts: both `app/contracts/queue.py` modules (api and worker), what versions/messages they define, and how duplication is kept in sync.
6. Test conventions: conftest fixtures, how PostgreSQL/Redis are provided (real, faked, env-gated), which suites the plan names exist today (test_authorization_regressions.py, test_dashboard_routes_rbac.py, test_internal_scheduled_scans.py, test_canonical_finding_candidates.py, queue-contract suites), and what a route-integration test looks like.
7. Auth shape: how JWT verification works today, what issuer/audience config exists, worker identity auth.
8. OpenAPI: `scripts/emit_openapi.py` usage and output path.

ACCEPTANCE: report written to `/home/nochaserz/Documents/Coding Projects/scanforge/orchestrate/managed-beta/reports/exp-api.md` with file pointers and one-line summaries, no large code dumps. Include the Alembic head id and the exact conftest fixture names a new test would use.

TIMEBOX: 40 minutes. FORBIDDEN: any edit, any write outside the report file. REPORT: 10-line summary plus the report path.
