# M00 — Preserve baseline and build disposable test fixtures

## GOAL

Stand up the program baseline in the implementation worktree: capture the git receipt, provision disposable native fixtures (PostgreSQL, Redis, object storage), run the four existing suites with bounded execution, and commit an honest baseline receipt plus fixture tooling.

## SCOPE

- Work only in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta` (branch `managed-beta/integration`, already checked out).
- May create: `infra/testing/docker-compose.integration.yml`, `scripts/dev_fixtures.sh`, `scripts/verify_test_inventory.py` (only if inventory needs it), `docs/receipts/2026-10-16-M00-baseline.md`, `.gitignore` additions for `.fixtures/`.
- May create (not committed): `.fixtures/` holding the postgres cluster, redis dir, minio binary and data, venvs are per-app.
- May not edit anything under `apps/` source or tests, `Makefile`, existing docs, or the shared tree at `/home/nochaserz/Documents/Coding Projects/scanforge` (read-only; it holds the operator's untracked planning docs).

## CONTEXT

- Plan authority: `/home/nochaserz/Documents/Coding Projects/scanforge/scanforge-security-platform/docs/plans/2026-10-16-managed-beta-implementation-plan.md` (task M00). Its Baseline and execution rules bind.
- Standing orders: `/home/nochaserz/Documents/Coding Projects/scanforge/orchestrate/managed-beta/preferences.md`.
- Environment facts (verified):
  - Docker absent; sudo requires a password. Do not attempt either.
  - PostgreSQL 16 server binaries at `/usr/lib/postgresql/16/bin` (initdb, pg_ctl, createdb). The system cluster on 5432 has no role for this user. Off-limits. Build a disposable cluster: `initdb -D .fixtures/pg -U scanforge --auth=trust`, start with `pg_ctl -o "-p 5433 -k <worktree>/.fixtures"`.
  - `redis-server` exists. Start a disposable instance on port 6399 with `requirepass`, `dir .fixtures/redis`. Port 6379 runs a dev instance. Off-limits.
  - MinIO not installed. Download the single binary `https://dl.min.io/server/minio/release/linux-amd64/minio` into `.fixtures/bin/`, run on port 9002, console 9003, data `.fixtures/minio-data`, root user `scanforge` / password `scanforge-local-storage`. If the download fails, record it blocked and still ship the compose file.
  - Scanner binaries exist but are NOT needed in M00.
  - `apps/api/.venv` and `apps/worker/.venv` do not exist in the worktree. Create them: `python3 -m venv apps/api/.venv && apps/api/.venv/bin/pip install -e "apps/api[dev]"` and the same for worker. Web deps: `cd apps/web && npm install`.
  - `make test` from the worktree root runs: pytest on apps/api, pytest on apps/worker, `npm run test:node`, `npm run test:vitest`.
- The four confirmed planning docs live untracked in the shared tree. Record their file names only in the receipt. No contents.

## ACCEPTANCE

1. Receipt at `docs/receipts/2026-10-16-M00-baseline.md` records: git root, branch `managed-beta/integration`, HEAD `6062170b9307553430490aa364d778f503bfde2`, the shared tree's tracked-diff summary and untracked file names (names only), the four confirmed doc names, every command actually run, and honest suite outcomes.
2. All four suites ran separately with per-suite timeouts. Counts recorded as observed: passed, failed, errors, skips, collection problems, stalls. A stall or failure is recorded as-is. No retries to green, no code fixes.
3. `scripts/dev_fixtures.sh` supports `start`, `stop`, `status`. After `start`: `psql "postgresql://scanforge@localhost:5433/scanforge_test" -c 'select 1'` succeeds, `redis-cli -p 6399 -a <fixture-password> ping` returns PONG, `curl -fsS http://localhost:9002/minio/health/live` returns 200 (or is recorded blocked with the reason).
4. Collection proof: from `apps/api`, `R04_POSTGRES_URL=postgresql://scanforge@localhost:5433/scanforge_r04 .venv/bin/python -m pytest tests/test_r04_postgres_completion_red.py --collect-only -q` collects (create the `scanforge_r04` database first). From `apps/worker`, `REDIS_URL=redis://:scanforge-fixture@localhost:6399/0 .venv/bin/python -m pytest tests/test_redis_stream_recovery_integration.py --collect-only -q` collects.
5. `infra/testing/docker-compose.integration.yml` defines postgres, redis and minio with fixture-only credentials and an isolated network, as the portable equivalent for container-capable hosts.
6. One commit on `managed-beta/integration` containing only the enumerated paths, with a descriptive message. Receipt records the commit SHA.

## VERIFY

- `bash scripts/dev_fixtures.sh start`, then the three health probes above, then `bash scripts/dev_fixtures.sh status`.
- The two collection commands above, exact output captured into the receipt.
- `timeout 1800 make test` from the worktree root, per-suite `timeout 900` prefixes. Output summarized into the receipt, tails of failures included.
- `git show --stat HEAD` pasted into the report.

## TIMEBOX

2 hours. On expiry, stop, commit nothing untested, and report partial findings.

## FORBIDDEN

No docker, no sudo, no edits in the shared tree, no use of ports 5432/6379 system services, no source or test code changes, no production credentials anywhere, no invented SHAs or counts, no pip/npm installs outside the worktree.

## REPORT

Status (done / partial / blocked), branch, head SHA, per-suite counts table, fixture health output lines, collection evidence lines, commit SHA and stat, deviations from this brief, suggested follow-ups.
