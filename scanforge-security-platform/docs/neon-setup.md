# Neon Database Setup Guide

This guide walks you through connecting ScanForge to a Neon Postgres database.

## Prerequisites

- A Neon account at [console.neon.tech](https://console.neon.tech)
- Your organization **Frantz** should already be accessible
- The project source code at `scanforge-security-platform/`

## Step 1: Create a Neon Project

### Via Neon Console

1. Go to [Neon Console](https://console.neon.tech/)
2. Select your organization: **Frantz**
3. Click **Create Project**
4. Configure:
   - **Name**: `scanforge`
   - **Region**: `US East (N. Virginia)` (or your closest region)
   - **Postgres version**: 16 (recommended)
5. Click **Create Project**

### Via CLI

```bash
# First, find your organization ID
npx neonctl orgs list

# Create the project
npx neonctl projects create --name scanforge --org-id <your-org-id>
```

## Step 2: Get Connection String

### Via Console

1. In Neon Console, select your **scanforge** project
2. Go to **Connection Details** tab
3. Choose **Pooled connection** (recommended for serverless)
4. Copy the connection string — it looks like:

```
postgresql://username:password@ep-12345678.us-east-1.neon.tech/scanforge
```

### Via CLI

```bash
# Get connection string for a project
npx neonctl connection-string --project-id <project-id>

# Or for a specific branch
npx neonctl connection-string --branch main
```

## Step 3: Configure Environment Variables

In your project directory, update `.env`:

```env
# ── Application ─────────────────────────────────────────────
APP_ENV=development
APP_NAME=ScanForge
APP_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000

# ── Database (Neon Postgres) ─────────────────────────────────
# IMPORTANT: Replace with your actual connection string from Step 2
# Use asyncpg driver for async SQLAlchemy
DATABASE_URL=postgresql+asyncpg://username:password@ep-12345678.us-east-1.neon.tech/scanforge?sslmode=require

# For sync operations (if needed later)
DATABASE_URL_SYNC=postgresql://username:password@ep-12345678.us-east-1.neon.tech/scanforge?sslmode=require

# ── Auth (Neon Auth) ────────────────────────────────────────
# Optional: If using Neon Auth for authentication
NEON_AUTH_ISSUER=https://your-project-id.neon.tech
NEON_AUTH_AUDIENCE=scanforge-api
NEON_AUTH_JWKS_URL=https://your-project-id.neon.tech/.well-known/jwks.json
NEON_AUTH_CLIENT_ID=your-client-id
NEON_AUTH_CLIENT_SECRET=your-client-secret

# ── Queue (Upstash Redis) ───────────────────────────────────
# For local dev, use local Redis (see docker-compose.yml)
UPSTASH_REDIS_REST_URL=http://localhost:6379
UPSTASH_REDIS_REST_TOKEN=dev-token

# ── Storage (Cloudflare R2 or MinIO) ────────────────────────
# For local dev with MinIO:
R2_ENDPOINT=http://localhost:9000
R2_BUCKET=scanforge-artifacts
R2_ACCESS_KEY_ID=scanforge
R2_SECRET_ACCESS_KEY=scanforge_local_storage

# ── CORS ───────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000
```

> **Important**: Replace `username`, `password`, and `ep-12345678...` with your actual Neon connection string values.

## Step 4: Run Migrations

This creates all the database tables:

```bash
cd scanforge-security-platform

# Run migrations
make migrate

# Or directly:
cd apps/api && alembic upgrade head
```

### Expected Tables

After migrations complete, these tables should exist:

| Table | Description |
|-------|-------------|
| `users` | User accounts |
| `organizations` | Organizations (teams, companies) |
| `memberships` | User-organization relationships with roles |
| `projects` | Security projects |
| `repositories` | Connected code repositories |
| `scans` | Scan runs and status |
| `scanner_runs` | Individual scanner executions |
| `findings` | Security findings from scans |
| `artifacts` | Scan output files in R2 |
| `policies` | Suppression and policy rules |
| `scan_schedules` | Scheduled scan configurations |
| `exports` | Report exports |
| `audit_logs` | Audit trail |
| `notifications` | User notifications |
| `suppressions` | Finding suppressions |
| `finding_references` | Finding external references |
| `finding_events` | Finding status change history |

## Step 5: Verify Setup

```bash
# Check connection and tables
psql "YOUR_CONNECTION_STRING" -c "\dt"

# Or via neonctl:
npx neonctl execute-sql --project-id <project-id> --query "SELECT version()"
```

## Using Neon MCP Server

With the Neon MCP server configured in opencode, you can interact with your database using natural language:

### List Projects

> "List my Neon projects"

### Create a Branch

> "Create a branch called 'dev' from main for my scanforge project"

### Run a Query

> "Execute SQL on scanforge: SELECT COUNT(*) FROM users"

### Database Migrations

The MCP server provides branch-based migration tools:

1. **Prepare Migration** — Runs your migration on a temporary branch
2. **Complete Migration** — Applies it to main after you verify

Example workflow:
> "Prepare a migration to add a 'severity' column to the findings table"

(test on the branch)

> "Complete the migration"

## Troubleshooting

### Connection Refused

- Ensure `sslmode=require` is in your connection string
- Check your IP is allowed in Neon (Neon allows all IPs by default)

### Authentication Errors

- Verify username/password in connection string
- Check project is in your organization

### Migration Fails

- Ensure DATABASE_URL is correct in `.env`
- Run `make migrate-status` to check current state

## Quick Reference

| Task | Command |
|------|---------|
| Create project | Neon Console or `neonctl projects create` |
| Get connection | `neonctl connection-string` |
| List branches | `neonctl branches list` |
| Create branch | `neonctl branches create --name <name>` |
| Run migrations | `make migrate` |
| Check tables | `\dt` in psql |
| View migration status | `make migrate-status` |

## Next Steps

- [Development Setup Guide](development-setup.md) — Run the full stack locally
- [Architecture Overview](../docs/architecture/system-overview.md) — Understand the system design
