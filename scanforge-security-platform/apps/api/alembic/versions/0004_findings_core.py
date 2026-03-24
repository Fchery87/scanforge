"""findings core

Revision ID: 0004_findings_core
Revises: 0003_scanning_core
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import func

revision = "0004_findings_core"
down_revision = "0003_scanning_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
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
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_findings_project_id", "findings", ["project_id"])
    op.create_index("ix_findings_repository_id", "findings", ["repository_id"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_fingerprint", "findings", ["canonical_fingerprint"])
    op.create_unique_constraint("uq_finding_repo_fingerprint", "findings", ["repository_id", "canonical_fingerprint"])

    op.create_table(
        "finding_instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_id", UUID(as_uuid=True), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner_run_id", UUID(as_uuid=True), sa.ForeignKey("scanner_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path", sa.String(2048), nullable=True),
        sa.Column("line_start", sa.Integer, nullable=True),
        sa.Column("line_end", sa.Integer, nullable=True),
        sa.Column("package_name", sa.String(255), nullable=True),
        sa.Column("installed_version", sa.String(128), nullable=True),
        sa.Column("fixed_version", sa.String(128), nullable=True),
        sa.Column("evidence_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_finding_instances_finding_id", "finding_instances", ["finding_id"])
    op.create_index("ix_finding_instances_scan_id", "finding_instances", ["scan_id"])
    op.create_index("ix_finding_instances_package_name", "finding_instances", ["package_name"])

    op.create_table(
        "finding_references",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_value", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_finding_references_finding_id", "finding_references", ["finding_id"])

    op.create_table(
        "finding_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_finding_events_finding_id", "finding_events", ["finding_id"])


def downgrade() -> None:
    op.drop_table("finding_events")
    op.drop_table("finding_references")
    op.drop_table("finding_instances")
    op.drop_table("findings")
