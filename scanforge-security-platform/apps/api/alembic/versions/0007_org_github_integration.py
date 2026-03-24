"""org github integration

Revision ID: 0007_org_github_integration
Revises: 0006_operational_support
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

revision = "0007_org_github_integration"
down_revision = "0006_operational_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_integrations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=func.gen_random_uuid(),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(50), nullable=False, server_default="github"),
        sa.Column("installation_id", sa.String(255), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=True),
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
    )
    op.create_index("ix_org_integrations_org_id", "organization_integrations", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_org_integrations_org_id", "organization_integrations")
    op.drop_table("organization_integrations")
