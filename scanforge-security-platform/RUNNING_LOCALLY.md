# Running ScanForge Locally

This is the canonical development setup guide. Run commands from `scanforge-security-platform/`, inside the parent Git repository. It describes current development behavior. The accepted dedicated-host beta topology in [ADR-011](docs/adr/ADR-011-beta-executor-and-github-ingress.md) still requires implementation and release evidence; see the [implementation plan](docs/plans/2026-10-16-managed-beta-implementation-plan.md).

## Prerequisites and installation

Use Python 3.12+, Node.js 20+, Git, and Docker with Compose for local infrastructure. Real local scans also need scanner executables. Installation needs network access.

```bash
cp .env.example .env
make install
```

Copy the template only for a new checkout; preserve an existing `.env`. Installation creates separate API/worker virtual environments and web dependencies. Do not install into system Python or use `--break-system-packages`.

## Database and storage

The API and worker discover the nearest `.env`. Web Make targets source the root `.env`, so values must also be valid shell assignments. Keep secrets in ignored configuration or a secret manager; never commit or paste them into logs. Existing process environment values take precedence.

For Compose development services:

```dotenv
APP_ENV=development
APP_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
DATABASE_URL=postgresql+asyncpg://scanforge:scanforge_local@localhost:5432/scanforge
R2_ENDPOINT=http://localhost:9000
R2_BUCKET=scanforge-artifacts
R2_ACCESS_KEY_ID=scanforge
R2_SECRET_ACCESS_KEY=scanforge_local_storage
```

These are public development credentials, unsuitable for exposed services.

```bash
make db-up
docker compose ps
```

Compose starts PostgreSQL 16 on 5432, raw Redis on 6379, and MinIO on 9000 with console on 9001. At `http://localhost:9001`, sign in with the Compose MinIO credentials above and create the private `scanforge-artifacts` bucket. Bucket creation is not automatic. LocalStack is optional and is not started by this target.

Alternatively, use a dedicated Neon development database/branch. Set `DATABASE_URL` to its `postgresql+asyncpg://` URL without `sslmode` or `channel_binding` query parameters. The API enables TLS for non-loopback hosts; Alembic converts the URL to its synchronous driver. Do not use production data for development.

```bash
make migrate
make migrate-status
```

Generate changes using `make migrate-generate name=description`, review the migration, then apply it. Rollback/reset commands are destructive, not routine troubleshooting.

The current revision in `0015_finding_instance_ai_annotation.py` is `0015_finding_ai_annotation`, despite its older filename. If a database records an obsolete revision, inspect `alembic_version`, actual schema, and migration history before recovery. Do not blindly stamp: stamping changes metadata without applying schema changes.

## Authentication

Use the implemented Neon Auth integration:

- Web: configure `NEON_AUTH_BASE_URL` (or `NEXT_PUBLIC_NEON_AUTH_BASE_URL`) and a strong `NEON_AUTH_COOKIE_SECRET`.
- API: configure the actual token provider's `NEON_AUTH_ISSUER`, `NEON_AUTH_JWKS_URL`, and `NEON_AUTH_AUDIENCE`.
- Provider: authorize the development web origin and callback URLs for the configured integration.

The web proxies auth through `/api/auth/*` and retrieves a signed JWT for API requests. Verify authenticated dashboard requests; browser sign-in alone does not prove API token compatibility. Do not bypass middleware or substitute hardcoded tokens. Other OIDC providers are not established drop-in integrations here.

## Queue and worker identity

End-to-end scanning needs a real Upstash-compatible REST endpoint/token in `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`. Compose Redis speaks TCP Redis; `http://localhost:6379` is not a REST endpoint. Raw Redis is useful for explicitly supported native-Redis tests.

After migrations and creation of a development organization, configure a strong API-only `WORKER_CREDENTIAL_PEPPER`. Provision an organization-scoped identity through `apps/api/scripts/manage_worker_identity.py`. Its source-defined syntax is:

```text
create ORGANIZATION_UUID NAME [--capability CAPABILITY ...]
inspect WORKER_UUID
disable WORKER_UUID
rotate WORKER_UUID
```

From `apps/api`, invoke `PYTHONPATH=. .venv/bin/python scripts/manage_worker_identity.py COMMAND ...`. Create and rotate display a credential once: run privately, store it directly in protected configuration, and do not capture/share output. Provisioning changes state; use `--help` for syntax and `inspect` for non-secret metadata.

Configure the worker's `WORKER_CREDENTIAL`, `WORKER_ORGANIZATION_ID`, unique `WORKER_CONSUMER_NAME`, `WORKER_CONCURRENCY=1`, and `API_BASE_URL=http://localhost:8000`. `INTERNAL_API_KEY` is not a worker credential. Scheduled administration uses separate `SCHEDULER_API_KEY` credentials and is unnecessary for manual development. API-only secrets must not be copied to dedicated workers; shared local configuration is not a production distribution model.

## GitHub development integration

For the current callback flow, configure the App setup URL and OAuth redirect URI as `http://localhost:3000/github/callback`. Set `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, and a separate strong `GITHUB_STATE_SIGNING_SECRET`.

Callbacks use browser navigation; webhook delivery needs a GitHub-reachable HTTPS development endpoint. Inspect current API webhook routes before configuring delivery. Centralized ingress, installation ownership verification, and complete automatic triggering/publication remain implementation requirements, not capabilities this guide claims are complete.

## Local scanners

`APP_ENV=development` selects local execution. Install maintained scanner distributions with versions compatible with the adapters, on worker `PATH` or through:

```text
TRIVY_BINARY GITLEAKS_BINARY OSV_SCANNER_BINARY SEMGREP_BINARY
SYFT_BINARY CHECKOV_BINARY GRYPE_BINARY
```

```bash
make scanner-check
semgrep --version
```

`make scanner-install` prints suggestions; it does not install tools. Its suggestions are not a pinned, verified distribution. `scanner-check` omits Semgrep and only checks versions. Use upstream installation instructions for the actual OS/architecture; verify downloaded release integrity. Distribution branding may differ from its underlying Ubuntu codename, so do not copy a workstation-specific repository entry blindly.

Keep `AI_ENABLED=false`. Known scanner/artifact gaps are tracked in the implementation plan. A version command or empty scan does not establish coverage. `private-beta` selects a different container path; changing the environment name does not implement the accepted host topology or fix its known gaps.

## Start and verify

Run each service in a separate terminal:

```bash
make api-dev
make web-dev
make worker-dev
```

Web runs on `http://localhost:3000`; API `/docs` and `/redoc` are on port 8000. Check `/api/v1/health` and `/api/v1/ready`, then authenticated organization access. Start workers only after identity/queue configuration.

```bash
make lint
make test
make web-build
```

These development checks are not the full release evidence required by [ADR-017](docs/adr/ADR-017-authoritative-evidence-and-optional-ai.md).

## Disposable PostgreSQL tests

`apps/api/tests/test_r04_postgres_completion_red.py` uses `R04_POSTGRES_URL`; PostgreSQL cases skip when absent. Its fixtures delete application table contents. Use a separate disposable database only, never shared development or production data.

An already available `pgserver` fixture may supply a cluster in an isolated temporary directory. It is optional, not a required project dependency; this guide does not install/start it. Keep returned connection details private. Migrate the disposable database through `DATABASE_URL`, then configure its asyncpg URL in `R04_POSTGRES_URL` before running:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m pytest apps/api/tests/test_r04_postgres_completion_red.py
```

Verify cluster identity first. Stop it through the fixture/server lifecycle before removing its disposable directory. Do not assume it contains no credentials or delete a running cluster's data directory.

## Troubleshooting

- Infrastructure: inspect `docker compose ps` and `docker compose logs postgres minio redis`; check service health and ports. `make db-down` stops services without deleting named volumes.
- Database: verify the selected database without printing credentials and run `make migrate-status`. Check driver URL/TLS. Do not stamp/reset to conceal schema mismatch.
- API 401: check issuer, audience, JWKS, and signed API-token retrieval. Never share tokens in diagnostics.
- Worker inactivity: verify organization, consumer, enabled credential, API connection, and REST queue configuration. Empty and unavailable queues differ. Queue purge is destructive, not a connectivity test.
- Scanners: check executable paths/versions from the worker environment, then a known-positive fixture. Versions alone do not prove analysis.
- Python imports: reinstall the affected editable environment with `make api-install` or `make worker-install`; recreating a virtual environment is a deliberate recovery operation.
- Web builds: inspect errors and required auth/API configuration first. Clear `.next` only after stopping the process; preserve lockfiles and environments unless reinstallation is intended.

See [repository authority](docs/adr/ADR-012-repository-authority-and-ordered-evidence.md), [durable evidence](docs/adr/ADR-013-durable-delivery-and-terminal-evidence.md), and [system overview](docs/SYSTEM_OVERVIEW.md) for architecture and operating semantics.
