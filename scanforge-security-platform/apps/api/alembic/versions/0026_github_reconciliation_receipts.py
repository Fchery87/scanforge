"""Add GitHub reconciliation receipts (additive new table).

Revision ID: 0026_github_reconciliation_receipts
Revises: 0025_shadow_pr_revision_identity
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_github_reconciliation_receipts"
down_revision = "0025_shadow_pr_revision_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_reconciliation_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("installation_id", sa.String(length=255), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_github_reconciliation_receipts_installation_id",
        "github_reconciliation_receipts",
        ["installation_id"],
    )
    op.create_index(
        "ix_github_reconciliation_receipts_organization_id",
        "github_reconciliation_receipts",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_github_reconciliation_receipts_organization_id", table_name="github_reconciliation_receipts")
    op.drop_index("ix_github_reconciliation_receipts_installation_id", table_name="github_reconciliation_receipts")
    op.drop_table("github_reconciliation_receipts")
