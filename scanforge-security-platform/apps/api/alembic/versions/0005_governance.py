"""governance

Revision ID: 0005_governance
Revises: 0004_findings_core
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import func

revision = "0005_governance"
down_revision = "0004_findings_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppression_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("repository_id", UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("match_criteria_json", JSONB, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_suppression_rules_org_id", "suppression_rules", ["organization_id"])

    op.create_table(
        "finding_suppressions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("suppression_rule_id", UUID(as_uuid=True), sa.ForeignKey("suppression_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    op.create_index("ix_finding_suppressions_finding_id", "finding_suppressions", ["finding_id"])


def downgrade() -> None:
    op.drop_table("finding_suppressions")
    op.drop_table("suppression_rules")
