"""scan execution lease visibility

Revision ID: 0021_scan_execution_lease
Revises: 0020_scan_attempt_identity
Create Date: 2026-09-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0021_scan_execution_lease"
down_revision = "0020_scan_attempt_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scans", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("scans", sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "last_heartbeat_at")
    op.drop_column("scans", "lease_owner")
    op.drop_column("scans", "lease_expires_at")
