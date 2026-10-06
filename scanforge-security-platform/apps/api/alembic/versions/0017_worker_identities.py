"""add organization-scoped worker identities

Revision ID: 0017_worker_identities
Revises: 0016_scan_soft_delete
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0017_worker_identities"
down_revision = "0016_scan_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_identities",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("credential_hash", sa.String(length=64), nullable=False),
        sa.Column("capabilities_json", JSONB, nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_hash"),
    )
    op.create_index("ix_worker_identities_organization_id", "worker_identities", ["organization_id"])
    op.create_index(
        "uq_worker_identities_active_org_name",
        "worker_identities",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("disabled_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_worker_identities_active_org_name", table_name="worker_identities")
    op.drop_index("ix_worker_identities_organization_id", table_name="worker_identities")
    op.drop_table("worker_identities")
