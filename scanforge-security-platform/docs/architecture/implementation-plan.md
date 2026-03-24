# Repository Security Platform — Architecture Implementation Plan

**Status:** Locked foundation  
**Purpose:** Internal web application for monitoring business-created code repositories with automated security and quality analysis  
**Primary surfaces:** Web application first, MCP deferred until after core platform stabilization  
**Document type:** Architectural implementation plan  
**Last updated:** 2026-03-21

---

## 1. Executive summary

This platform is a **web-first repository security and quality monitoring system** designed to help monitor private business projects. The system connects repositories, runs automated scans, stores normalized findings, surfaces remediation guidance, tracks trends over time, and supports scheduled monitoring.

The product is intentionally designed as an **orchestration and intelligence layer** rather than a custom scanner engine. Proven open-source tools perform the scanning work, while this platform owns:

- repository onboarding
- scan orchestration
- normalized finding storage
- dashboards and reporting
- prioritization and remediation workflows
- audit history
- scheduling and notifications
- organization/project/repository management

The platform is being designed for internal use first, with flexibility to adapt later if commercial distribution becomes relevant.

---

## 2. Locked product decisions

### 2.1 Product direction

- **Primary product surface:** web application
- **Secondary future surface:** MCP server
- **Reasoning:** the core value is in the human workflow first — dashboards, findings, scans, team/project management, exports, and remediation prioritization

### 2.2 Scanner philosophy

Do not build custom scanners first. Build a platform that:

- runs established tools
- stores raw artifacts
- normalizes results into a canonical finding model
- deduplicates repeated issues over time
- enriches findings for dashboards and prioritization

### 2.3 Hosting and infrastructure direction

#### Locked application stack
- **Frontend:** Next.js
- **Backend API:** FastAPI
- **Workers:** Python background workers
- **Database:** Neon Postgres
- **ORM:** SQLAlchemy
- **Auth:** Neon Auth *(for now)*

#### Locked infrastructure stack
- **Frontend hosting:** Vercel
- **Backend API + workers + cron:** Render
- **Object storage:** Cloudflare R2
- **Queue / cache:** Upstash Redis

---

## 3. Product goals

### 3.1 Primary goals

The system should enable users to:

- connect code repositories
- scan codebases and dependencies for security and quality issues
- detect secrets and sensitive information exposure
- identify outdated packages and vulnerable dependencies
- store scan history and finding trends over time
- prioritize issues by severity and importance
- run scans manually and on schedules
- export reports and retain scan artifacts
- maintain auditability of actions and findings

### 3.2 MVP goals

The MVP should support:

- organization and project setup
- repository connection
- manual scan triggering
- scheduled scanning
- scan history
- normalized findings pages
- severity/category filtering
- artifact storage
- exports
- basic audit logs
- basic RBAC
- notifications for important scan events

### 3.3 Deferred goals

The following are intentionally deferred until after MVP:

- MCP server
- PR annotations
- advanced policy engine
- container registry integrations
- IaC scanning
- license compliance workflows
- AI remediation assistant
- SSO/SAML
- Jira/Linear integrations

---

## 4. Recommended scanner stack for internal use

This stack was selected to minimize licensing friction and vendor subscription dependency for internal usage.

### 4.1 Core recommended scanners

- **Trivy**
  - vulnerabilities
  - misconfigurations
  - repository scanning
  - container support later
  - secrets support

- **Gitleaks**
  - committed secrets detection
  - historical secret exposure

- **OSV-Scanner / OSV API**
  - dependency vulnerability intelligence
  - package advisory mapping
  - version risk support

- **Syft**
  - SBOM generation

- **Grype**
  - vulnerability scanning from SBOM/images/filesystems

### 4.2 Optional early add-ons

- **Checkov**
  - add when IaC/config scanning becomes necessary

- **Semgrep Community Edition**
  - optional after the core pipeline is stable
  - useful for faster static analysis coverage

### 4.3 Not recommended for first internal MVP

- **CodeQL**
  - powerful, but not a first-choice foundation for the current internal-only, low-friction MVP direction

### 4.4 Platform responsibility versus scanner responsibility

#### Scanners should do
- detect issues
- produce raw outputs
- provide metadata and evidence

#### Platform should do
- run tools
- normalize results
- deduplicate findings
- track history
- enrich severity and remediation data
- generate dashboards
- manage users/projects/roles
- store artifacts
- support exports and notifications

---

## 5. High-level system architecture

### 5.1 Architectural overview

The system is divided into five major runtime layers:

1. **Next.js frontend on Vercel**
2. **FastAPI web API on Render**
3. **Python background workers on Render**
4. **Neon Postgres as system of record**
5. **Cloudflare R2 and Upstash Redis for artifacts and queue/cache**

### 5.2 Frontend responsibilities

The Next.js application is responsible for:

- authentication-facing UI
- organization and project dashboards
- findings pages
- scan history views
- reports UI
- settings and admin pages
- role-sensitive experience rendering
- export download UX

The frontend should **not** own scan orchestration or scanner execution logic.

### 5.3 Backend API responsibilities

The FastAPI service is responsible for:

- REST API endpoints
- authentication integration
- organization/project/repository CRUD
- scan creation and status APIs
- findings listing and details
- export generation requests
- webhook receivers
- audit log writes
- policy and suppression endpoints later

### 5.4 Worker responsibilities

The worker service is responsible for:

- queue consumption
- repo preparation
- scanner execution
- raw artifact upload to R2
- normalized finding persistence
- finding enrichment
- notification dispatch
- scheduled scan processing
- cleanup/retention tasks

### 5.5 Data/storage responsibilities

#### Neon Postgres
Store:
- users
- organizations
- memberships
- projects
- repositories
- scans
- scanner runs
- findings
- finding instances
- finding lifecycle events
- suppressions
- exports metadata
- audit logs

#### Cloudflare R2
Store:
- raw scanner JSON
- SARIF files
- SBOM files
- report exports
- logs and large artifacts

#### Upstash Redis
Store:
- queued jobs
- job locks
- retry counters
- temporary scan state
- cache and rate-limiting data

Redis must **not** be used as the permanent system of record.

---

## 6. Runtime topology

### 6.1 Vercel
Deploy:
- one Next.js application

### 6.2 Render
Deploy:
- one FastAPI web service
- one worker service
- one or more cron jobs

### 6.3 Render cron jobs

Recommended cron jobs:

- nightly scan scheduler
- weekly deep scan scheduler
- stale notification cleanup
- artifact retention cleanup
- metrics/trend recalculation

### 6.4 Environment separation

Use:
- local
- preview/dev
- staging
- production

Use Neon branching to support environment testing and migration rehearsal.

---

## 7. Request and job flows

### 7.1 Repository onboarding flow

1. User signs in
2. User creates or selects an organization
3. User creates a project
4. User connects a repository
5. Integration metadata is saved
6. Initial scan is created
7. Scan job is queued
8. Worker executes scanner pipeline
9. Findings are normalized and stored
10. Dashboard updates with initial results

### 7.2 Manual scan flow

1. User clicks “Run scan”
2. Frontend calls FastAPI
3. FastAPI creates `scan` row with `queued` status
4. Worker job is enqueued in Redis
5. Worker prepares repository snapshot
6. Worker runs applicable scanners
7. Raw outputs are uploaded to R2
8. Findings are normalized and stored in Postgres
9. Scan status is updated
10. Notifications are sent if configured

### 7.3 Scheduled scan flow

1. Render Cron triggers scheduler
2. Scheduler identifies eligible repositories/projects
3. Jobs are enqueued in batches
4. Workers process scans
5. New findings are compared to historical findings
6. Notification events are written if thresholds are met

### 7.4 Finding lifecycle flow

1. Scanner detects issue
2. Platform computes canonical fingerprint
3. Existing finding match is attempted
4. If match exists, update `last_seen_at`
5. If no match, create new `finding`
6. Create `finding_instance`
7. Generate `finding_event`
8. Update project/scan summaries

---

## 8. Canonical domain model

The platform schema is organized into these domains:

1. identity and access
2. organizations and membership
3. projects and repositories
4. scans and scanner runs
5. findings and finding instances
6. suppressions and governance
7. artifacts and exports
8. notifications
9. audit logs

### 8.1 Core entity relationships

- one organization has many members
- one organization has many projects
- one project has many repositories
- one repository has many scans
- one scan has many scanner runs
- one scan can produce many finding instances
- one logical finding has many finding instances over time
- one finding has many references, events, and suppressions

---

## 9. Database schema backbone

### 9.1 Must-have tables

#### Identity and access
- `users`
- `organizations`
- `organization_members`

#### Project and repository core
- `projects`
- `repositories`
- `repository_integrations`
- `scan_schedules`

#### Scanning core
- `scans`
- `scanner_runs`
- `scan_artifacts`

#### Findings core
- `findings`
- `finding_instances`
- `finding_references`
- `finding_events`

#### Governance
- `suppression_rules`
- `finding_suppressions`

#### Operational support
- `exports`
- `audit_logs`

### 9.2 Logical finding versus finding instance

This is one of the most important design decisions.

#### `findings`
Represents the durable logical issue over time.

Examples:
- the same exposed secret seen in repeated scans
- the same vulnerable dependency seen across multiple scan runs
- the same suspicious code pattern recurring in the repo

#### `finding_instances`
Represents a specific appearance of that issue in one scan.

Examples:
- exact path/line occurrence for a given scan
- package version and advisory evidence in a specific scan

### 9.3 Key uniqueness rule

Use a `canonical_fingerprint` on `findings` so recurring issues can be tracked across time.

Examples of fingerprint inputs:

#### Secret findings
- category
- secret type
- repository
- path
- normalized location window

#### Vulnerable dependency findings
- category
- package name
- installed version
- manifest path
- advisory identifier

#### Static issue findings
- category
- normalized rule id
- repo
- path
- symbol or function name if available

---

## 10. SQLAlchemy modeling strategy

### 10.1 ORM approach

Use modern SQLAlchemy 2.x style with:

- `DeclarativeBase`
- typed `Mapped[...]`
- `mapped_column()`
- explicit `relationship()` definitions
- PostgreSQL UUID primary keys

### 10.2 Shared ORM patterns

Use:
- UUID primary keys everywhere
- timestamp mixins
- Postgres enums for stable categories
- JSONB only for variable metadata/evidence payloads

### 10.3 ORM responsibilities

Keep ORM models focused on:
- fields
- relationships
- constraints
- indexes

Do **not** embed heavy business logic into model classes.

### 10.4 Service-layer responsibilities

Put business logic into services such as:

- `services/scans.py`
- `services/findings.py`
- `services/permissions.py`
- `services/reports.py`
- `services/notifications.py`

---

## 11. Queue and worker design

### 11.1 Redis responsibilities

Use Upstash Redis for:
- scan queue entries
- worker locks
- retry tracking
- transient status cache
- rate limiting

### 11.2 Suggested job types

- `scan.repo.full`
- `scan.repo.diff`
- `scan.dependencies`
- `scan.secrets`
- `scan.normalize`
- `scan.export`
- `scan.notify`
- `score.recalculate`
- `retention.cleanup`

### 11.3 Job stage model

Recommended stages:
- queued
- claimed
- repo_prepared
- scanners_running
- artifacts_uploaded
- normalized
- persisted
- notifications_sent
- done

This gives better internal observability than a single broad “running” state.

---

## 12. Scan orchestration pipeline

### Phase A — target preparation
- resolve project/repository/branch/commit
- create scan record
- fetch repository snapshot
- detect relevant files and manifests

### Phase B — scanner selection
Run tools based on repository contents.

Examples:
- lockfiles/manifests present → OSV / Trivy
- secrets exposure check → Gitleaks
- Dockerfile or image support later → Trivy
- SBOM support later → Syft → Grype
- IaC support later → Checkov

### Phase C — raw artifact storage
Store raw outputs in R2:
- JSON
- SARIF
- SBOM files
- logs
- evidence bundles

### Phase D — normalization
Convert each scanner output into the platform’s canonical finding model.

### Phase E — deduplication and correlation
- compare with existing canonical fingerprints
- determine whether issue is new, existing, or regressed

### Phase F — enrichment
- normalize severity
- attach references
- add remediation summary where available
- update summary metrics

### Phase G — persistence and notifications
- write scan summaries
- update findings and instances
- write finding events
- trigger notification events

---

## 13. Findings model and prioritization

### 13.1 Canonical finding categories

Use the following categories from day one:

- vulnerability
- secret
- dependency_outdated
- malicious_pattern
- code_quality
- container_risk
- iac_misconfiguration
- license_compliance

### 13.2 Severity model

Use:
- critical
- high
- medium
- low
- info

### 13.3 Finding states

Use:
- open
- fixed
- suppressed
- accepted_risk
- duplicate

### 13.4 Finding lifecycle events

Track events such as:
- opened
- reopened
- fixed
- suppressed
- unsuppressed
- severity_changed
- accepted_risk

### 13.5 Prioritization inputs

For MVP, prioritize using:
- severity
- finding category
- whether fix version exists
- whether issue is new
- whether branch is default branch
- age of the finding

Do not over-engineer exploitability scoring in MVP.

---

## 14. Auth and RBAC model

### 14.1 Auth direction

Use **Neon Auth** for now, but keep auth provider concerns separated from application authorization.

### 14.2 App-owned RBAC

The platform should own authorization through app tables and logic.

Recommended roles:
- owner
- admin
- security_reviewer
- developer
- viewer

### 14.3 Responsibility split

#### Auth provider should handle
- identity
- sessions
- authentication lifecycle

#### App should handle
- org membership
- project access
- admin privileges
- suppression permissions
- export permissions
- audit-sensitive actions

### 14.4 Why this matters

This prevents provider lock-in and keeps business authorization rules stable if auth changes later.

---

## 15. Frontend information architecture

### 15.1 Major route groups

Recommended high-level route groups:

- marketing
- auth
- dashboard
  - org home
  - projects list
  - project overview
  - findings
  - scans
  - dependencies
  - reports
  - team/settings
  - audit

### 15.2 Core pages for MVP

#### Organization dashboard
- project cards
- scan status summary
- top risk counts

#### Project overview page
- security score summary
- latest scan status
- open critical/high findings
- trend snapshot

#### Findings page
- filters by severity/category/status/scanner
- table view
- detail panel/page

#### Scan details page
- scanner run status
- timing
- artifact links
- findings detected in the scan

#### Reports page
- export history
- generate report action
- download artifacts

#### Audit page
- recent privileged actions
- scan triggers
- suppressions
- exports

---

## 16. API design principles

### 16.1 API style

Use a versioned REST API under:

`/api/v1`

### 16.2 Initial endpoint groups

#### Organization/project/repository
- create organization
- create project
- connect repository
- list repositories

#### Scans
- create scan
- list scans
- get scan details
- cancel scan later if needed

#### Findings
- list findings
- get finding detail
- suppress finding
- list finding events

#### Exports
- create export
- list exports
- download export metadata

#### Audit
- list audit logs

#### Webhooks
- provider webhook receiver

### 16.3 Filtering expectations

The findings list should support filtering by:
- severity
- category
- status
- scanner
- repository
- date range
- fix available
- text search

---

## 17. Artifact and report strategy

### 17.1 What goes to R2

- raw scanner outputs
- normalized export bundles
- SBOM files
- logs too large for Postgres
- generated PDF/CSV/JSON reports

### 17.2 What stays in Postgres

- artifact metadata
- export metadata
- scan summary metadata
- finding summaries

### 17.3 Export formats for MVP

Support:
- JSON
- CSV
- PDF

### 17.4 Report types

Start with:
- project summary report
- findings export report
- scan-specific report

---

## 18. Notifications strategy

### 18.1 MVP notification targets

Start with:
- in-app notifications
- email notifications

Slack webhooks can come shortly after MVP if needed.

### 18.2 Trigger conditions

Send notifications for:
- first critical finding in a project
- new secret exposure
- scan failure repeated more than once
- scheduled scan completed with new high/critical issues

### 18.3 Notification storage

Persist notification events to Postgres for traceability.

---

## 19. Audit logging strategy

### 19.1 Actions that must be audited

Audit at minimum:
- organization creation
- membership changes
- project creation
- repository connection/disconnection
- scan creation
- suppression actions
- report export requests
- privileged settings changes

### 19.2 Suggested audit payload

Each audit log should include:
- actor
- action
- target type
- target id
- timestamp
- metadata JSON
- optional IP/user agent if available and appropriate

### 19.3 Why audit logs matter early

Audit logs add value immediately for:
- debugging user actions
- internal accountability
- future enterprise-readiness

---

## 20. Score and dashboard model

### 20.1 Dashboard scores

Do not rely only on one opaque score.

Recommended score buckets:
- security score
- dependency health score
- secrets hygiene score
- code health score

### 20.2 Inputs for early scoring

Use simple weighted inputs based on:
- count of open findings by severity
- age of unresolved findings
- unresolved secret count
- fix availability
- newly introduced findings

### 20.3 Executive overview

You may also show one blended top-line score for convenience, but keep the sub-scores visible.

---

## 21. Project structure recommendation

### 21.1 Suggested repository structure

```text
/apps
  /web
  /api
  /worker
/packages
  /shared-contracts
  /security-rules
/infrastructure
  /render
  /vercel
  /neon
  /r2
/docs
  /architecture
  /prd
  /adr
  /runbooks
```

### 21.2 Simplified alternative for MVP

If needed, simplify to:

```text
/web
/backend
/docs
```

Where:
- `web` = Next.js app
- `backend` = FastAPI + worker + DB models
- `docs` = architecture, PRD, ADRs

---

## 22. Environment variables and config domains

### 22.1 Frontend config

Examples:
- app URL
- API base URL
- public auth settings
- feature flags if used

### 22.2 Backend config

Examples:
- database URL
- auth provider config
- webhook secrets
- R2 credentials
- Upstash credentials
- scan profile settings
- retention settings

### 22.3 Worker config

Examples:
- queue config
- artifact storage config
- scanner binary paths or invocation config
- concurrency limits
- job timeout settings

---

## 23. MVP implementation phases

## Phase 0 — foundation and repo setup

Deliverables:
- monorepo or split repo structure
- FastAPI skeleton
- Next.js skeleton
- SQLAlchemy base setup
- Alembic setup
- Neon connection
- Render service definitions
- Vercel deployment setup

## Phase 1 — identity and tenant core

Deliverables:
- Neon Auth integration
- app user sync
- organizations
- memberships
- basic role enforcement

## Phase 2 — project and repository core

Deliverables:
- project CRUD
- repository connection model
- integration metadata persistence
- dashboard shell

## Phase 3 — scan pipeline core

Deliverables:
- scan creation endpoint
- worker queue integration
- repository preparation flow
- Trivy/Gitleaks/OSV integration
- raw artifact upload to R2
- scan status updates

## Phase 4 — findings model and UI

Deliverables:
- normalization pipeline
- canonical finding storage
- finding instances
- findings list/detail UI
- filters and scan detail page

## Phase 5 — scheduled monitoring and exports

Deliverables:
- scan schedules
- Render cron jobs
- export creation
- CSV/JSON/PDF output
- basic notifications
- audit logs

## Phase 6 — hardening and UX polish

Deliverables:
- retry logic
- error handling improvements
- performance tuning
- dashboard scorecards
- onboarding polish

---

## 24. Database migration order

Recommended Alembic migration sequence:

### Migration 001
- users
- organizations
- organization_members

### Migration 002
- projects
- repositories
- repository_integrations
- scan_schedules

### Migration 003
- scans
- scanner_runs
- scan_artifacts

### Migration 004
- findings
- finding_instances
- finding_references
- finding_events

### Migration 005
- suppression_rules
- finding_suppressions

### Migration 006
- exports
- audit_logs

Add notifications and policy tables after the first working MVP if needed.

---

## 25. Risks and mitigation strategy

### 25.1 False positives

**Risk:** users lose trust if too many false positives appear.

**Mitigation:**
- suppression support
- finding lifecycle tracking
- clear evidence display
- severity normalization

### 25.2 Scan runtime complexity

**Risk:** long-running or unreliable scan jobs.

**Mitigation:**
- worker isolation
- scanner-specific run tracking
- retries with caps
- artifact/log preservation

### 25.3 Cost creep

**Risk:** usage-based services scale cost unexpectedly.

**Mitigation:**
- keep raw artifacts only as long as needed
- avoid storing unnecessary blobs in Postgres
- batch scheduled scans
- monitor R2 and Render usage early

### 25.4 Auth coupling

**Risk:** auth-provider-specific logic spreads across the app.

**Mitigation:**
- keep authorization app-owned
- isolate auth integration layer

### 25.5 Schema overengineering

**Risk:** too many abstractions too early slow delivery.

**Mitigation:**
- center MVP on projects, repositories, scans, findings, and finding instances
- defer advanced policy/team structures

---

## 26. Operational principles

### 26.1 Source of truth rules

- Postgres is the source of truth for normalized business data
- R2 is the source of truth for large raw artifacts
- Redis is not a source of truth

### 26.2 Architectural rule

Build around the platform’s **canonical finding model**, not around any one scanner’s raw output format.

### 26.3 Development rule

Keep business logic in service layers, not ORM classes and not frontend pages.

### 26.4 Product rule

Validate the web app workflows first. MCP is an access layer to add later after the platform concepts are stable.

---

## 27. Final locked foundation

### Application stack
- Frontend: Next.js
- Backend: FastAPI
- Workers: Python background workers
- DB: Neon Postgres
- ORM: SQLAlchemy
- Auth: Neon Auth *(for now)*

### Infrastructure stack
- Frontend hosting: Vercel
- Backend API + workers + cron: Render
- Object storage: Cloudflare R2
- Queue/cache: Upstash Redis

### Scanner direction
- Trivy
- Gitleaks
- OSV-Scanner / OSV API
- Syft
- Grype
- Checkov later
- Semgrep Community Edition optional later

### Product sequencing
1. web app first
2. stable API and worker model
3. scan pipeline and findings workflows
4. exports, audit, notifications
5. MCP later

---

## 28. Recommended next deliverables

After this architectural implementation plan, the best next documents to create are:

1. **PRD / feature scope document**
2. **API contract specification**
3. **SQLAlchemy + Alembic implementation scaffold**
4. **Worker/queue orchestration specification**
5. **Frontend information architecture and page spec**
6. **MVP task breakdown**

---

## 29. Conclusion

This plan gives you a strong, modern, web-first architecture for an internal repository monitoring platform that is practical to build, extensible over time, and aligned with the tool and hosting choices already locked.

The most important decisions already made are the right ones:

- web app first
- orchestration platform over custom scanners
- FastAPI + Next.js split
- Postgres-backed normalized findings model
- dedicated workers and scheduled jobs
- artifact storage separated from relational data
- auth separated from RBAC
- MCP deferred until the platform is stable

This is a solid foundation for a serious build.
