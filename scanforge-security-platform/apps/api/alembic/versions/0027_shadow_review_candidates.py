"""Add shadow PR head tracking and review candidates (additive new tables).

Revision ID: 0027_shadow_review_candidates
Revises: 0026_github_reconciliation_receipts
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027_shadow_review_candidates"
down_revision = "0026_github_reconciliation_receipts"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "shadow_pull_request_heads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pull_request_number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("head_observed_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("repository_id", "pull_request_number", name="uq_shadow_pr_head"),
    )
    op.create_index("ix_shadow_pull_request_heads_repository_id", "shadow_pull_request_heads", ["repository_id"])

    op.create_table(
        "shadow_review_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pull_request_number", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("scanner", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "first_scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "last_scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("resolution_basis", sa.String(length=32), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "repository_id", "pull_request_number", "fingerprint", name="uq_shadow_candidate_identity"
        ),
    )
    op.create_index("ix_shadow_review_candidates_repository_id", "shadow_review_candidates", ["repository_id"])


def downgrade() -> None:
    op.drop_index("ix_shadow_review_candidates_repository_id", table_name="shadow_review_candidates")
    op.drop_table("shadow_review_candidates")
    op.drop_index("ix_shadow_pull_request_heads_repository_id", table_name="shadow_pull_request_heads")
    op.drop_table("shadow_pull_request_heads")
