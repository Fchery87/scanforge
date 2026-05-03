"""persist scan type

Revision ID: 0012_scan_type
Revises: 0011_security_cleanup
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_scan_type"
down_revision = "0011_security_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("scan_type", sa.String(length=50), nullable=False, server_default="full"))
    op.alter_column("scans", "scan_type", server_default=None)


def downgrade() -> None:
    op.drop_column("scans", "scan_type")
