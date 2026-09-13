"""server-owned scan completion receipts

Revision ID: 0019_scan_completion_receipts
Revises: 0018_idempotent_scan_occurrences
"""

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0019_scan_completion_receipts"
down_revision = "0018_idempotent_scan_occurrences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_completion_receipts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=func.gen_random_uuid(),
        ),
        sa.Column(
            "scan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("winning_attempt_id", sa.String(length=64), nullable=False),
        sa.Column("execution_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("terminal_status", sa.String(length=50), nullable=False),
        sa.Column("inserted_findings", sa.Integer(), nullable=False),
        sa.Column("updated_findings", sa.Integer(), nullable=False),
        sa.Column("scanner_runs_total", sa.Integer(), nullable=False),
        sa.Column("scanner_runs_complete", sa.Boolean(), nullable=False),
        sa.Column("response_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("scan_id", name="uq_scan_completion_receipt_scan"),
    )
    op.create_index(
        "ix_scan_completion_receipts_scan_id",
        "scan_completion_receipts",
        ["scan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_completion_receipts_scan_id", table_name="scan_completion_receipts")
    op.drop_table("scan_completion_receipts")
