"""add ai_annotation to finding_instances

Revision ID: 0015_finding_instance_ai_annotation
Revises: 0014_repository_importance
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0015_finding_instance_ai_annotation"
down_revision = "0014_repository_importance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic's default version table uses VARCHAR(32), but this revision ID is
    # longer. Widen it before Alembic records this revision at transaction end.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.add_column(
        "finding_instances",
        sa.Column("ai_annotation", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("finding_instances", "ai_annotation")
