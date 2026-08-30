"""add ai_annotation to finding_instances

Revision ID: 0015_finding_instance_ai_annotation
Revises: 0014_repository_importance
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_finding_instance_ai_annotation"
down_revision = "0014_repository_importance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "finding_instances",
        sa.Column("ai_annotation", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("finding_instances", "ai_annotation")
