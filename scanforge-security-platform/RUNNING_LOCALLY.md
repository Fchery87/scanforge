# Running ScanForge Locally

## Prerequisites

- **Docker** — for local Postgres, Redis, MinIO
- **Node.js / npm** — for the web frontend
- **Python 3.12+** — for API and worker

## Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Fill in your .env values (database, auth, GitHub, etc.)

# 3. Install all dependencies (web + api + worker)
make install
```

## Start Local Infrastructure

```bash
make db-up
```

This starts:
- **Postgres** on `localhost:5432` (user: `scanforge`, pass: `scanforge_local`)
- **Redis** on `localhost:6379`
- **MinIO** on `localhost:9000` (user: `scanforge`, pass: `scanforge_local_storage`)

## Run Migrations

```bash
make migrate
```

## Start Services

Open **3 separate terminals** from the project root:

```bash
# Terminal 1 — API (http://localhost:8000)
make api-dev

# Terminal 2 — Web (http://localhost:3000)
make web-dev

# Terminal 3 — Worker (scan processor)
make worker-dev
```

## Useful URLs

| URL | Description |
|-----|-------------|
| `http://localhost:3000` | Web app |
| `http://localhost:8000/docs` | API Swagger UI |
| `http://localhost:8000/redoc` | API ReDoc |

## All Commands

### Setup

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies (web + api + worker) |
| `make scanner-install` | Install scanner binaries (trivy, gitleaks, etc.) |
| `make db-up` | Start local database with Docker |
| `make db-down` | Stop local database |

### Development

| Command | Description |
|---------|-------------|
| `make api-dev` | FastAPI dev server on `:8000` |
| `make web-dev` | Next.js dev server on `:3000` |
| `make worker-dev` | Worker process (foreground) |

### Migrations

| Command | Description |
|---------|-------------|
| `make migrate` | Run pending migrations |
| `make migrate-generate name=X` | Generate a new migration |
| `make migrate-status` | Show migration status |
| `make migrate-rollback` | Roll back one migration |
| `make migrate-reset` | Roll back all migrations (DEV ONLY) |

### Build & Lint

| Command | Description |
|---------|-------------|
| `make web-build` | Build Next.js app |
| `make lint` | Lint all apps |
| `make test` | Run tests |

## GitHub App Configuration

To enable the GitHub integration, configure your GitHub App at `https://github.com/settings/apps/{your-app}`:

| Setting | Value |
|---------|-------|
| **Setup URL** | `http://localhost:3000/github/callback` |
| **Redirect on update** | ✅ Checked |

The **Setup URL** is the most critical setting — GitHub redirects here after the user installs the app. It must point to `/github/callback`. The `installation_id` is passed as a query parameter.

Required `.env` variables:

```
GITHUB_APP_ID=123456              # Numeric App ID
GITHUB_APP_SLUG=your-app-slug     # App slug from URL
GITHUB_CLIENT_ID=Iv1...           # OAuth Client ID (starts with Iv1)
GITHUB_CLIENT_SECRET=...          # Generate in App settings
GITHUB_PRIVATE_KEY=...            # Base64-encoded .pem file
GITHUB_WEBHOOK_SECRET=...         # Your webhook secret
```

### How the flow works

1. User clicks "Connect GitHub" in Settings → Integrations
2. Frontend stores `org_id` in localStorage, redirects to `https://github.com/apps/{SLUG}/installations/new`
3. User installs the GitHub App on their account/org
4. GitHub redirects to the **Setup URL** (`/github/callback`) with `installation_id`
5. Frontend reads `installation_id` from URL + `org_id` from localStorage
6. Frontend calls `POST /organizations/{org_id}/github/connect` to save the integration
7. User is redirected to onboarding with `github_connected=true`

## Troubleshooting

**`make db-up` fails** — Make sure Docker is running.

**Port already in use** — Check if another process is using ports 3000, 5432, 6379, 8000, or 9000:
```bash
lsof -i :PORT_NUMBER
```

**Migration errors** — Ensure your `.env` `DATABASE_URL` is correct and the database is running:
```bash
make migrate-status
```

**Python venv issues** — Recreate the virtual environment:
```bash
rm -rf apps/api/.venv apps/worker/.venv
make install
```
