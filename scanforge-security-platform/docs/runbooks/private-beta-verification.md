# Verify a private-beta release

This runbook checks the secure private-beta specification. Local checks cannot approve a release. Missing live evidence remains unverified.

## Run local checks

Install the API and worker development dependencies in their `.venv` directories with `make api-install worker-install`. These targets use each application's `constraints.txt`. Render, Docker builds, and CI use the same Python constraints. Install web dependencies with `npm ci`. Run from `scanforge-security-platform`.

```sh
make private-beta-gate-local GATE_ARGS='--output /tmp/scanforge-beta-local'
```

The gate runs API and worker lint and tests. It checks web lint, TypeScript, generated OpenAPI and web contracts, both web test suites, and a production webpack build. It also validates one migration head and audits dependencies. Python audits skip the local editable ScanForge packages and reject any reported dependency vulnerability. The web audit rejects high and critical vulnerabilities.

The gate keeps native integration tests in separate processes. The regular API test fixtures use SQLite and must not change the native PostgreSQL models. To enable integrations, supply these environment variables.

| Variable | Required value |
| --- | --- |
| `TEST_POSTGRES_URL` | An asyncpg URL for a disposable, migrated PostgreSQL test database. |
| `REDIS_URL` | A URL for an isolated Redis test service. |
| `SCANFORGE_LIVE_DOCKER` | `1` to run actual container containment checks. |
| `SCANNER_IMAGE` | A built scanner image pinned by its immutable digest. |

Migrate the disposable database before the completion tests. This command changes the database named by `TEST_POSTGRES_URL`.

```sh
cd apps/api
DATABASE_URL="$TEST_POSTGRES_URL" .venv/bin/alembic upgrade head
cd ../..
make private-beta-gate-local GATE_ARGS='--output /tmp/scanforge-beta-integrations'
```

Each command writes its output to a separate log. `report.json` records command status, log hashes, commit SHA, and whether the working tree has changes. Integration suites that skip tests fail their check. Local mode returns failure for any executed check that fails. Unconfigured integrations remain unverified and prevent release approval.

## Collect live evidence

Keep evidence outside the source tree. Create one JSON receipt per check name below. Use the commit deployed to staging. Record the operator, environment, observation time, result, and files containing the actual measurements. Sanitize credentials and matched secret values before retaining evidence.

| Receipt file | Required proof |
| --- | --- |
| `postgres-full-suite.json` | The full API suite terminates and passes against PostgreSQL. The small completion integration suite does not satisfy this requirement. |
| `migration-empty-and-upgrade.json` | Migrations pass on an empty database and an upgraded staging copy. |
| `staging-deployment.json` | Shared API and scheduler deploy from committed configuration. Dedicated workers use `infra/worker`. Readiness checks pass. |
| `upstash-recovery.json` | Production Redis REST claim, crash recovery, replay, acknowledgement, outage recovery, and dead-letter behavior pass. |
| `github-triggers-and-check.json` | Manual, scheduled, push, and PR triggers enqueue one scan. PR Checks update with exact commit context and incomplete coverage. |
| `authenticated-browser.json` | Authenticated onboarding, scan pages, scanner health, finding triage, drawer keyboard controls, and access failures pass in a real browser. |
| `canary-boundaries.json` | Canary tests cover every scan type and prohibited durable or external boundary. Record only redacted test evidence. |
| `operational-drills.json` | Backup and restore, worker replacement, credential rotation, dead-letter recovery, and organization kill switch pass. Recovery finishes within ten minutes. |
| `monitoring-alerts.json` | Alerts detect queue age, worker health, failed persistence, scanner failure, and storage failure. |
| `beta-load.json` | At least 95 percent of scans start within five minutes under the three-organization beta load. Record the sample size and timing distribution. |
| `scanner-image-offline-assets.json` | Image build succeeds with pinned tool versions and rules/database receipts. All seven adapters execute offline, preserve evidence, and reject hostile fixtures. |

A receipt has this shape. Replace every example value with observed evidence.

```json
{
  "status": "passed",
  "commit_sha": "<full deployed commit SHA>",
  "observed_at": "2026-10-01T12:00:00Z",
  "environment": "staging",
  "operator": "<operator identity>",
  "artifacts": [
    {"path": "logs/github-check.txt", "sha256": "<SHA-256 of the file>"}
  ]
}
```

Artifacts must be files inside the evidence directory. The gate verifies their hashes and requires receipts for the current commit. Receipt validation confirms attribution and file integrity. An operator must review whether each artifact proves the stated behavior. The gate cannot infer that a log proves a drill from its filename.

## Run the release gate

Commit the release candidate. Use a clean working tree. Enable PostgreSQL, Redis, and Docker integrations. Then run the release mode with the evidence directory.

```sh
make private-beta-gate GATE_ARGS='--output /tmp/scanforge-beta-release --evidence-dir /secure/evidence/scanforge-beta'
```

Release mode returns failure when any command fails, any required integration is unavailable, any receipt is missing or invalid, or the source tree has changes. Approve the release only after `release_ready` is `true` and the operator has reviewed the evidence. This command does not deploy services.

## Verify Render configuration

The Blueprint creates the shared API and a scheduler that runs each minute. Its paths use the Git root containing `scanforge-security-platform`. Contract verification generates temporary files and compares them with the committed schema and web types. It does not overwrite source files. Single-head validation is read-only and does not apply migrations.

The API applies Alembic migrations before startup. The scheduler receives only its API URL and scheduler credential. Each organization scanner host uses `infra/worker/docker-compose.beta.yml`.

Provision the documented environment groups and validate the Blueprint before syncing. Automatic deploys are disabled so release verification precedes deployment. A Render Blueprint sync can recreate a deleted managed resource. Review the resource changes before approving a sync.

Render documents the native `python` runtime, required build and start commands, and the migration command in its [Blueprint reference](https://render.com/docs/blueprint-spec). Its [monorepo guide](https://render.com/docs/monorepo-support) defines `rootDir` relative to the Git root. No live Render deployment was executed during the local implementation run.
