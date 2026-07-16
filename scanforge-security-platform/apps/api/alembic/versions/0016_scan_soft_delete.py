"""add deleted_at to scans for soft delete

Revision ID: 0016_scan_soft_delete
Revises: 0015_finding_instance_ai_annotation
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_scan_soft_delete"
down_revision = "0015_finding_instance_ai_annotation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scans", "deleted_at")
