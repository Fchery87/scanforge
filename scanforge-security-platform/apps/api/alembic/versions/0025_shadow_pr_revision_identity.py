"""Record shadow PR revision identity on scans (additive, nullable).

Revision ID: 0025_shadow_pr_revision_identity
Revises: 0024_evidence_and_execution_contracts
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_shadow_pr_revision_identity"
down_revision = "0024_evidence_and_execution_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("merge_base_sha", sa.String(length=64), nullable=True))
    op.add_column("scans", sa.Column("comparison_strategy", sa.String(length=32), nullable=True))
    op.add_column(
        "scans",
        sa.Column("head_is_fork", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("scans", "head_is_fork")
    op.drop_column("scans", "comparison_strategy")
    op.drop_column("scans", "merge_base_sha")
