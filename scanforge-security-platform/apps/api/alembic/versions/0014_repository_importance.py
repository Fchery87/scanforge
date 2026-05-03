"""add repository importance

Revision ID: 0014_repository_importance
Revises: 0013_finding_risk_score
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_repository_importance"
down_revision = "0013_finding_risk_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("importance", sa.String(length=20), nullable=False, server_default="normal"),
    )
    op.alter_column("repositories", "importance", server_default=None)


def downgrade() -> None:
    op.drop_column("repositories", "importance")
