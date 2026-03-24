# ScanForge — Repository Security Platform

ScanForge is a centralized security scanning platform designed to continuously monitor code repositories for vulnerabilities, secrets, and compliance issues. It provides a unified dashboard for security teams and developers to track, manage, and remediate security findings across their entire codebase.

## The Problem

Modern development teams rely on multiple security scanning tools, each producing different output formats and requiring separate workflows. This fragmentation leads to:
- Missed vulnerabilities due to scattered findings
- Lack of centralized visibility into security posture
- Inconsistent remediation tracking
- Manual effort correlating results across tools

## Use Cases

### For Security Teams
- **Continuous Monitoring**: Automatically scan repositories on a schedule to detect new vulnerabilities as code changes
- **Centralized Dashboard**: View all security findings across projects in one place with severity-based prioritization
- **Compliance Reporting**: Generate reports for audits and track remediation progress over time
- **Audit Trail**: Maintain a complete history of scan activities and finding status changes

### For Development Teams
- **Shift-Left Security**: Catch vulnerabilities early in the development lifecycle before they reach production
- **Actionable Findings**: Get normalized, consistent security findings regardless of which scanner detected them
- **Suppression Workflow**: Mark false positives or accepted risks with proper justification and approval
- **Repository Onboarding**: Easily connect repositories and configure scanning without deep security expertise

### For Engineering Leadership
- **Security Scorecards**: Track security posture across projects with quantitative metrics
- **Trend Analysis**: Monitor security improvement or regression over time
- **Resource Allocation**: Identify which repositories need the most security attention
- **Governance**: Enforce security policies and standards across the organization

## How It Works

1. **Connect Repositories**: Onboard your code repositories through the web interface
2. **Configure Scans**: Set up manual or scheduled scanning using industry-standard tools
3. **Scan Execution**: The platform orchestrates multiple scanners against your code
4. **Finding Normalization**: Results are standardized into a consistent schema
5. **Review & Remediate**: Use the dashboard to prioritize and track fixes
6. **Export & Report**: Generate reports for stakeholders and compliance requirements

## Security Scanners

ScanForge integrates with leading open-source security tools:

- **Trivy** — Vulnerability and misconfiguration scanner for containers, filesystems, and code repositories
- **Gitleaks** — Detects hardcoded secrets, API keys, and credentials in Git repositories
- **OSV-Scanner** — Checks dependencies against the Open Source Vulnerabilities database
- **Syft** — Generates Software Bill of Materials (SBOM) from container images and filesystems
- **Grype** — Matches vulnerabilities against SBOM data for comprehensive dependency analysis

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 16 | Modern React-based web interface |
| API | FastAPI | High-performance Python REST API |
| Workers | Python | Background scan processing |
| Database | Neon Postgres | Serverless PostgreSQL with branching |
| Cache/Queue | Upstash Redis | Scan job queuing and caching |
| Object Storage | Cloudflare R2 | Raw scan output and artifact storage |
| Auth | Neon Auth (JWT) | Secure authentication and authorization |
| Hosting (Frontend) | Vercel | Edge-optimized frontend deployment |
| Hosting (Backend) | Render | Scalable API and worker hosting |

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.12+
- Docker (for local infrastructure)

### 1. Clone and Install

```bash
git clone <repository-url>
cd scanforge-security-platform
make install
```

### 2. Start Local Infrastructure

```bash
make db-up
```

This starts PostgreSQL, Redis, and MinIO (S3-compatible storage) via Docker.

### 3. Install Scanner Binaries

```bash
make scanner-install
```

### 4. Run Database Migrations

```bash
make migrate
```

### 5. Start Development Services

```bash
make dev
```

Access the application:
- **Web Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Worker**: Runs in foreground processing scan jobs

## Development

### API (`apps/api/`)
```bash
make api-dev        # Dev server with hot reload
make migrate        # Run pending migrations
make migrate-generate name=your_migration  # Create new migration
```

### Web (`apps/web/`)
```bash
make web-dev        # Next.js dev server
make web-build      # Production build
make web-lint       # Run linting
```

### Worker (`apps/worker/`)
```bash
make worker-dev     # Development worker
make worker-prod    # Production worker
```

## Deployment

### Vercel (Frontend)
```bash
cd apps/web && vercel
```

Configure environment variable:
- `NEXT_PUBLIC_API_BASE_URL` — API endpoint URL

### Render (API + Worker)
Deploy via `render.yaml` configuration.

Required environment groups:
- `shared-app`: DATABASE_URL, APP_ENV, APP_URL, CORS_ORIGINS
- `auth`: NEON_AUTH_* variables
- `storage`: R2_* variables
- `queue`: UPSTASH_* variables

## API Documentation

Interactive API documentation is available when the API is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Environment Variables

Copy `.env.example` to `.env` and configure your values:

```bash
cp .env.example .env
```

Key variables:
- `DATABASE_URL` — PostgreSQL connection string
- `NEON_AUTH_*` — Authentication configuration
- `UPSTASH_*` — Redis connection for queue/cache
- `R2_*` — Cloudflare R2 storage credentials

## Project Structure

```
scanforge-security-platform/
├── apps/
│   ├── api/              # FastAPI backend with REST endpoints
│   ├── web/              # Next.js frontend dashboard
│   └── worker/           # Python background worker for scan processing
├── infra/                # Infrastructure configuration files
├── packages/
│   └── contracts/        # Shared API contracts and types
├── spec/                 # Product specifications and documentation
│   ├── PRD.md           # Product requirements
│   ├── DB_SCHEMA.md     # Database schema design
│   ├── API_OVERVIEW.md  # API endpoint specifications
│   └── ...              # Additional specs
├── docker-compose.yml    # Local development infrastructure
├── Makefile             # Development automation commands
├── render.yaml          # Backend deployment configuration
└── .env.example         # Environment variable template
```

## Roadmap

- **Phase 1**: Core scanning with Trivy, Gitleaks, OSV-Scanner
- **Phase 2**: Scheduled scans, suppression workflows, notifications
- **Phase 3**: SBOM generation (Syft/Grype), infrastructure scanning (Checkov)
- **Phase 4**: AI-assisted remediation, PR integration, advanced governance

## Contributing

1. Create a feature branch from `main`
2. Make your changes following existing code conventions
3. Run `make lint` to check code quality
4. Test your changes locally
5. Submit a pull request with a clear description

## License

[Specify your license here]