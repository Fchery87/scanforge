"""Add versioned execution, provenance, coverage, and branch observation contracts.

Revision ID: 0024_evidence_and_execution_contracts
Revises: 0023_org_invitations_and_owner_transfer
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_evidence_and_execution_contracts"
down_revision = "0023_org_invitations_and_owner_transfer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False, server_default="connected"),
    )
    op.create_index("ix_repositories_external_repo_id", "repositories", ["external_repo_id"])

    op.create_table(
        "repository_branch_generations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_ref_name", sa.String(length=255), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=False),
        sa.Column("generation_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("head_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("ancestry_status", sa.String(length=32), nullable=False, server_default="verified_initial"),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "repository_id",
            "full_ref_name",
            "generation_number",
            name="uq_repo_branch_generation",
        ),
    )
    op.create_index(
        "ix_repository_branch_generations_repository_id",
        "repository_branch_generations",
        ["repository_id"],
    )

    op.add_column(
        "scans",
        sa.Column("contract_version", sa.String(length=32), nullable=False, server_default="2026-10-beta.v1"),
    )
    op.add_column("scans", sa.Column("full_ref_name", sa.String(length=255), nullable=True))
    op.add_column(
        "scans",
        sa.Column("branch_generation_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "scans",
        sa.Column("ancestry_status", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column("scans", sa.Column("expected_scanners_json", postgresql.JSONB(), nullable=True))
    op.add_column(
        "scans",
        sa.Column("coverage_completeness", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "scans",
        sa.Column("closure_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "scans",
        sa.Column("cleanup_state", sa.String(length=32), nullable=False, server_default="not_required"),
    )
    op.add_column(
        "scans",
        sa.Column("dispatch_state", sa.String(length=32), nullable=False, server_default="awaiting_dispatch"),
    )
    op.add_column(
        "scans",
        sa.Column(
            "superseded_by_scan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("scans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("scans", sa.Column("supersession_reason", sa.String(length=255), nullable=True))
    op.add_column("scans", sa.Column("worker_principal_id", sa.String(length=128), nullable=True))
    op.add_column("scans", sa.Column("worker_incarnation_id", sa.String(length=128), nullable=True))

    op.create_table(
        "scan_dispatch_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("scan_type", sa.String(length=50), nullable=False, server_default="full"),
        sa.Column("job_type", sa.String(length=64), nullable=False, server_default="scan.repo.full"),
        sa.Column("business_identity_key", sa.String(length=255), nullable=True),
        sa.Column("request_idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("full_ref_name", sa.String(length=255), nullable=True),
        sa.Column("branch_generation_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="awaiting_dispatch"),
        sa.Column("queue_job_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "superseded_by_scan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("scans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("supersession_reason", sa.String(length=255), nullable=True),
        sa.Column("webhook_delivery_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "repository_id",
            "business_identity_key",
            name="uq_dispatch_repo_business_identity",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "repository_id",
            "request_idempotency_key",
            name="uq_dispatch_org_repo_idempotency_key",
        ),
    )
    op.create_index("ix_scan_dispatch_obligations_organization_id", "scan_dispatch_obligations", ["organization_id"])
    op.create_index("ix_scan_dispatch_obligations_project_id", "scan_dispatch_obligations", ["project_id"])
    op.create_index("ix_scan_dispatch_obligations_repository_id", "scan_dispatch_obligations", ["repository_id"])
    op.create_index("ix_scan_dispatch_obligations_scan_id", "scan_dispatch_obligations", ["scan_id"])
    op.create_index(
        "ix_scan_dispatch_obligations_business_identity_key",
        "scan_dispatch_obligations",
        ["business_identity_key"],
    )
    op.create_index(
        "ix_scan_dispatch_obligations_request_idempotency_key",
        "scan_dispatch_obligations",
        ["request_idempotency_key"],
    )
    op.create_index("ix_scan_dispatch_obligations_status", "scan_dispatch_obligations", ["status"])
    op.create_index(
        "ix_scan_dispatch_obligations_webhook_delivery_id",
        "scan_dispatch_obligations",
        ["webhook_delivery_id"],
    )

    op.add_column("scanner_runs", sa.Column("attempt_id", sa.String(length=64), nullable=True))
    op.add_column(
        "scanner_runs",
        sa.Column("execution_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scanner_runs",
        sa.Column("outcome_status", sa.String(length=32), nullable=False, server_default="completed"),
    )
    op.add_column("scanner_runs", sa.Column("parser_version", sa.String(length=64), nullable=True))
    op.add_column("scanner_runs", sa.Column("rules_digest", sa.String(length=128), nullable=True))
    op.add_column("scanner_runs", sa.Column("db_digest", sa.String(length=128), nullable=True))
    op.add_column("scanner_runs", sa.Column("db_published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "scanner_runs",
        sa.Column("db_freshness_state", sa.String(length=32), nullable=False, server_default="unverified"),
    )
    op.add_column("scanner_runs", sa.Column("image_digest", sa.String(length=128), nullable=True))
    op.add_column(
        "scanner_runs",
        sa.Column("artifact_availability", sa.String(length=32), nullable=False, server_default="unavailable"),
    )
    op.add_column(
        "scanner_runs",
        sa.Column("closure_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column(
        "scan_completion_receipts",
        sa.Column("contract_version", sa.String(length=32), nullable=False, server_default="2026-10-beta.v1"),
    )
    op.add_column(
        "scan_completion_receipts",
        sa.Column("worker_principal_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "scan_completion_receipts",
        sa.Column("worker_incarnation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "scan_completion_receipts",
        sa.Column("coverage_completeness", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "scan_completion_receipts",
        sa.Column("closure_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "scan_completion_receipts",
        sa.Column("artifact_availability", sa.String(length=32), nullable=False, server_default="unavailable"),
    )

    op.add_column("scan_artifacts", sa.Column("organization_id", sa.String(length=64), nullable=True))
    op.add_column("scan_artifacts", sa.Column("attempt_id", sa.String(length=64), nullable=True))
    op.add_column("scan_artifacts", sa.Column("scanner_name", sa.String(length=50), nullable=True))
    op.add_column("scan_artifacts", sa.Column("staging_uri", sa.String(length=2048), nullable=True))
    op.add_column(
        "scan_artifacts",
        sa.Column("verification_state", sa.String(length=32), nullable=False, server_default="staged"),
    )
    op.add_column("scan_artifacts", sa.Column("redaction_policy_version", sa.String(length=32), nullable=True))
    op.add_column("scan_artifacts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scan_artifacts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scan_artifacts", sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_scan_artifacts_organization_id", "scan_artifacts", ["organization_id"])

    op.add_column(
        "findings",
        sa.Column("fingerprint_version", sa.String(length=32), nullable=False, server_default="fp.v2"),
    )
    op.add_column(
        "findings",
        sa.Column("human_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "findings",
        sa.Column("evidence_trust_level", sa.String(length=32), nullable=False, server_default="verified"),
    )
    op.add_column(
        "findings",
        sa.Column(
            "duplicate_of_finding_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("findings", sa.Column("risk_acceptance_reason", sa.Text(), nullable=True))
    op.add_column("findings", sa.Column("risk_acceptance_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("findings", sa.Column("false_positive_reason", sa.Text(), nullable=True))
    op.add_column("findings", sa.Column("manual_reopen_checkpoint_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("findings", sa.Column("advisory_id", sa.String(length=128), nullable=True))
    op.add_column("findings", sa.Column("package_ecosystem", sa.String(length=64), nullable=True))
    op.add_column("findings", sa.Column("package_name", sa.String(length=255), nullable=True))
    op.create_index("ix_findings_duplicate_of_finding_id", "findings", ["duplicate_of_finding_id"])
    op.create_index("ix_findings_advisory_id", "findings", ["advisory_id"])
    op.create_index("ix_findings_package_name", "findings", ["package_name"])

    op.add_column("finding_events", sa.Column("actor_worker_principal_id", sa.String(length=128), nullable=True))
    op.add_column("finding_events", sa.Column("attempt_id", sa.String(length=64), nullable=True))
    op.add_column("finding_events", sa.Column("execution_revision", sa.Integer(), nullable=True))

    op.create_table(
        "finding_branch_observations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_ref_name", sa.String(length=255), nullable=False),
        sa.Column("branch_generation_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("observed_state", sa.String(length=32), nullable=False),
        sa.Column("consecutive_comparable_absences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_absence_commits_json", postgresql.JSONB(), nullable=True),
        sa.Column("scanner_name", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "finding_id",
            "full_ref_name",
            "branch_generation_number",
            "scan_id",
            name="uq_finding_branch_obs_scan",
        ),
    )
    op.create_index("ix_finding_branch_observations_finding_id", "finding_branch_observations", ["finding_id"])
    op.create_index("ix_finding_branch_observations_repository_id", "finding_branch_observations", ["repository_id"])
    op.create_index("ix_finding_branch_observations_scan_id", "finding_branch_observations", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_finding_branch_observations_scan_id", table_name="finding_branch_observations")
    op.drop_index("ix_finding_branch_observations_repository_id", table_name="finding_branch_observations")
    op.drop_index("ix_finding_branch_observations_finding_id", table_name="finding_branch_observations")
    op.drop_table("finding_branch_observations")

    op.drop_column("finding_events", "execution_revision")
    op.drop_column("finding_events", "attempt_id")
    op.drop_column("finding_events", "actor_worker_principal_id")

    op.drop_index("ix_findings_package_name", table_name="findings")
    op.drop_index("ix_findings_advisory_id", table_name="findings")
    op.drop_index("ix_findings_duplicate_of_finding_id", table_name="findings")
    op.drop_column("findings", "package_name")
    op.drop_column("findings", "package_ecosystem")
    op.drop_column("findings", "advisory_id")
    op.drop_column("findings", "manual_reopen_checkpoint_at")
    op.drop_column("findings", "false_positive_reason")
    op.drop_column("findings", "risk_acceptance_expires_at")
    op.drop_column("findings", "risk_acceptance_reason")
    op.drop_column("findings", "duplicate_of_finding_id")
    op.drop_column("findings", "evidence_trust_level")
    op.drop_column("findings", "human_revision")
    op.drop_column("findings", "fingerprint_version")

    op.drop_index("ix_scan_artifacts_organization_id", table_name="scan_artifacts")
    op.drop_column("scan_artifacts", "erased_at")
    op.drop_column("scan_artifacts", "expires_at")
    op.drop_column("scan_artifacts", "verified_at")
    op.drop_column("scan_artifacts", "redaction_policy_version")
    op.drop_column("scan_artifacts", "verification_state")
    op.drop_column("scan_artifacts", "staging_uri")
    op.drop_column("scan_artifacts", "scanner_name")
    op.drop_column("scan_artifacts", "attempt_id")
    op.drop_column("scan_artifacts", "organization_id")

    op.drop_column("scan_completion_receipts", "artifact_availability")
    op.drop_column("scan_completion_receipts", "closure_eligible")
    op.drop_column("scan_completion_receipts", "coverage_completeness")
    op.drop_column("scan_completion_receipts", "worker_incarnation_id")
    op.drop_column("scan_completion_receipts", "worker_principal_id")
    op.drop_column("scan_completion_receipts", "contract_version")

    op.drop_column("scanner_runs", "closure_eligible")
    op.drop_column("scanner_runs", "artifact_availability")
    op.drop_column("scanner_runs", "image_digest")
    op.drop_column("scanner_runs", "db_freshness_state")
    op.drop_column("scanner_runs", "db_published_at")
    op.drop_column("scanner_runs", "db_digest")
    op.drop_column("scanner_runs", "rules_digest")
    op.drop_column("scanner_runs", "parser_version")
    op.drop_column("scanner_runs", "outcome_status")
    op.drop_column("scanner_runs", "execution_revision")
    op.drop_column("scanner_runs", "attempt_id")

    op.drop_index("ix_scan_dispatch_obligations_webhook_delivery_id", table_name="scan_dispatch_obligations")
    op.drop_index("ix_scan_dispatch_obligations_status", table_name="scan_dispatch_obligations")
    op.drop_index(
        "ix_scan_dispatch_obligations_request_idempotency_key",
        table_name="scan_dispatch_obligations",
    )
    op.drop_index(
        "ix_scan_dispatch_obligations_business_identity_key",
        table_name="scan_dispatch_obligations",
    )
    op.drop_index("ix_scan_dispatch_obligations_scan_id", table_name="scan_dispatch_obligations")
    op.drop_index("ix_scan_dispatch_obligations_repository_id", table_name="scan_dispatch_obligations")
    op.drop_index("ix_scan_dispatch_obligations_project_id", table_name="scan_dispatch_obligations")
    op.drop_index("ix_scan_dispatch_obligations_organization_id", table_name="scan_dispatch_obligations")
    op.drop_table("scan_dispatch_obligations")

    op.drop_column("scans", "worker_incarnation_id")
    op.drop_column("scans", "worker_principal_id")
    op.drop_column("scans", "supersession_reason")
    op.drop_column("scans", "superseded_by_scan_id")
    op.drop_column("scans", "dispatch_state")
    op.drop_column("scans", "cleanup_state")
    op.drop_column("scans", "closure_eligible")
    op.drop_column("scans", "coverage_completeness")
    op.drop_column("scans", "expected_scanners_json")
    op.drop_column("scans", "ancestry_status")
    op.drop_column("scans", "branch_generation_number")
    op.drop_column("scans", "full_ref_name")
    op.drop_column("scans", "contract_version")

    op.drop_index("ix_repository_branch_generations_repository_id", table_name="repository_branch_generations")
    op.drop_table("repository_branch_generations")

    op.drop_index("ix_repositories_external_repo_id", table_name="repositories")
    op.drop_column("repositories", "lifecycle_state")
