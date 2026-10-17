# M00 completion — credential-safe landing of the baseline unit

Fresh worker, consolidated scope. The prior pilot (report in `orchestrate/managed-beta/inbox/`) verified everything but could not commit: a shield blocked credential-looking literals.

## GOAL

Land M00 as shield-clean commits on `managed-beta/integration` in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform`: fixture credentials derived at runtime instead of literals, receipt finalized with true SHAs, and the api venv dependency gap closed.

## SCOPE

Files you may modify/commit: `scripts/dev_fixtures.sh`, `infra/testing/docker-compose.integration.yml`, `docs/receipts/2026-10-16-M00-baseline.md`, `scanforge-security-platform/.gitignore` (worktree-root spelling varies; the one already modified), and `apps/api/pyproject.toml` (dev extra only). Nothing else.

## CONTEXT

- Baseline truth: `git rev-parse HEAD` before your commits must read `60621705b9307553430490aa364d778f503bfde2`. Verify, never trust prose.
- Pilot facts you inherit: fixtures postgres@5433 and redis@6399 are up and healthy; api suite `202 passed, 8 skipped`; worker suite `122 passed` with `REDIS_URL=redis://:scanforge-fixture@localhost:6399/0`; web node `76 passed`; web vitest `9 passed, 1 failed` (`lib/api-contracts.spec.ts` byte-parity 5s timeout, pre-existing, do not fix); minio blocked (dl.min.io returns 410); r04 and redis-streams collection probes passed once `DATABASE_URL` was set.
- Standing orders: `/home/nochaserz/Documents/Coding Projects/scanforge/orchestrate/managed-beta/preferences.md` — especially 13 (no credential-looking literals in committed files) and 14 (rev-parse SHAs).

## ACCEPTANCE

1. `scripts/dev_fixtures.sh` contains no credential literal. Credentials are generated or env-derived at start, persisted to the gitignored `.fixtures/credentials.env`, and `scripts/dev_fixtures.sh print-env` exports `DATABASE_URL`, `REDIS_URL`, and the minio variables. A `start` on a fresh `.fixtures` regenerates them.
2. `docker-compose.integration.yml` carries no credential literal either; it reads env with fixture-only variable names.
3. `grep -rn "scanforge-fixture\|scanforge-local-storage" scripts infra docs .gitignore` returns nothing in files destined for the commit.
4. MinIO: retry the dl.min.io URL once, then query the GitHub API for the current minio/minio release asset and try it. If both fail, keep the compose file, mark minio BLOCKED in the receipt, and move on within a 10-minute cap.
5. `apps/api/pyproject.toml` dev extra gains `psycopg[binary]`; install into the api venv; the receipt records the reason (fresh venvs could not collect without it).
6. Receipt finalized: true baseline SHA via rev-parse, per-suite counts from the pilot, the vitest byte-parity failure noted as pre-existing, minio status, credential mechanism, and your commit SHAs.
7. Two commits maximum: (a) fixture tooling + receipt + gitignore, (b) pyproject dev extra. Descriptive messages, only enumerated paths, shield passes.

## VERIFY

- `git rev-parse HEAD` before committing matches the baseline.
- The grep in acceptance 3, pasted.
- `bash scripts/dev_fixtures.sh status` healthy; `bash scripts/dev_fixtures.sh print-env` yields working URLs: rerun the r04 collection probe and the worker pytest (`122 passed`) using the printed `REDIS_URL`.
- `cd apps/api && DATABASE_URL=<printed> .venv/bin/python -m pytest -q` returns `202 passed, 8 skipped` (or better) in one line pasted.
- `git show --stat HEAD~1 HEAD` pasted.

## TIMEBOX

45 minutes. FORBIDDEN: shield bypass or retry-with-same-changes, credential literals anywhere committed, apps source edits beyond the pyproject dev extra, staging outside enumerated paths, editing the shared tree.

## REPORT

Status, branch, commit SHAs, grep proof, suite lines, minio outcome, deviations, follow-ups.
