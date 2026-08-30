"""add idempotency fingerprint to finding instances

Revision ID: 0018_idempotent_scan_occurrences
Revises: 0017_worker_identities
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_idempotent_scan_occurrences"
down_revision = "0017_worker_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "finding_instances",
        sa.Column("occurrence_fingerprint", sa.String(length=64), nullable=True),
    )
    op.execute("UPDATE finding_instances SET occurrence_fingerprint = md5(id::text)")
    op.alter_column("finding_instances", "occurrence_fingerprint", nullable=False)
    op.create_unique_constraint(
        "uq_finding_instance_scan_occurrence",
        "finding_instances",
        ["scan_id", "occurrence_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_finding_instance_scan_occurrence",
        "finding_instances",
        type_="unique",
    )
    op.drop_column("finding_instances", "occurrence_fingerprint")
