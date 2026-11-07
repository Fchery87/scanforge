"""Add shadow replay corpus entries (additive new table, references only).

Revision ID: 0029_shadow_corpus_entries
Revises: 0028_shadow_candidate_labels
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029_shadow_corpus_entries"
down_revision = "0028_shadow_candidate_labels"
branch_labels = None
depends_on = None

TABLE = "shadow_corpus_entries"


def _fk(column: str, target: str) -> sa.Column:
    return sa.Column(
        column,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(f"{target}.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _fk("organization_id", "organizations"),
        _fk("repository_id", "repositories"),
        sa.Column("pull_request_number", sa.Integer(), nullable=False),
        _fk("scan_id", "scans"),
        _fk("candidate_id", "shadow_review_candidates"),
        _fk("label_id", "shadow_review_candidate_labels"),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=True),
        sa.Column("merge_base_sha", sa.String(length=64), nullable=True),
        sa.Column("split", sa.String(length=16), nullable=False),
        sa.Column("split_policy", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("label_id", name="uq_shadow_corpus_label"),
    )
    op.create_index(f"ix_{TABLE}_organization_id", TABLE, ["organization_id"])
    op.create_index(f"ix_{TABLE}_repository_id", TABLE, ["repository_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_repository_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_organization_id", table_name=TABLE)
    op.drop_table(TABLE)
