"""webhook event digest idempotency and scan base sha

Revision ID: 0022_webhook_event_digest_base_sha
Revises: 0021_scan_execution_lease
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0022_webhook_event_digest"
down_revision = "0021_scan_execution_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # R10 recorded base/head diff: base commit persisted alongside commit_sha.
    op.add_column("scans", sa.Column("base_sha", sa.String(length=64), nullable=True))

    # R10 replay safety: canonical event digest (D6 convention: canonical JSON + SHA-256)
    # plus the original business response, so identical replays never duplicate scans.
    op.add_column("webhook_deliveries", sa.Column("event_digest", sa.String(length=64), nullable=True))
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "scan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("webhook_deliveries", sa.Column("response_json", JSONB(), nullable=True))

    # Backfill follows the 0018 occurrence-fingerprint convention: deterministic,
    # row-unique digest for pre-existing rows (provider + delivery_id is unique).
    op.execute("UPDATE webhook_deliveries SET event_digest = md5(provider || ':' || delivery_id)")
    op.alter_column("webhook_deliveries", "event_digest", nullable=False)

    op.create_unique_constraint(
        "uq_webhook_provider_repo_event_digest",
        "webhook_deliveries",
        ["provider", "repository_id", "event_digest"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_webhook_provider_repo_event_digest",
        "webhook_deliveries",
        type_="unique",
    )
    op.drop_column("webhook_deliveries", "response_json")
    op.drop_column("webhook_deliveries", "scan_id")
    op.drop_column("webhook_deliveries", "event_digest")
    op.drop_column("scans", "base_sha")
