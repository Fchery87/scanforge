# ScanForge Security Platform — Build Implementation Plan

**Status:** Ready for Implementation  
**Based on:** ScanForge-architecture-implementation-plan.md  
**Purpose:** Detailed task breakdown for building the remaining 85% of the platform  
**Last updated:** 2026-03-21

---

## 1. Overview

The scaffold is ~15% implemented. This plan details the remaining 85% across 6 phases, organized by dependency order.

### What Exists
- ✅ Monorepo structure (`apps/web`, `apps/api`, `apps/worker`, `packages`, `infra`, `docs`)
- ✅ All SQLAlchemy 2.x models with proper relationships, enums, mixins
- ✅ FastAPI skeleton with router structure
- ✅ Next.js skeleton with basic pages and layout
- ✅ Alembic configuration (but migrations are empty)
- ✅ Environment variable templates

### What Needs to Be Built
- Alembic migrations (6 migration files)
- Auth middleware and integration
- API routes (organizations, projects, repositories, scans, findings, exports, audit)
- Service layer (8+ business logic modules)
- Pydantic schemas (7+ request/response models)
- Worker infrastructure (queue client, R2 client, scanner adapters)
- Frontend pages (10+ pages)
- Infrastructure configs (Render blueprint, Vercel config)

---

## 2. Implementation Phases

```
Phase 0.5 ─── Alembic Migrations ──────────────────────── Week 1
Phase 1 ───── Auth & Identity ─────────────────────────── Week 1-2
Phase 2 ───── Project & Repository Core ─────────────────── Week 2-3
Phase 3 ───── Scan Pipeline ─────────────────────────────── Week 3-4
Phase 4 ───── Findings & Normalization ─────────────────── Week 4-5
Phase 5 ───── UI & Dashboard ────────────────────────────── Week 5-7
Phase 6 ───── Exports, Notifications, Audit ────────────── Week 7-8
Phase 7 ───── Hardening & Polish ───────────────────────── Week 8-9
```

---

## 3. Phase 0.5 — Alembic Migrations

**Goal:** Create real database schema migrations so the application can deploy.

### 3.1 Migration 001 — Identity & Access

**File:** `apps/api/alembic/versions/0001_identity_and_access.py`

```python
"""identity and access

Revision ID: 0001_identity_and_access
Revises:
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # users table
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_provider_user_id", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_auth_provider_user_id", "users", ["auth_provider_user_id"])

    # organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), unique=True, nullable=False),
        sa.Column("created_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # organization_members table
    op.create_table(
        "organization_members",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("owner", "admin", "security_reviewer", "developer", "viewer", name="member_role"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_organization_members_org_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])
    op.create_unique_constraint("uq_org_member_org_user", "organization_members", ["organization_id", "user_id"])

def downgrade() -> None:
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("users")
```

### 3.2 Migration 002 — Projects & Repositories

**File:** `apps/api/alembic/versions/0002_projects_and_repositories.py`

```python
"""projects and repositories

Revision ID: 0002_projects_and_repositories
Revises: 0001_identity_and_access
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_projects_org_id", "projects", ["organization_id"])
    op.create_unique_constraint("uq_project_org_slug", "projects", ["organization_id", "slug"])

    # repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Enum("github", "gitlab", "bitbucket", "manual", name="repo_provider"), nullable=False),
        sa.Column("external_repo_id", sa.String(255), nullable=True),
        sa.Column("owner_name", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("clone_url", sa.String(1024), nullable=True),
        sa.Column("html_url", sa.String(1024), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])
    op.create_unique_constraint("uq_repo_provider_full_name", "repositories", ["provider", "full_name"])

    # repository_integrations table
    op.create_table(
        "repository_integrations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("installation_id", sa.String(255), nullable=True),
        sa.Column("provider_account_id", sa.String(255), nullable=True),
        sa.Column("webhook_secret_ref", sa.String(255), nullable=True),
        sa.Column("access_metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    # scan_schedules table
    op.create_table(
        "scan_schedules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_type", sa.String(50), nullable=False),  # daily, weekly, on_push
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_type", sa.String(50), nullable=False),  # full, diff, dependencies
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_scan_schedules_repository_id", "scan_schedules", ["repository_id"])
    op.create_index("ix_scan_schedules_next_run_at", "scan_schedules", ["next_run_at"])

def downgrade() -> None:
    op.drop_table("scan_schedules")
    op.drop_table("repository_integrations")
    op.drop_table("repositories")
    op.drop_table("projects")
```

### 3.3 Migration 003 — Scanning Core

**File:** `apps/api/alembic/versions/0003_scanning_core.py`

```python
"""scanning core

Revision ID: 0003_scanning_core
Revises: 0002_projects_and_repositories
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # scans table
    op.create_table(
        "scans",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),  # manual, scheduled, webhook
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", "canceled", name="scan_status"), nullable=False, default="queued"),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("pull_request_number", sa.Integer, nullable=True),
        sa.Column("requested_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("summary_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_scans_project_id", "scans", ["project_id"])
    op.create_index("ix_scans_repository_id", "scans", ["repository_id"])
    op.create_index("ix_scans_commit_sha", "scans", ["commit_sha"])

    # scanner_runs table
    op.create_table(
        "scanner_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner_name", sa.String(50), nullable=False),
        sa.Column("scanner_version", sa.String(64), nullable=True),
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", "canceled", name="scan_status"), nullable=False, default="queued"),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("exit_code", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("artifact_uri", sa.String(2048), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_scanner_runs_scan_id", "scanner_runs", ["scan_id"])
    op.create_index("ix_scanner_runs_scanner_name", "scanner_runs", ["scanner_name"])

    # scan_artifacts table
    op.create_table(
        "scan_artifacts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner_run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scanner_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("artifact_type", sa.String(50), nullable=False),  # raw_json, sarif, sbom, log
        sa.Column("storage_uri", sa.String(2048), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_scan_artifacts_scan_id", "scan_artifacts", ["scan_id"])

def downgrade() -> None:
    op.drop_table("scan_artifacts")
    op.drop_table("scanner_runs")
    op.drop_table("scans")
```

### 3.4 Migration 004 — Findings Core

**File:** `apps/api/alembic/versions/0004_findings_core.py`

```python
"""findings core

Revision ID: 0004_findings_core
Revises: 0003_scanning_core
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # findings table
    op.create_table(
        "findings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),  # vulnerability, secret, dependency_outdated, etc.
        sa.Column("severity", sa.String(20), nullable=False),  # critical, high, medium, low, info
        sa.Column("status", sa.String(20), nullable=False, default="open"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("canonical_fingerprint", sa.String(255), nullable=False),
        sa.Column("primary_scanner", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("fixed_version", sa.String(128), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_findings_project_id", "findings", ["project_id"])
    op.create_index("ix_findings_repository_id", "findings", ["repository_id"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_fingerprint", "findings", ["canonical_fingerprint"])
    op.create_unique_constraint("uq_finding_repo_fingerprint", "findings", ["repository_id", "canonical_fingerprint"])

    # finding_instances table
    op.create_table(
        "finding_instances",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner_run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scanner_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path", sa.String(2048), nullable=True),
        sa.Column("line_start", sa.Integer, nullable=True),
        sa.Column("line_end", sa.Integer, nullable=True),
        sa.Column("package_name", sa.String(255), nullable=True),
        sa.Column("installed_version", sa.String(128), nullable=True),
        sa.Column("fixed_version", sa.String(128), nullable=True),
        sa.Column("evidence_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_finding_instances_finding_id", "finding_instances", ["finding_id"])
    op.create_index("ix_finding_instances_scan_id", "finding_instances", ["scan_id"])
    op.create_index("ix_finding_instances_package_name", "finding_instances", ["package_name"])

    # finding_references table
    op.create_table(
        "finding_references",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),  # advisory, documentation, commit
        sa.Column("reference_value", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_finding_references_finding_id", "finding_references", ["finding_id"])

    # finding_events table
    op.create_table(
        "finding_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),  # opened, reopened, fixed, suppressed, etc.
        sa.Column("actor_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_finding_events_finding_id", "finding_events", ["finding_id"])

def downgrade() -> None:
    op.drop_table("finding_events")
    op.drop_table("finding_references")
    op.drop_table("finding_instances")
    op.drop_table("findings")
```

### 3.5 Migration 005 — Governance

**File:** `apps/api/alembic/versions/0005_governance.py`

```python
"""governance

Revision ID: 0005_governance
Revises: 0004_findings_core
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # suppression_rules table
    op.create_table(
        "suppression_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("repository_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rule_type", sa.String(50), nullable=False),  # fingerprint, path, package
        sa.Column("match_criteria_json", JSONB, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_suppression_rules_org_id", "suppression_rules", ["organization_id"])

    # finding_suppressions table
    op.create_table(
        "finding_suppressions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("suppression_rule_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppression_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suppressed_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_finding_suppressions_finding_id", "finding_suppressions", ["finding_id"])

def downgrade() -> None:
    op.drop_table("finding_suppressions")
    op.drop_table("suppression_rules")
```

### 3.6 Migration 006 — Operational Support

**File:** `apps/api/alembic/versions/0006_operational_support.py`

```python
"""operational support

Revision ID: 0006_operational_support
Revises: 0005_governance
Create Date: 2026-03-21
"""

def upgrade() -> None:
    # exports table
    op.create_table(
        "exports",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("export_type", sa.String(50), nullable=False),  # findings, scan_report, project_summary
        sa.Column("format", sa.String(20), nullable=False),  # json, csv, pdf
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("requested_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filter_criteria_json", JSONB, nullable=True),
        sa.Column("storage_uri", sa.String(2048), nullable=True),
        sa.Column("artifact_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_exports_project_id", "exports", ["project_id"])
    op.create_index("ix_exports_status", "exports", ["status"])

    # audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("ip_address", INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),  # finding_alert, scan_complete, scan_failed
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("target_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean, default=False, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_org_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("exports")
```

---

## 4. Phase 1 — Auth & Identity

### 4.1 Directory Structure

```
apps/api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── routes/
│   │           ├── __init__.py
│   │           ├── auth.py          # Auth callback, session endpoints
│   │           ├── organizations.py
│   │           ├── memberships.py
│   │           ├── projects.py
│   │           ├── repositories.py
│   │           ├── scans.py
│   │           ├── findings.py
│   │           ├── exports.py
│   │           ├── notifications.py
│   │           └── audit.py
│   ├── core/
│   │   ├── config.py               # Extend with auth settings
│   │   └── security.py              # JWT validation, password hashing
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                  # Auth dependency
│   │   ├── rbac.py                  # Permission checks
│   │   └── audit.py                 # Audit logging middleware
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── organizations.py
│   │   ├── memberships.py
│   │   ├── projects.py
│   │   ├── repositories.py
│   │   ├── scans.py
│   │   ├── findings.py
│   │   ├── exports.py
│   │   ├── notifications.py
│   │   └── common.py                # Pagination, filters, responses
│   └── services/
│       ├── __init__.py
│       ├── auth.py                  # Neon Auth integration
│       ├── users.py
│       ├── organizations.py
│       ├── memberships.py
│       ├── projects.py
│       ├── repositories.py
│       ├── scans.py
│       ├── findings.py
│       ├── exports.py
│       ├── notifications.py
│       └── audit.py
```

### 4.2 Core Config Extension

**File:** `apps/api/app/core/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Database
    DATABASE_URL: str
    
    # App
    APP_ENV: str = "development"
    APP_NAME: str = "repo-security-platform-api"
    
    # Neon Auth
    NEON_AUTH_ISSUER: str = ""
    NEON_AUTH_AUDIENCE: str = ""
    NEON_AUTH_JWKS_URL: str = ""
    NEON_AUTH_CLIENT_ID: str = ""
    NEON_AUTH_CLIENT_SECRET: str = ""
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # R2
    R2_ENDPOINT: str = ""
    R2_BUCKET: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_PUBLIC_BASE_URL: str = ""
    
    # Redis
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    
    # GitHub
    GITHUB_APP_ID: str = ""
    GITHUB_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    
    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    
    # Slack
    SLACK_WEBHOOK_URL: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4.3 Auth Middleware

**File:** `apps/api/app/middleware/auth.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from typing import Optional
import json
from functools import lru_cache

security = HTTPBearer(auto_error=False)

class JWKSClient:
    def __init__(self, jwks_url: str):
        self.jwks_url = jwks_url
        self._jwks: Optional[dict] = None
    
    async def get_jwks(self) -> dict:
        if self._jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url)
                self._jwks = response.json()
        return self._jwks

@lru_cache
def get_jwks_client() -> JWKSClient:
    from app.core.config import get_settings
    settings = get_settings()
    return JWKSClient(settings.NEON_AUTH_JWKS_URL)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwks_client: JWKSClient = Depends(get_jwks_client),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        jwks = await jwks_client.get_jwks()
        payload = jwt.decode(
            credentials.credentials,
            jwks,
            algorithms=["RS256"],
            audience=settings.NEON_AUTH_AUDIENCE,
            issuer=settings.NEON_AUTH_ISSUER,
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict]:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
```

### 4.4 RBAC Middleware

**File:** `apps/api/app/middleware/rbac.py`

```python
from fastapi import HTTPException, status, Depends
from typing import Callable
from enum import Enum

class Permission(str, Enum):
    # Organization permissions
    ORG_MANAGE = "org:manage"
    ORG_MEMBER_INVITE = "org:member:invite"
    ORG_MEMBER_REMOVE = "org:member:remove"
    ORG_SETTINGS_VIEW = "org:settings:view"
    ORG_SETTINGS_EDIT = "org:settings:edit"
    
    # Project permissions
    PROJECT_MANAGE = "project:manage"
    PROJECT_VIEW = "project:view"
    
    # Repository permissions
    REPO_CONNECT = "repo:connect"
    REPO_DISCONNECT = "repo:disconnect"
    REPO_VIEW = "repo:view"
    
    # Scan permissions
    SCAN_TRIGGER = "scan:trigger"
    SCAN_VIEW = "scan:view"
    SCAN_CANCEL = "scan:cancel"
    
    # Finding permissions
    FINDING_VIEW = "finding:view"
    FINDING_SUPPRESS = "finding:suppress"
    FINDING_RESOLVE = "finding:resolve"
    
    # Export permissions
    EXPORT_CREATE = "export:create"
    EXPORT_VIEW = "export:view"
    
    # Admin
    ADMIN = "admin"

ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    "owner": [p for p in Permission],  # All permissions
    "admin": [
        Permission.ORG_MEMBER_INVITE,
        Permission.ORG_MEMBER_REMOVE,
        Permission.ORG_SETTINGS_EDIT,
        Permission.PROJECT_MANAGE,
        Permission.REPO_CONNECT,
        Permission.REPO_DISCONNECT,
        Permission.SCAN_TRIGGER,
        Permission.SCAN_VIEW,
        Permission.SCAN_CANCEL,
        Permission.FINDING_VIEW,
        Permission.FINDING_SUPPRESS,
        Permission.FINDING_RESOLVE,
        Permission.EXPORT_CREATE,
        Permission.EXPORT_VIEW,
    ],
    "security_reviewer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
        Permission.FINDING_SUPPRESS,
        Permission.EXPORT_CREATE,
        Permission.EXPORT_VIEW,
    ],
    "developer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_TRIGGER,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
        Permission.EXPORT_VIEW,
    ],
    "viewer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
    ],
}

def require_permission(permission: Permission):
    async def dependency(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        # Get user role from token or database
        user_role = current_user.get("role", "viewer")
        
        if permission in ROLE_PERMISSIONS.get(user_role, []):
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required: {permission}",
        )
    return dependency
```

### 4.5 Service Layer: Organizations

**File:** `apps/api/app/services/organizations.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from app.db.models import Organization, OrganizationMember
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate

class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        data: OrganizationCreate,
        user_id: UUID,
    ) -> Organization:
        org = Organization(
            name=data.name,
            slug=data.slug,
            created_by_user_id=user_id,
        )
        self.db.add(org)
        await self.db.flush()
        
        # Add creator as owner
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user_id,
            role="owner",
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(org)
        return org
    
    async def get_by_id(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> Organization | None:
        # Check user is member
        membership = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        if not membership.scalar_one_or_none():
            return None
        
        result = await self.db.execute(
            select(Organization)
            .options(selectinload(Organization.members))
            .where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def list_for_user(
        self,
        user_id: UUID,
    ) -> list[Organization]:
        result = await self.db.execute(
            select(Organization)
            .join(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.name)
        )
        return list(result.scalars().all())
    
    async def update(
        self,
        org_id: UUID,
        data: OrganizationUpdate,
    ) -> Organization | None:
        org = await self.db.get(Organization, org_id)
        if not org:
            return None
        
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        
        await self.db.commit()
        await self.db.refresh(org)
        return org
    
    async def delete(self, org_id: UUID) -> bool:
        org = await self.db.get(Organization, org_id)
        if not org:
            return False
        
        await self.db.delete(org)
        await self.db.commit()
        return True
```

### 4.6 Organization Routes

**File:** `apps/api/app/api/v1/routes/organizations.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)
from app.services.organizations import OrganizationService

router = APIRouter()

@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.create(data, UUID(current_user["sub"]))
    return org

@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    orgs = await service.list_for_user(UUID(current_user["sub"]))
    return orgs

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.get_by_id(org_id, UUID(current_user["sub"]))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.update(org_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    deleted = await service.delete(org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
```

---

## 5. Phase 2 — Project & Repository Core

### 5.1 Service: Projects

```python
# apps/api/app/services/projects.py

class ProjectService:
    async def create(
        self,
        org_id: UUID,
        data: ProjectCreate,
        user_id: UUID,
    ) -> Project:
        project = Project(
            organization_id=org_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            default_branch=data.default_branch,
            created_by_user_id=user_id,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def get_by_id(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> Project | None:
        # Check user has access via org membership
        result = await self.db.execute(
            select(Project)
            .join(Organization)
            .join(OrganizationMember)
            .where(
                Project.id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_for_org(
        self,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Project], int]:
        # Count
        count_result = await self.db.execute(
            select(func.count(Project.id))
            .where(Project.organization_id == org_id)
        )
        total = count_result.scalar_one()
        
        # List
        result = await self.db.execute(
            select(Project)
            .where(Project.organization_id == org_id)
            .order_by(Project.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        projects = list(result.scalars().all())
        
        return projects, total
    
    async def update(
        self,
        project_id: UUID,
        data: ProjectUpdate,
    ) -> Project | None:
        project = await self.db.get(Project, project_id)
        if not project:
            return None
        
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        
        await self.db.commit()
        await self.db.refresh(project)
        return project
```

### 5.2 Service: Repositories

```python
# apps/api/app/services/repositories.py

class RepositoryService:
    async def connect(
        self,
        project_id: UUID,
        data: RepositoryConnect,
        user_id: UUID,
    ) -> Repository:
        repo = Repository(
            project_id=project_id,
            provider=data.provider,
            external_repo_id=data.external_repo_id,
            owner_name=data.owner_name,
            repo_name=data.repo_name,
            full_name=data.full_name,
            default_branch=data.default_branch,
            clone_url=data.clone_url,
            html_url=data.html_url,
        )
        self.db.add(repo)
        await self.db.flush()
        
        # Create integration if provider is GitHub
        if data.provider == "github" and data.installation_id:
            integration = RepositoryIntegration(
                repository_id=repo.id,
                installation_id=data.installation_id,
                provider_account_id=data.provider_account_id,
            )
            self.db.add(integration)
        
        await self.db.commit()
        await self.db.refresh(repo)
        return repo
    
    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Repository], int]:
        query = (
            select(Repository)
            .where(Repository.project_id == project_id)
        )
        
        if is_active is not None:
            query = query.where(Repository.is_active == is_active)
        
        count_result = await self.db.execute(
            select(func.count(Repository.id))
            .where(Repository.project_id == project_id)
        )
        total = count_result.scalar_one()
        
        result = await self.db.execute(
            query
            .order_by(Repository.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        repos = list(result.scalars().all())
        
        return repos, total
    
    async def disconnect(
        self,
        repo_id: UUID,
    ) -> bool:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            return False
        
        repo.is_active = False
        await self.db.commit()
        return True
```

---

## 6. Phase 3 — Scan Pipeline

### 6.1 Queue Client

**File:** `apps/worker/app/clients/queue.py`

```python
from upstash_redis import Redis
from pydantic import BaseModel
from typing import Literal
from uuid import UUID
import json

class QueueJob(BaseModel):
    job_type: str  # scan.repo.full, scan.repo.diff, etc.
    job_id: str
    payload: dict
    created_at: str

class QueueClient:
    def __init__(self, redis_url: str, redis_token: str):
        self.redis = Redis(url=redis_url, token=redis_token)
        self.scan_queue = "queue:scans"
        self.dlq = "queue:scans:dlq"
    
    async def enqueue(
        self,
        job_type: Literal["scan.repo.full", "scan.repo.diff", "scan.dependencies", "scan.secrets"],
        payload: dict,
        delay_seconds: int = 0,
    ) -> str:
        job_id = str(UUID.uuid4())
        job = QueueJob(
            job_type=job_type,
            job_id=job_id,
            payload=payload,
            created_at=datetime.utcnow().isoformat(),
        )
        
        if delay_seconds > 0:
            await self.redis.zadd(
                self.scan_queue,
                {json.dumps(job.model_dump()): datetime.utcnow().timestamp() + delay_seconds}
            )
        else:
            await self.redis.lpush(self.scan_queue, json.dumps(job.model_dump()))
        
        return job_id
    
    async def dequeue(self, timeout_seconds: int = 5) -> QueueJob | None:
        result = await self.redis.brpop(self.scan_queue, timeout=timeout_seconds)
        if result:
            _, data = result
            return QueueJob.model_validate_json(data)
        return None
    
    async def get_job_status(self, job_id: str) -> dict | None:
        data = await self.redis.get(f"job:{job_id}:status")
        if data:
            return json.loads(data)
        return None
    
    async def update_job_status(
        self,
        job_id: str,
        stage: str,
        metadata: dict | None = None,
    ):
        status_data = {
            "stage": stage,
            "updated_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        await self.redis.set(
            f"job:{job_id}:status",
            json.dumps(status_data),
            ex=86400,  # 24 hour expiry
        )
    
    async def retry_job(self, job: QueueJob, max_retries: int = 3) -> bool:
        retry_count = await self.redis.incr(f"job:{job.job_id}:retries")
        
        if retry_count > max_retries:
            await self.redis.lpush(self.dlq, json.dumps(job.model_dump()))
            return False
        
        await self.enqueue(
            job.job_type,
            job.payload,
            delay_seconds=retry_count * 60,  # Exponential backoff
        )
        return True
```

### 6.2 R2 Client

**File:** `apps/worker/app/clients/r2.py`

```python
import boto3
from botocore.config import Config
from pathlib import Path
import hashlib

class R2Client:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        public_base_url: str,
    ):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = bucket
        self.public_base_url = public_base_url
    
    def _compute_checksum(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def upload_scan_artifact(
        self,
        scan_id: str,
        scanner_name: str,
        artifact_type: str,
        file_path: Path,
        content_type: str = "application/json",
    ) -> dict:
        key = f"scans/{scan_id}/{scanner_name}/{artifact_type}_{file_path.name}"
        
        checksum = self._compute_checksum(file_path)
        file_size = file_path.stat().st_size
        
        self.s3.upload_file(
            str(file_path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        
        return {
            "storage_uri": f"{self.public_base_url}/{key}",
            "checksum_sha256": checksum,
            "size_bytes": file_size,
            "content_type": content_type,
        }
    
    async def upload_raw_output(
        self,
        scan_id: str,
        scanner_name: str,
        output_data: dict,
        format: str = "json",
    ) -> str:
        import json
        
        key = f"scans/{scan_id}/{scanner_name}/raw_output.{format}"
        
        content = json.dumps(output_data, indent=2)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content.encode(),
            ContentType="application/json",
        )
        
        return f"{self.public_base_url}/{key}"
    
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    
    async def delete_scan_artifacts(self, scan_id: str):
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=f"scans/{scan_id}/")
        
        for page in pages:
            if "Contents" in page:
                keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})
```

### 6.3 Scan Orchestrator

**File:** `apps/worker/app/services/scan_orchestrator.py`

```python
from app.clients.queue import QueueClient, QueueJob
from app.clients.r2 import R2Client
from app.scanners.gitleaks import GitleaksAdapter
from app.scanners.trivy import TrivyAdapter
from app.scanners.osv import OsvAdapter
from app.normalizers.gitleaks import normalize_gitleaks_output
from app.normalizers.trivy import normalize_trivy_output
from app.normalizers.osv import normalize_osv_output
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

class ScanOrchestrator:
    def __init__(self, queue: QueueClient, r2: R2Client, api_base_url: str):
        self.queue = queue
        self.r2 = r2
        self.api_base_url = api_url
        self.scanners = {
            "gitleaks": GitleaksAdapter(),
            "trivy": TrivyAdapter(),
            "osv": OsvAdapter(),
        }
        self.normalizers = {
            "gitleaks": normalize_gitleaks_output,
            "trivy": normalize_trivy_output,
            "osv": normalize_osv_output,
        }
    
    async def process_scan_job(self, job: QueueJob) -> bool:
        job_id = job.job_id
        payload = job.payload
        scan_id = payload["scan_id"]
        repo_id = payload["repository_id"]
        scan_type = job.job_type
        
        try:
            await self.queue.update_job_status(job_id, "claimed")
            
            # Phase A: Target preparation
            await self.queue.update_job_status(job_id, "repo_preparing")
            repo_path = await self._prepare_repository(repo_id, payload.get("branch"))
            
            # Phase B: Scanner selection
            await self.queue.update_job_status(job_id, "scanners_running")
            scanner_results = await self._run_scanners(scan_id, repo_path, scan_type)
            
            # Phase C: Artifact storage
            await self.queue.update_job_status(job_id, "artifacts_uploading")
            await self._upload_artifacts(scan_id, scanner_results)
            
            # Phase D: Normalization
            await self.queue.update_job_status(job_id, "normalizing")
            normalized_findings = await self._normalize_results(scanner_results)
            
            # Phase E-F: Deduplication and persistence
            await self.queue.update_job_status(job_id, "persisting")
            await self._persist_findings(scan_id, normalized_findings)
            
            # Phase G: Notifications
            await self.queue.update_job_status(job_id, "notifications_sending")
            await self._trigger_notifications(scan_id, normalized_findings)
            
            await self.queue.update_job_status(job_id, "done")
            
            # Cleanup
            shutil.rmtree(repo_path, ignore_errors=True)
            
            return True
            
        except Exception as e:
            await self.queue.update_job_status(job_id, "failed", {"error": str(e)})
            await self.queue.retry_job(job)
            return False
    
    async def _prepare_repository(self, repo_id: str, branch: str | None) -> Path:
        # TODO: Clone repository using Git provider client
        # For now, create temp directory
        temp_dir = Path(tempfile.mkdtemp())
        return temp_dir
    
    async def _run_scanners(
        self,
        scan_id: str,
        repo_path: Path,
        scan_type: str,
    ) -> dict:
        results = {}
        
        for scanner_name, adapter in self.scanners.items():
            try:
                result = adapter.run(repo_path)
                results[scanner_name] = {
                    "success": result.success,
                    "raw_output": result.raw_output,
                    "artifact_paths": [str(p) for p in result.artifact_paths],
                }
            except Exception as e:
                results[scanner_name] = {
                    "success": False,
                    "error": str(e),
                    "raw_output": {},
                    "artifact_paths": [],
                }
        
        return results
    
    async def _upload_artifacts(self, scan_id: str, results: dict):
        for scanner_name, result in results.items():
            for artifact_path in result.get("artifact_paths", []):
                await self.r2.upload_scan_artifact(
                    scan_id=scan_id,
                    scanner_name=scanner_name,
                    artifact_type="raw",
                    file_path=Path(artifact_path),
                )
            
            # Upload raw output JSON
            if result.get("raw_output"):
                await self.r2.upload_raw_output(
                    scan_id=scan_id,
                    scanner_name=scanner_name,
                    output_data=result["raw_output"],
                )
    
    async def _normalize_results(self, results: dict) -> list[dict]:
        all_findings = []
        
        for scanner_name, result in results.items():
            if not result.get("success"):
                continue
            
            normalizer = self.normalizers.get(scanner_name)
            if normalizer:
                findings = normalizer(result["raw_output"])
                all_findings.extend(findings)
        
        return all_findings
    
    async def _persist_findings(self, scan_id: str, findings: list[dict]):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.api_base_url}/api/v1/scans/{scan_id}/findings",
                json={"findings": findings},
            )
    
    async def _trigger_notifications(self, scan_id: str, findings: list[dict]):
        # Check for critical findings
        critical_count = sum(1 for f in findings if f.get("severity") == "critical")
        new_secret_count = sum(1 for f in findings if f.get("category") == "secret")
        
        if critical_count > 0 or new_secret_count > 0:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.api_base_url}/api/v1/notifications/scan-alert",
                    json={
                        "scan_id": scan_id,
                        "critical_count": critical_count,
                        "new_secrets": new_secret_count,
                    },
                )
```

### 6.4 Gitleaks Normalizer

**File:** `apps/worker/app/normalizers/gitleaks.py`

```python
import hashlib
import json

def compute_secret_fingerprint(
    repo_id: str,
    secret_type: str,
    path: str,
    line: int,
) -> str:
    components = [
        secret_type.lower(),
        repo_id,
        path.lower(),
        str(line),
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()

def normalize_gitleaks_output(raw_output: dict) -> list[dict]:
    findings = []
    
    # Gitleaks outputs "results" array
    results = raw_output.get("results", [])
    
    for result in results:
        # Extract secret info
        secret_type = result.get("RuleID", "unknown")
        file_path = result.get("File", "")
        line_start = result.get("StartLine")
        line_end = result.get("EndLine", line_start)
        
        # Compute fingerprint
        fingerprint = compute_secret_fingerprint(
            repo_id="",  # Will be set by orchestrator
            secret_type=secret_type,
            path=file_path,
            line=line_start,
        )
        
        finding = {
            "category": "secret",
            "severity": _map_secret_severity(secret_type),
            "title": f"Exposed secret: {secret_type}",
            "description": result.get("Match", ""),
            "canonical_fingerprint": fingerprint,
            "primary_scanner": "gitleaks",
            "confidence_score": 0.95,
            "instance": {
                "path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "commit": result.get("Commit"),
                "author": result.get("Author"),
                "email": result.get("Email"),
                "date": result.get("Date"),
                "match": result.get("Match"),
            },
            "references": [
                {
                    "type": "documentation",
                    "value": f"https://github.com/gitleaks/gitleaks/blob/master/docs/rules/{secret_type.lower()}.md",
                }
            ],
        }
        findings.append(finding)
    
    return findings

def _map_secret_severity(secret_type: str) -> str:
    high_risk_types = [
        "aws_access_key",
        "aws_secret_key",
        "private_key",
        "ssh_key",
        "database_url",
        "api_key",
    ]
    
    if secret_type.lower() in high_risk_types:
        return "critical"
    return "high"
```

---

## 7. Phase 4 — Findings & Normalization

### 7.1 Finding Service

**File:** `apps/api/app/services/findings.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from uuid import UUID
from app.db.models import (
    Finding,
    FindingInstance,
    FindingReference,
    FindingEvent,
    Project,
    OrganizationMember,
)
from app.schemas.findings import (
    FindingCreate,
    FindingUpdate,
    FindingFilter,
)

class FindingService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        filters: FindingFilter,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        # Build base query with access check
        base_query = (
            select(Finding)
            .join(Project)
            .join(OrganizationMember)
            .where(
                Finding.project_id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )
        
        # Apply filters
        if filters.severity:
            base_query = base_query.where(Finding.severity == filters.severity)
        if filters.category:
            base_query = base_query.where(Finding.category == filters.category)
        if filters.status:
            base_query = base_query.where(Finding.status == filters.status)
        if filters.scanner:
            base_query = base_query.where(Finding.primary_scanner == filters.scanner)
        if filters.repository_id:
            base_query = base_query.where(Finding.repository_id == filters.repository_id)
        if filters.search:
            search_term = f"%{filters.search}%"
            base_query = base_query.where(
                or_(
                    Finding.title.ilike(search_term),
                    Finding.description.ilike(search_term),
                )
            )
        
        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Get paginated results
        result = await self.db.execute(
            base_query
            .options(selectinload(Finding.instances))
            .order_by(Finding.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        findings = result.scalars().all()
        
        return findings, total
    
    async def get_by_id(
        self,
        finding_id: UUID,
        user_id: UUID,
    ) -> Finding | None:
        result = await self.db.execute(
            select(Finding)
            .join(Project)
            .join(OrganizationMember)
            .options(
                selectinload(Finding.instances),
                selectinload(Finding.references),
                selectinload(Finding.events),
            )
            .where(
                Finding.id == finding_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def upsert_from_scan(
        self,
        scan_id: str,
        repository_id: UUID,
        project_id: UUID,
        normalized_findings: list[dict],
    ) -> tuple[int, int]:
        """Upsert findings from a scan, return (new_count, updated_count)."""
        new_count = 0
        updated_count = 0
        
        for finding_data in normalized_findings:
            fingerprint = finding_data["canonical_fingerprint"]
            
            # Check if finding exists
            existing = await self.db.execute(
                select(Finding).where(
                    and_(
                        Finding.repository_id == repository_id,
                        Finding.canonical_fingerprint == fingerprint,
                    )
                )
            )
            finding = existing.scalar_one_or_none()
            
            if finding:
                # Update existing finding
                finding.last_seen_at = datetime.utcnow()
                if finding.severity != finding_data.get("severity"):
                    finding.severity = finding_data["severity"]
                
                updated_count += 1
            else:
                # Create new finding
                finding = Finding(
                    project_id=project_id,
                    repository_id=repository_id,
                    category=finding_data["category"],
                    severity=finding_data["severity"],
                    status="open",
                    title=finding_data["title"],
                    description=finding_data.get("description"),
                    canonical_fingerprint=fingerprint,
                    primary_scanner=finding_data.get("primary_scanner"),
                    confidence_score=finding_data.get("confidence_score"),
                    fixed_version=finding_data.get("fixed_version"),
                    metadata_json=finding_data.get("metadata"),
                )
                self.db.add(finding)
                new_count += 1
            
            await self.db.flush()
            
            # Create finding instance
            instance_data = finding_data.get("instance", {})
            instance = FindingInstance(
                finding_id=finding.id,
                scan_id=scan_id,
                path=instance_data.get("path"),
                line_start=instance_data.get("line_start"),
                line_end=instance_data.get("line_end"),
                package_name=instance_data.get("package_name"),
                installed_version=instance_data.get("installed_version"),
                fixed_version=instance_data.get("fixed_version"),
                evidence_json=instance_data,
            )
            self.db.add(instance)
            
            # Create references
            for ref in finding_data.get("references", []):
                reference = FindingReference(
                    finding_id=finding.id,
                    reference_type=ref.get("type"),
                    reference_value=ref.get("value"),
                    url=ref.get("url"),
                )
                self.db.add(reference)
        
        await self.db.commit()
        return new_count, updated_count
    
    async def suppress(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str,
        rule_id: UUID | None = None,
    ) -> Finding | None:
        finding = await self.db.get(Finding, finding_id)
        if not finding:
            return None
        
        finding.status = "suppressed"
        
        # Create event
        event = FindingEvent(
            finding_id=finding_id,
            event_type="suppressed",
            actor_user_id=user_id,
            reason=reason,
        )
        self.db.add(event)
        
        await self.db.commit()
        await self.db.refresh(finding)
        return finding
    
    async def resolve(
        self,
        finding_id: UUID,
        user_id: UUID,
        fixed_version: str | None = None,
        reason: str | None = None,
    ) -> Finding | None:
        finding = await self.db.get(Finding, finding_id)
        if not finding:
            return None
        
        finding.status = "fixed"
        if fixed_version:
            finding.fixed_version = fixed_version
        
        # Create event
        event = FindingEvent(
            finding_id=finding_id,
            event_type="fixed",
            actor_user_id=user_id,
            reason=reason,
        )
        self.db.add(event)
        
        await self.db.commit()
        await self.db.refresh(finding)
        return finding
```

---

## 8. Phase 5 — UI & Dashboard

### 8.1 Page Structure

```
apps/web/app/
├── (auth)/
│   ├── login/
│   │   └── page.tsx
│   └── callback/
│       └── page.tsx
├── (dashboard)/
│   ├── layout.tsx                    # Dashboard shell with sidebar
│   ├── page.tsx                      # Redirect to first org
│   ├── organizations/
│   │   ├── page.tsx                  # Organization list
│   │   ├── [org_id]/
│   │   │   ├── page.tsx              # Org dashboard
│   │   │   ├── projects/
│   │   │   │   ├── page.tsx          # Project list
│   │   │   │   └── [project_id]/
│   │   │   │       ├── page.tsx      # Project overview
│   │   │   │       ├── findings/
│   │   │   │       │   ├── page.tsx  # Findings list
│   │   │   │       │   └── [finding_id]/
│   │   │   │       │       └── page.tsx  # Finding detail
│   │   │   │       ├── scans/
│   │   │   │       │   ├── page.tsx  # Scan history
│   │   │   │       │   └── [scan_id]/
│   │   │   │       │       └── page.tsx  # Scan detail
│   │   │   │       ├── repositories/
│   │   │   │       │   ├── page.tsx  # Repository list
│   │   │   │       │   └── connect/
│   │   │   │       │       └── page.tsx  # Connect repo
│   │   │   │       ├── reports/
│   │   │   │       │   └── page.tsx  # Exports & reports
│   │   │   │       └── settings/
│   │   │   │           ├── page.tsx  # Project settings
│   │   │   │           └── members/
│   │   │   │               └── page.tsx
│   │   │   ├── audit/
│   │   │   │   └── page.tsx          # Audit logs
│   │   │   ├── notifications/
│   │   │   │   └── page.tsx
│   │   │   └── settings/
│   │   │       ├── page.tsx          # Org settings
│   │   │       └── members/
│   │   │           └── page.tsx
│   │   └── new/
│   │       ├── organization/
│   │       │   └── page.tsx
│   │       └── project/
│   │           └── page.tsx
├── api/
│   └── [...proxy]/route.ts          # Proxy to backend
└── layout.tsx
```

### 8.2 Dashboard Layout

**File:** `apps/web/app/(dashboard)/layout.tsx`

```tsx
import { redirect } from "next/navigation";
import { getUser } from "@/lib/auth";
import { Sidebar } from "@/components/dashboard/sidebar";
import { Header } from "@/components/dashboard/header";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getUser();
  
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <Sidebar user={user} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header user={user} />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
```

### 8.3 Project Overview Page

**File:** `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/page.tsx`

```tsx
import { getProject } from "@/lib/api";
import { SecurityScorecard } from "@/components/project/security-scorecard";
import { RecentScans } from "@/components/project/recent-scans";
import { OpenFindings } from "@/components/project/open-findings";
import { QuickActions } from "@/components/project/quick-actions";

interface Props {
  params: Promise<{ org_id: string; project_id: string }>;
}

export default async function ProjectOverviewPage({ params }: Props) {
  const { org_id, project_id } = await params;
  const project = await getProject(org_id, project_id);
  const stats = await getProjectStats(project_id);
  const recentScans = await getRecentScans(project_id);
  const criticalFindings = await getOpenFindings(project_id, { severity: "critical", limit: 5 });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-gray-400">{project.description}</p>
        </div>
        <QuickActions projectId={project_id} />
      </div>

      <SecurityScorecard stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentScans scans={recentScans} />
        <OpenFindings findings={criticalFindings} />
      </div>
    </div>
  );
}
```

### 8.4 Findings List Page

**File:** `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/findings/page.tsx`

```tsx
import { getFindings } from "@/lib/api";
import { FindingsFilters } from "@/components/findings/findings-filters";
import { FindingsTable } from "@/components/findings/findings-table";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { StatusBadge } from "@/components/ui/status-badge";

interface Props {
  params: Promise<{ org_id: string; project_id: string }>;
  searchParams: Promise<{
    severity?: string;
    category?: string;
    status?: string;
    page?: string;
  }>;
}

export default async function FindingsPage({ params, searchParams }: Props) {
  const { org_id, project_id } = await params;
  const filters = await searchParams;
  
  const page = parseInt(filters.page || "1");
  const findings = await getFindings(project_id, {
    ...filters,
    page,
    limit: 50,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Findings</h1>
        <p className="text-gray-400">
          {findings.total} total findings
        </p>
      </div>

      <FindingsFilters
        projectId={project_id}
        currentFilters={filters}
        counts={findings.counts}
      />

      <FindingsTable
        findings={findings.items}
        projectId={project_id}
      />

      {findings.pages > 1 && (
        <Pagination
          currentPage={page}
          totalPages={findings.pages}
          baseUrl={`/organizations/${org_id}/projects/${project_id}/findings`}
        />
      )}
    </div>
  );
}
```

---

## 9. Phase 6 — Exports, Notifications, Audit

### 9.1 Export Service

**File:** `apps/api/app/services/exports.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID, UUID
import csv
import json
from io import StringIO, BytesIO
from datetime import datetime
from app.db.models import Export, Finding, ScanArtifact
from app.clients.r2 import R2Client

class ExportService:
    def __init__(self, db: AsyncSession, r2_client: R2Client):
        self.db = db
        self.r2 = r2_client
    
    async def create_export(
        self,
        project_id: UUID,
        user_id: UUID,
        export_type: str,
        format: str,
        filters: dict | None = None,
    ) -> Export:
        export = Export(
            project_id=project_id,
            requested_by_user_id=user_id,
            export_type=export_type,
            format=format,
            filter_criteria_json=filters,
            status="pending",
        )
        self.db.add(export)
        await self.db.commit()
        await self.db.refresh(export)
        
        # Trigger async generation
        await self._generate_export_async(export.id)
        
        return export
    
    async def _generate_export_async(self, export_id: UUID):
        export = await self.db.get(Export, export_id)
        if not export:
            return
        
        try:
            # Fetch data based on export type
            if export.export_type == "findings":
                data = await self._fetch_findings_data(export)
            elif export.export_type == "scan_report":
                data = await self._fetch_scan_report(export)
            elif export.export_type == "project_summary":
                data = await self._fetch_project_summary(export)
            
            # Generate file
            if export.format == "json":
                content = json.dumps(data, indent=2)
                content_type = "application/json"
            elif export.format == "csv":
                content = self._dict_to_csv(data)
                content_type = "text/csv"
            else:
                raise ValueError(f"Unsupported format: {export.format}")
            
            # Upload to R2
            file_key = f"exports/{export.project_id}/{export.id}.{export.format}"
            self.r2.s3.put_object(
                Bucket=self.r2.bucket,
                Key=file_key,
                Body=content.encode(),
                ContentType=content_type,
            )
            
            # Update export record
            export.status = "completed"
            export.storage_uri = f"{self.r2.public_base_url}/{file_key}"
            export.completed_at = datetime.utcnow()
            export.row_count = len(data) if isinstance(data, list) else 1
            
            await self.db.commit()
            
        except Exception as e:
            export.status = "failed"
            export.error_message = str(e)
            await self.db.commit()
    
    async def list_exports(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Export], int]:
        result = await self.db.execute(
            select(Export)
            .where(Export.project_id == project_id)
            .order_by(Export.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        exports = list(result.scalars().all())
        
        count_result = await self.db.execute(
            select(func.count(Export.id))
            .where(Export.project_id == project_id)
        )
        total = count_result.scalar_one()
        
        return exports, total
    
    def _dict_to_csv(self, data: list[dict]) -> str:
        if not data:
            return ""
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
```

### 9.2 Audit Middleware

**File:** `apps/api/app/middleware/audit.py`

```python
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.session import AsyncSessionLocal
from app.db.models import AuditLog
import json
from datetime import datetime

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

AUDITED_PATHS = [
    "/api/v1/organizations",
    "/api/v1/projects",
    "/api/v1/repositories",
    "/api/v1/scans",
    "/api/v1/findings",
    "/api/v1/exports",
]

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in AUDITED_METHODS:
            return await call_next(request)
        
        should_audit = any(
            request.url.path.startswith(path) for path in AUDITED_PATHS
        )
        
        if not should_audit:
            return await call_next(request)
        
        response = await call_next(request)
        
        # Log after response is generated
        if response.status_code < 400:  # Only log successful actions
            await self._log_action(request, response)
        
        return response
    
    async def _log_action(self, request: Request, response: Response):
        # Extract user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "org_id", None)
        
        # Determine action from path
        action = self._determine_action(request)
        target_type, target_id = self._parse_target(request.url.path)
        
        # Extract request metadata
        body = None
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.body()
            except Exception:
                pass
        
        async with AsyncSessionLocal() as db:
            audit_log = AuditLog(
                organization_id=org_id,
                actor_user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata_json={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "status_code": response.status_code,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.add(audit_log)
            await db.commit()
    
    def _determine_action(self, request: Request) -> str:
        method = request.method
        path = request.url.path
        
        if method == "POST":
            return f"create_{self._resource_name(path)}"
        elif method == "PUT" or method == "PATCH":
            return f"update_{self._resource_name(path)}"
        elif method == "DELETE":
            return f"delete_{self._resource_name(path)}"
        
        return f"{method.lower()}_{self._resource_name(path)}"
    
    def _resource_name(self, path: str) -> str:
        segments = [s for s in path.split("/") if s and s != "api" and s != "v1"]
        return segments[0] if segments else "unknown"
    
    def _parse_target(self, path: str) -> tuple[str, str | None]:
        segments = [s for s in path.split("/") if s and s != "api" and s != "v1"]
        
        if not segments:
            return "unknown", None
        
        resource = segments[0]
        if len(segments) > 1:
            # Check if next segment is UUID
            target_id = segments[1]
            return resource, target_id
        
        return resource, None
```

---

## 10. Phase 7 — Infrastructure & Hardening

### 10.1 Render Blueprint

**File:** `infra/render/render.yaml`

```yaml
services:
  - name: api
    type: web
    region: oregon
    plan: starter
    env: python311
    buildCommand: cd apps/api && pip install -e .
    startCommand: cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: NEON_AUTH_ISSUER
        sync: false
      - key: NEON_AUTH_JWKS_URL
        sync: false
      - key: UPSTASH_REDIS_REST_URL
        sync: false
      - key: UPSTASH_REDIS_REST_TOKEN
        sync: false
      - key: R2_ENDPOINT
        sync: false
      - key: R2_BUCKET
        sync: false
      - key: R2_ACCESS_KEY_ID
        sync: false
      - key: R2_SECRET_ACCESS_KEY
        sync: false

  - name: worker
    type: background worker
    region: oregon
    plan: starter
    env: python311
    buildCommand: cd apps/worker && pip install -e .
    startCommand: cd apps/worker && python -m app.worker.main
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: UPSTASH_REDIS_REST_URL
        sync: false
      - key: UPSTASH_REDIS_REST_TOKEN
        sync: false
      - key: R2_ENDPOINT
        sync: false
      - key: R2_BUCKET
        sync: false
      - key: R2_ACCESS_KEY_ID
        sync: false
      - key: R2_SECRET_ACCESS_KEY
        sync: false

cron:
  - name: scan-scheduler
    schedule: "0 2 * * *"  # 2 AM daily
    command: cd apps/worker && python -m app.crons.scheduler
    regions: [oregon]

  - name: retention-cleanup
    schedule: "0 3 * * 0"  # 3 AM Sunday
    command: cd apps/worker && python -m app.crons.retention
    regions: [oregon]
```

### 10.2 Vercel Config

**File:** `apps/web/vercel.json`

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "regions": ["iad1"],
  "env": {
    "NEXT_PUBLIC_API_BASE_URL": "@api_base_url",
    "NEXT_PUBLIC_APP_URL": "@app_url"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-DNS-Prefetch-Control",
          "value": "on"
        },
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=63072000; includeSubDomains; preload"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "Referrer-Policy",
          "value": "strict-origin-when-cross-origin"
        },
        {
          "key": "Permissions-Policy",
          "value": "camera=(), microphone=(), geolocation=()"
        }
      ]
    }
  ]
}
```

### 10.3 Global Exception Handler

**File:** `apps/api/app/core/exceptions.py`

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
import structlog

logger = structlog.get_logger()

def setup_exception_handlers(app: FastAPI):
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": exc.errors(),
            },
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(
        request: Request,
        exc: SQLAlchemyError,
    ):
        logger.error("database_error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Database error occurred"},
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_exception_handler(
        request: Request,
        exc: ValidationError,
    ):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": exc.errors(),
            },
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        logger.error(
            "unhandled_exception",
            error=str(exc),
            type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
        )
        
        # In development, include more details
        if settings.APP_ENV == "development":
            import traceback
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
            )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
```

---

## 11. File Manifest

### Backend Files to Create

| File | Phase |
|------|-------|
| `apps/api/alembic/versions/0001_identity_and_access.py` | 0.5 |
| `apps/api/alembic/versions/0002_projects_and_repositories.py` | 0.5 |
| `apps/api/alembic/versions/0003_scanning_core.py` | 0.5 |
| `apps/api/alembic/versions/0004_findings_core.py` | 0.5 |
| `apps/api/alembic/versions/0005_governance.py` | 0.5 |
| `apps/api/alembic/versions/0006_operational_support.py` | 0.5 |
| `apps/api/app/core/config.py` (update) | 1 |
| `apps/api/app/core/security.py` | 1 |
| `apps/api/app/core/exceptions.py` | 1 |
| `apps/api/app/middleware/auth.py` | 1 |
| `apps/api/app/middleware/rbac.py` | 1 |
| `apps/api/app/middleware/audit.py` | 1 |
| `apps/api/app/schemas/__init__.py` | 1 |
| `apps/api/app/schemas/auth.py` | 1 |
| `apps/api/app/schemas/common.py` | 1 |
| `apps/api/app/schemas/organizations.py` | 1 |
| `apps/api/app/schemas/memberships.py` | 1 |
| `apps/api/app/schemas/projects.py` | 1 |
| `apps/api/app/schemas/repositories.py` | 1 |
| `apps/api/app/schemas/scans.py` | 1 |
| `apps/api/app/schemas/findings.py` | 1 |
| `apps/api/app/schemas/exports.py` | 1 |
| `apps/api/app/schemas/notifications.py` | 1 |
| `apps/api/app/services/__init__.py` | 1 |
| `apps/api/app/services/auth.py` | 1 |
| `apps/api/app/services/users.py` | 1 |
| `apps/api/app/services/organizations.py` | 1 |
| `apps/api/app/services/memberships.py` | 1 |
| `apps/api/app/services/projects.py` | 2 |
| `apps/api/app/services/repositories.py` | 2 |
| `apps/api/app/services/scans.py` | 3 |
| `apps/api/app/services/findings.py` | 4 |
| `apps/api/app/services/exports.py` | 6 |
| `apps/api/app/services/notifications.py` | 6 |
| `apps/api/app/services/audit.py` | 6 |
| `apps/api/app/api/v1/routes/auth.py` | 1 |
| `apps/api/app/api/v1/routes/organizations.py` | 1 |
| `apps/api/app/api/v1/routes/memberships.py` | 1 |
| `apps/api/app/api/v1/routes/projects.py` | 2 |
| `apps/api/app/api/v1/routes/repositories.py` | 2 |
| `apps/api/app/api/v1/routes/scans.py` | 3 |
| `apps/api/app/api/v1/routes/findings.py` | 4 |
| `apps/api/app/api/v1/routes/exports.py` | 6 |
| `apps/api/app/api/v1/routes/notifications.py` | 6 |
| `apps/api/app/api/v1/routes/audit.py` | 6 |

### Worker Files to Create

| File | Phase |
|------|-------|
| `apps/worker/app/clients/__init__.py` | 3 |
| `apps/worker/app/clients/queue.py` | 3 |
| `apps/worker/app/clients/r2.py` | 3 |
| `apps/worker/app/clients/git.py` | 3 |
| `apps/worker/app/services/__init__.py` | 3 |
| `apps/worker/app/services/scan_orchestrator.py` | 3 |
| `apps/worker/app/services/notification_service.py` | 6 |
| `apps/worker/app/normalizers/__init__.py` | 4 |
| `apps/worker/app/normalizers/gitleaks.py` | 4 |
| `apps/worker/app/normalizers/trivy.py` | 4 |
| `apps/worker/app/normalizers/osv.py` | 4 |
| `apps/worker/app/crons/__init__.py` | 5 |
| `apps/worker/app/crons/scheduler.py` | 5 |
| `apps/worker/app/crons/retention.py` | 5 |

### Frontend Files to Create

| File | Phase |
|------|-------|
| `apps/web/app/(auth)/login/page.tsx` | 1 |
| `apps/web/app/(auth)/callback/page.tsx` | 1 |
| `apps/web/app/(dashboard)/layout.tsx` | 5 |
| `apps/web/app/(dashboard)/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/findings/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/findings/[finding_id]/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/scans/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/repositories/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/repositories/connect/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/reports/page.tsx` | 6 |
| `apps/web/app/(dashboard)/organizations/[org_id]/projects/[project_id]/settings/page.tsx` | 5 |
| `apps/web/app/(dashboard)/organizations/[org_id]/audit/page.tsx` | 6 |
| `apps/web/app/(dashboard)/organizations/[org_id]/notifications/page.tsx` | 6 |
| `apps/web/app/(dashboard)/organizations/[org_id]/settings/page.tsx` | 5 |
| `apps/web/components/dashboard/sidebar.tsx` | 5 |
| `apps/web/components/dashboard/header.tsx` | 5 |
| `apps/web/components/project/security-scorecard.tsx` | 7 |
| `apps/web/components/project/recent-scans.tsx` | 5 |
| `apps/web/components/project/open-findings.tsx` | 5 |
| `apps/web/components/project/quick-actions.tsx` | 5 |
| `apps/web/components/findings/findings-filters.tsx` | 5 |
| `apps/web/components/findings/findings-table.tsx` | 5 |
| `apps/web/components/ui/severity-badge.tsx` | 5 |
| `apps/web/components/ui/status-badge.tsx` | 5 |
| `apps/web/lib/auth.ts` | 1 |
| `apps/web/lib/api.ts` (update) | 5 |

### Infrastructure Files

| File | Phase |
|------|-------|
| `infra/render/render.yaml` | 7 |
| `apps/web/vercel.json` | 7 |
| `apps/api/Dockerfile` | 7 |
| `apps/worker/Dockerfile` | 7 |

---

## 12. Implementation Timeline

```
Week 1:
├── Create 6 Alembic migration files
├── Update config.py with all env vars
├── Implement auth middleware
├── Implement RBAC middleware
└── Create organization routes & service

Week 2:
├── Create membership routes & service
├── Create project routes & service
├── Create repository routes & service
└── Create auth callback page

Week 3:
├── Implement queue client
├── Implement R2 client
├── Create scan routes & service
├── Create scan orchestrator
└── Implement scan creation endpoint

Week 4:
├── Create trivy adapter
├── Create gitleaks adapter
├── Create osv adapter
└── Implement raw artifact upload

Week 5:
├── Create normalizers for all scanners
├── Implement findings service
├── Create findings routes
├── Create findings list UI
└── Create findings detail UI

Week 6:
├── Create dashboard layout
├── Create project overview page
├── Create scan history page
└── Create scan detail page

Week 7:
├── Create findings filters
├── Create repository list page
├── Create repository connect page
└── Create export service

Week 8:
├── Create audit middleware
├── Create notification service
├── Create notifications UI
└── Create audit logs UI

Week 9:
├── Create Render blueprint
├── Create Vercel config
├── Implement global exception handler
├── Create security scorecard
└── Performance tuning
```

---

## 13. Dependencies

```
# apps/api/pyproject.toml additions
dependencies = [
    ...
    "python-jose[cryptography]>=3.3.0",  # JWT validation
    "httpx>=0.27.0",  # Already present
    "structlog>=24.0.0",  # Structured logging
    "boto3>=1.34.0",  # S3/R2 client
]

# apps/worker/pyproject.toml additions
dependencies = [
    ...
    "upstash-redis>=1.0.0",  # Queue client
    "boto3>=1.34.0",  # R2 client
    "structlog>=24.0.0",  # Logging
]

# apps/web/package.json additions
dependencies = [
    ...
    "@tanstack/react-query>=5.0.0",
    "lucide-react>=0.400.0",
    "tailwindcss>=4.0.0",
    "clsx>=2.0.0",
]
```
