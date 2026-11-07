"""Add reviewer labels for shadow review candidates (additive new table).

Revision ID: 0028_shadow_candidate_labels
Revises: 0027_shadow_review_candidates
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028_shadow_candidate_labels"
down_revision = "0027_shadow_review_candidates"
branch_labels = None
depends_on = None

TABLE = "shadow_review_candidate_labels"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shadow_review_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_id", "actor_user_id", name="uq_shadow_label_actor"),
    )
    op.create_index(f"ix_{TABLE}_organization_id", TABLE, ["organization_id"])
    op.create_index(f"ix_{TABLE}_candidate_id", TABLE, ["candidate_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_candidate_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_organization_id", table_name=TABLE)
    op.drop_table(TABLE)
