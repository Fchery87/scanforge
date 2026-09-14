"""server-issued scan attempt identity

Revision ID: 0020_scan_attempt_identity
Revises: 0019_scan_completion_receipts
Create Date: 2026-09-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0020_scan_attempt_identity"
down_revision = "0019_scan_completion_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("current_attempt_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "scans",
        sa.Column("execution_revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("scans", "execution_revision")
    op.drop_column("scans", "current_attempt_id")
