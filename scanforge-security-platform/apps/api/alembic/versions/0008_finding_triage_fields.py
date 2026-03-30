"""finding triage fields

Revision ID: 0008_finding_triage_fields
Revises: 0007_org_github_integration
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_finding_triage_fields"
down_revision = "0007_org_github_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("assignee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("findings", sa.Column("due_date", sa.Date(), nullable=True))
    op.create_index("ix_findings_assignee_user_id", "findings", ["assignee_user_id"])
    op.create_index("ix_findings_due_date", "findings", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_findings_due_date", table_name="findings")
    op.drop_index("ix_findings_assignee_user_id", table_name="findings")
    op.drop_column("findings", "due_date")
    op.drop_column("findings", "assignee_user_id")
