"""organization invitations for verified pending membership acceptance

Revision ID: 0023_org_invitations_and_owner_transfer
Revises: 0022_webhook_event_digest
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision = "0023_org_invitations_and_owner_transfer"
down_revision = "0022_webhook_event_digest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(length=64),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    member_role_enum = ENUM(
        "owner",
        "admin",
        "security_reviewer",
        "developer",
        "viewer",
        name="member_role",
        create_type=False,
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", member_role_enum, nullable=False),
        sa.Column(
            "invited_by_user_id",
            UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "accepted_by_user_id",
            UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_org_invitation_token_hash"),
    )
    op.create_index("ix_org_invitations_org_id", "organization_invitations", ["organization_id"])
    op.create_index("ix_org_invitations_email", "organization_invitations", ["email"])
    op.create_index("ix_org_invitations_status", "organization_invitations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_org_invitations_status", table_name="organization_invitations")
    op.drop_index("ix_org_invitations_email", table_name="organization_invitations")
    op.drop_index("ix_org_invitations_org_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")
