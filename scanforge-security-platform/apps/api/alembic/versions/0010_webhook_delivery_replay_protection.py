"""webhook delivery replay protection

Revision ID: 0010_webhook_replay
Revises: 0009_export_title
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

revision = "0010_webhook_replay"
down_revision = "0009_export_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=func.gen_random_uuid(),
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("delivery_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "repository_id", UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True
        ),
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
            onupdate=func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_provider_delivery"),
    )
    op.create_index("ix_webhook_deliveries_org_id", "webhook_deliveries", ["organization_id"])
    op.create_index("ix_webhook_deliveries_project_id", "webhook_deliveries", ["project_id"])
    op.create_index("ix_webhook_deliveries_repository_id", "webhook_deliveries", ["repository_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_repository_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_project_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_org_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
