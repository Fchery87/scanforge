# Running ScanForge Locally

This is the fast path for getting the repo running on one machine.

## Prerequisites

- Docker
- Node.js 20+
- Python 3.11+ or 3.12+
- scanner binaries if you want real scan execution instead of just app startup and tests

## 1. Create Local Environment

```bash
cp .env.example .env
```

Minimum things to review in `.env`:

- `DATABASE_URL`
- `CORS_ORIGINS`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `R2_*`
- `NEON_AUTH_*`
- `INTERNAL_API_KEY`

## 2. Install Dependencies

```bash
make install
```

This creates separate virtual environments for `apps/api` and `apps/worker` and installs `apps/web` dependencies.

## 3. Start Local Infrastructure

```bash
make db-up
```

This starts:

- Postgres on `localhost:5432`
- Redis on `localhost:6379`
- MinIO on `localhost:9000`
- MinIO console on `http://localhost:9001`

## 4. Run Migrations

```bash
make migrate
```

## 5. Start The Main Processes

Use three terminals from the project root:

```bash
make api-dev
make web-dev
make worker-dev
```

Useful URLs:

- `http://localhost:3000`
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`
- `http://localhost:9001`

## Important Queue Note

The worker queue client uses the Upstash Redis REST API, not a raw Redis TCP client. That means Docker Redis alone is not enough for end-to-end queue-backed scans unless you change the queue implementation or provide working Upstash REST credentials.

## GitHub Local Callback Configuration

For GitHub App installation and OAuth flows, use:

- setup URL: `http://localhost:3000/github/callback`
- redirect URI: `http://localhost:3000/github/callback`

Relevant env vars:

```env
GITHUB_APP_ID=123456
GITHUB_APP_SLUG=your-app-slug
GITHUB_CLIENT_ID=Iv1...
GITHUB_CLIENT_SECRET=...
GITHUB_PRIVATE_KEY=...
GITHUB_WEBHOOK_SECRET=...
GITHUB_STATE_SIGNING_SECRET=...
```

## Common Commands

```bash
make help
make install
make db-up
make db-down
make migrate
make migrate-status
make scanner-install
make scanner-check
make api-dev
make web-dev
make worker-dev
make worker-purge-queue
make lint
make test
```

## Troubleshooting

### Docker services do not start

Make sure Docker is running, then retry `make db-up`.

### Migrations fail

Check the configured `DATABASE_URL` and then run:

```bash
make migrate-status
```

### Worker cannot process real jobs

Check:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `INTERNAL_API_KEY`
- scanner binaries from `make scanner-check`

### Python environment is broken

```bash
rm -rf apps/api/.venv apps/worker/.venv
make install
```
