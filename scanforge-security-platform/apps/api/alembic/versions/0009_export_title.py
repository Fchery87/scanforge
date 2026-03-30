"""export title

Revision ID: 0009_export_title
Revises: 0008_finding_triage_fields
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_export_title"
down_revision = "0008_finding_triage_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exports", sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("exports", "title")
