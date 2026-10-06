"""Persist exact PR context and retryable GitHub Check projection."""

import sqlalchemy as sa

from alembic import op

revision = "0021_github_scan_context"
down_revision = "0020_scan_attempt_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("base_commit_sha", sa.String(64), nullable=True))
    op.add_column("scans", sa.Column("head_commit_sha", sa.String(64), nullable=True))
    op.add_column("scans", sa.Column("github_check_run_id", sa.BigInteger(), nullable=True))
    op.add_column("scans", sa.Column("github_check_pending", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("scans", sa.Column("github_check_payload_digest", sa.String(64), nullable=True))
    op.create_index("ix_scans_github_check_pending", "scans", ["github_check_pending"])


def downgrade() -> None:
    op.drop_index("ix_scans_github_check_pending", table_name="scans")
    for name in (
        "github_check_payload_digest",
        "github_check_pending",
        "github_check_run_id",
        "head_commit_sha",
        "base_commit_sha",
    ):
        op.drop_column("scans", name)
