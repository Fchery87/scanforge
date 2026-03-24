# ScanForge Security Platform - System Overview

## Architecture

ScanForge is a **three-tier security scanning platform**:
- **Frontend**: Next.js 16 (Vercel)
- **Backend**: FastAPI async Python (Render)
- **Workers**: Background job processor (Redis queue + Python workers)
- **Supporting Services**:
  - PostgreSQL (Neon)
  - Redis queue (Upstash)
  - S3 object storage (Cloudflare R2)
  - JWT Authentication (Neon Auth)

### Request Flow
```
User Browser → Next.js Frontend → FastAPI REST API → PostgreSQL
                    ↓
              Upstash Redis (queue)
                    ↓
              Python Workers → Scanners (Trivy, Gitleaks, OSV)
                    ↓
              Cloudflare R2 (artifacts) → API → Database
```

---

## Core Data Model

```
User
  └─ OrganizationMember (role: owner/admin/security_reviewer/developer/viewer)
     └─ Organization
        └─ Project
           ├─ Repository (github/gitlab/bitbucket/manual)
           │  └─ Scan (QUEUED → RUNNING → COMPLETED)
           │     ├─ ScannerRun (Trivy/Gitleaks/OSV status)
           │     └─ FindingInstance (per-scan finding occurrence)
           └─ Finding (deduplicated, severity, category)
              ├─ FindingEvent (audit: suppressed/fixed/reopened)
              └─ FindingReference (CVEs, links)
```

### Key Tables
- `organizations` — Team/workspace containers
- `projects` — Collections of repositories within an org
- `repositories` — Git repos (GitHub, GitLab, Bitbucket, manual)
- `scans` — Individual security scan runs with status tracking
- `findings` — Deduplicated vulnerabilities (one per canonical fingerprint per repo)
- `finding_instances` — Per-scan occurrences of findings
- `organization_members` — RBAC with roles: owner, admin, security_reviewer, developer, viewer

---

## User Journey After Creating an Organization

### Step 1: Create Project
**Endpoint**: `POST /api/v1/organizations/{org_id}/projects`

User groups repositories into projects. Each project represents a collection of repos to scan together.

### Step 2: Connect Repository
**Endpoint**: `POST /api/v1/organizations/{org_id}/projects/{project_id}/repositories`

User connects a Git repository from:
- GitHub, GitLab, Bitbucket
- Manual (via clone URL)

System stores provider info, clone URL, and optional webhook integration for automated scanning.

### Step 3: Run First Scan
**Endpoint**: `POST /api/v1/organizations/{org_id}/projects/{project_id}/scans`

User triggers a manual scan. The API:
1. Creates a `Scan` record with status=QUEUED
2. Enqueues job to Redis with scan details

### Step 4: Worker Orchestrates Scan
**Process**: Background worker picks up job from Redis queue

The worker executes a pipeline:
```
Clone repo
  ↓
Run 3 scanners in parallel:
  - Trivy (vulnerabilities + misconfigurations)
  - Gitleaks (secrets detection)
  - OSV (dependency vulnerabilities)
  ↓
Normalize results to unified schema
  ↓
Deduplicate findings by canonical fingerprint
  ↓
Save findings to database
  ↓
Upload raw artifacts to Cloudflare R2
  ↓
Update Scan status → COMPLETED
```

**Scanner Adapters**:
- `TrivyAdapter` — Container/config vulns
- `GitleaksAdapter` — Hardcoded secrets
- `OsvAdapter` — Dependency vulns (OSV database)

Each returns normalized JSON findings with:
- Path in code/manifest
- Line numbers (if applicable)
- Severity (critical, high, medium, low)
- Category (vulnerability, secret, dependency_outdated, etc.)
- CVE references and advisory links

### Step 5: Findings Created & Deduplicated
The system creates:
- `Finding` — Deduplicated by `canonical_fingerprint` (hash of: path, line, package, etc.)
- `FindingInstance` — This scan's occurrence of the finding
- `FindingReference` — CVE ID, CVSS, advisory URLs
- Status = "open" by default

If the same finding appears in a future scan:
- New `FindingInstance` created
- Existing `Finding.last_seen_at` updated
- Status remains "open" (unless user suppressed/fixed it)

### Step 6: User Reviews Findings
**Endpoint**: `GET /api/v1/organizations/{org_id}/projects/{project_id}/findings`

Frontend lists findings with filters:
- Severity (critical, high, medium, low)
- Category (vulnerability, secret, dependency_outdated, etc.)
- Status (open, suppressed, fixed)
- Scanner (Trivy, Gitleaks, OSV)
- Repository

User can:
- **Suppress** — Hide finding (creates suppression rule, stores reason)
- **Resolve** — Mark as fixed (stores fixed version, marks status="fixed")
- **Reopen** — Revert from resolved/suppressed (status="open")

All actions logged to `FindingEvent` for audit trail.

### Step 7: Schedule Recurring Scans (Optional)
**Endpoint**: `POST /api/v1/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/scan-schedules`

User creates recurring scan schedule:
- Daily — Runs at 2:00 AM
- Weekly — Runs every Sunday at 2:00 AM

Auto-triggers scans at intervals. Findings re-scanned and deduplicated automatically.

---

## Scan Lifecycle

```
QUEUED → RUNNING → COMPLETED
              ↘ FAILED → (retry up to 3x) → DLQ (Dead Letter Queue)
              ↘ CANCELED
```

**Status Tracking**:
- `Scan.status` — Overall scan progress
- `ScannerRun.status` — Per-scanner status (one for Trivy, one for Gitleaks, one for OSV)
- `Finding.status` — open | suppressed | fixed

**Retry Logic**:
- If scan fails: exponential backoff, max 3 retries
- If retries exhausted: move to dead letter queue (DLQ) for manual investigation

---

## API Endpoint Structure

### Organizations
```
POST   /api/v1/organizations                    # Create org
GET    /api/v1/organizations                    # List user's orgs (paginated)
GET    /api/v1/organizations/{org_id}           # Get org with members
PATCH  /api/v1/organizations/{org_id}           # Update org
DELETE /api/v1/organizations/{org_id}           # Delete org (owner only)
```

### Projects
```
POST   /api/v1/organizations/{org_id}/projects/{project_id}  # Create project
GET    /api/v1/organizations/{org_id}/projects                # List projects
GET    /api/v1/organizations/{org_id}/projects/{project_id}  # Get project with stats
PATCH  /api/v1/organizations/{org_id}/projects/{project_id}  # Update project
DELETE /api/v1/organizations/{org_id}/projects/{project_id}  # Soft delete (is_active=false)
```

### Repositories
```
POST   /api/v1/organizations/{org_id}/projects/{project_id}/repositories
GET    /api/v1/organizations/{org_id}/projects/{project_id}/repositories
GET    /api/v1/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}
PATCH  /api/v1/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}
DELETE /api/v1/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}
```

### Scans
```
POST   /api/v1/organizations/{org_id}/projects/{project_id}/scans           # Create scan
GET    /api/v1/organizations/{org_id}/projects/{project_id}/scans           # List scans
GET    /api/v1/organizations/{org_id}/projects/{project_id}/scans/{scan_id} # Get scan details
POST   /api/v1/organizations/{org_id}/projects/{project_id}/scans/{scan_id}/cancel
```

### Findings
```
GET    /api/v1/organizations/{org_id}/projects/{project_id}/findings        # List with filters
GET    /api/v1/organizations/{org_id}/projects/{project_id}/findings/{finding_id}
POST   /api/v1/organizations/{org_id}/projects/{project_id}/findings/{finding_id}/suppress
POST   /api/v1/organizations/{org_id}/projects/{project_id}/findings/{finding_id}/resolve
POST   /api/v1/organizations/{org_id}/projects/{project_id}/findings/{finding_id}/reopen
```

---

## Frontend User Journey

### Key Pages

1. **Onboarding** (`/onboarding`)
   - Checklist: create_org → create_project → connect_repo → run_first_scan → review_findings → setup_schedule
   - Tracks completion percentage

2. **Organizations Dashboard** (`/dashboard`)
   - Lists user's organizations
   - Security grade for each org (A+ to F based on: 100 - critical×25 - open×3)
   - Create new organization button

3. **Organization Dashboard** (`/dashboard/{org_id}`)
   - Shows all projects in organization
   - Project cards with: repo count, open findings count, scan count

4. **Projects** (`/dashboard/{org_id}/projects`)
   - Detailed project view with stats
   - Repository list, scan history

5. **Repositories** (`/dashboard/{org_id}/projects/{project_id}/repositories`)
   - List connected repos
   - Connect new repo, disconnect existing ones
   - Scan schedule management

6. **Scans** (`/dashboard/{org_id}/projects/{project_id}/scans`)
   - List scans with status filters
   - Trigger new manual scan
   - View scan history and results

7. **Scan Detail** (`/dashboard/{org_id}/projects/{project_id}/scans/{scan_id}`)
   - Scanner runs (Trivy, Gitleaks, OSV)
   - Status, duration, artifact links
   - Summary statistics

8. **Findings** (`/dashboard/{org_id}/projects/{project_id}/findings`)
   - List findings with advanced filters
   - Bulk suppress/resolve operations
   - Finding detail drawer with instances, references, events

9. **Suppression Rules** — Manage finding suppression policies

10. **Audit Logs** — Organization activity history

11. **Scorecard** — Security posture scoring dashboard

12. **Settings** — Organization settings and preferences

---

## Service Layer

**Location**: `/apps/api/app/services/`

Core business logic services:
- `organizations.py` — Create org, list for user, manage membership
- `projects.py` — CRUD projects, get stats
- `repositories.py` — Connect repo, manage integrations
- `scans.py` — Create scan, list, update status, manage scanner runs
- `findings.py` — Upsert findings, suppress, resolve, reopen, get stats
- `audit_logs.py` — Log all actions
- `exports.py` — Generate CSV/JSON exports
- `memberships.py` — Add/remove team members
- `notifications.py` — Send alerts to users

**Key Patterns**:
- All services accept `AsyncSession` from FastAPI dependency injection
- Access control via `user_id` passed from authenticated requests
- Services return model instances or None
- Error handling via HTTPException in route handlers

---

## Authentication & Authorization

- **Provider**: Neon Auth (JWT tokens)
- **Middleware**: `get_current_user` dependency extracts JWT claims
- **Dev Mode**: Auto-bypasses auth if no token (creates mock user automatically)

### RBAC (Role-Based Access Control)

Per-organization roles:
- **owner** — Full control, delete organization
- **admin** — Manage projects, repos, members, suppression rules
- **security_reviewer** — View findings, manage suppressions, view audit logs
- **developer** — View findings in their repos, limited suppression access
- **viewer** — Read-only access to findings

Roles stored in `OrganizationMember.role` enum.

---

## Key Features

✅ **Multi-scanner support** — Trivy + Gitleaks + OSV run in parallel
✅ **Deduplication** — Same vulnerability doesn't create duplicate records
✅ **Async job processing** — Workers handle scans independently via Redis
✅ **Finding lifecycle** — Open → Suppressed/Fixed → Reopen with full audit
✅ **RBAC** — Team members with granular organization roles
✅ **Audit logging** — All actions tracked for compliance
✅ **Security scoring** — Grade = 100 - (critical×25 + open×3)
✅ **Exports** — CSV/JSON findings export
✅ **GitHub App webhooks** — Automatic scans on push/PR
✅ **Scheduled scans** — Daily/weekly recurring security scans

---

## Example: Complete User Journey

1. **User signs up** → Created in `users` table
2. **Creates organization** → `Organization` + `OrganizationMember` (owner)
3. **Creates project** → `Project` in organization
4. **Connects GitHub repo** → `Repository` + `RepositoryIntegration` (webhook enabled)
5. **Triggers first scan** → `Scan` created (QUEUED)
6. **Worker processes**:
   - Dequeues from Redis
   - Clones repo
   - Runs Trivy, Gitleaks, OSV in parallel
   - Normalizes results
   - Creates/updates `Finding` records (deduplicated)
   - Creates `FindingInstance` for this scan
   - Updates `Scan` → COMPLETED
7. **User reviews findings**:
   - Lists 5 critical vulns, 12 secrets, 8 outdated deps
   - Suppresses non-critical secrets (creates suppression event)
   - Marks 2 vulns as resolved with fixed version
8. **Future scans**:
   - Re-scans same repo
   - Suppressed findings excluded from results
   - Resolved vulns don't reappear (unless code reverted)
   - New findings added
9. **Audit trail** — All suppressions/resolutions logged to `FindingEvent`

---

## File Structure Summary

### Backend
```
/apps/api/
├── app/
│   ├── db/
│   │   ├── models/           # SQLAlchemy models
│   │   ├── enums.py          # MemberRole, RepoProvider, ScanStatus, etc.
│   │   └── session.py        # Database connection
│   ├── services/             # Business logic (8 service modules)
│   ├── api/v1/routes/        # FastAPI route handlers
│   ├── schemas/              # Pydantic request/response models
│   ├── middleware/
│   │   ├── auth.py           # JWT auth, RBAC
│   │   ├── audit.py          # Audit logging middleware
│   │   └── security_headers.py
│   └── main.py               # FastAPI app setup
└── alembic/                  # Database migrations
```

### Worker
```
/apps/worker/
├── app/
│   ├── worker/
│   │   ├── main.py           # Worker event loop
│   │   └── maintenance.py    # Housekeeping tasks
│   ├── services/
│   │   └── scan_orchestrator.py  # Scan pipeline orchestration
│   ├── scanners/             # Scanner adapters
│   │   ├── base.py
│   │   ├── trivy.py
│   │   ├── gitleaks.py
│   │   └── osv.py
│   ├── normalizers/          # Result normalization
│   │   ├── trivy.py
│   │   ├── gitleaks.py
│   │   └── osv.py
│   └── clients/
│       ├── queue.py          # Redis queue client
│       └── r2.py             # S3-compatible storage client
```

### Frontend
```
/apps/web/
├── app/
│   └── (dashboard)/
│       ├── onboarding/       # Onboarding checklist
│       ├── dashboard/        # Org/project/scan views
│       │   ├── {org_id}/
│       │   │   ├── page.tsx  # Org dashboard
│       │   │   ├── projects/
│       │   │   ├── repositories/
│       │   │   ├── scans/
│       │   │   ├── findings/
│       │   │   └── settings/
│       │   └── page.tsx      # Org list
└── lib/
    └── api.ts                # API client wrapper
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, TailwindCSS |
| Backend API | FastAPI, SQLAlchemy 2.0, Pydantic V2, asyncio |
| Database | PostgreSQL (Neon) |
| Job Queue | Redis (Upstash) |
| Object Storage | Cloudflare R2 (S3-compatible) |
| Authentication | Neon Auth (JWT) |
| Scanners | Trivy, Gitleaks, OSV |
| Deployment | Vercel (frontend), Render (API + worker) |

---

## Development Guidance

### Running Locally

```bash
# Start backend API
make api-dev

# Start worker
make worker-dev

# Start frontend
cd apps/web && npm run dev
```

### Key Environment Variables

**Backend** (`.env`):
- `DATABASE_URL` — PostgreSQL connection
- `REDIS_URL` — Redis queue connection
- `R2_*` — Cloudflare R2 credentials
- `NEON_AUTH_ISSUER` — JWT issuer

**Worker** (`.env`):
- Same as backend + worker-specific config

**Frontend** (`.env.local`):
- `NEXT_PUBLIC_API_URL` — Backend API URL

### Database Migrations

```bash
cd apps/api
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## Troubleshooting

### Organization Creation Fails
Check:
- JWT token validity in dev mode
- `users` table has user record
- `organizations` table constraints

### Scan Stuck in QUEUED
Check:
- Redis connection (Upstash)
- Worker process running
- Database constraints on `scans` table

### Findings Not Appearing
Check:
- Scanner output normalization (logs in worker)
- Canonical fingerprint collision detection
- `findings` and `finding_instances` inserts

### Database Enum Error
The enums in `app/db/enums.py` use lowercase values (e.g., `MemberRole.OWNER = "owner"`).
SQLAlchemy models must specify `values_callable=lambda e: [m.value for m in e]` when creating Enum columns.
See `/apps/api/app/db/models/*.py` for examples.

---

## Next Steps

For new features or modifications:
1. Check existing models in `/apps/api/app/db/models/`
2. Add service logic in `/apps/api/app/services/`
3. Create/update API routes in `/apps/api/app/api/v1/routes/`
4. Update frontend in `/apps/web/app/`
5. Run migrations if schema changes
6. Test with `make api-dev`, `make worker-dev`, and frontend dev server
