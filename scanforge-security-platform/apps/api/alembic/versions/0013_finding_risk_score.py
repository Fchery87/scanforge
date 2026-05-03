"""add finding risk score

Revision ID: 0013_finding_risk_score
Revises: 0012_scan_type
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_finding_risk_score"
down_revision = "0012_scan_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("risk_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "risk_score")
