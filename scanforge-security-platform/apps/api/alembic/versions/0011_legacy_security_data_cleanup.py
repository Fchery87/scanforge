"""legacy security data cleanup

Revision ID: 0011_security_cleanup
Revises: 0010_webhook_replay
Create Date: 2026-04-04
"""

from alembic import op

revision = "0011_security_cleanup"
down_revision = "0010_webhook_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE scanner_runs
        SET artifact_uri = regexp_replace(artifact_uri, '^https?://[^/]+/', '')
        WHERE artifact_uri ~ '^https?://';
        """
    )

    op.execute(
        """
        UPDATE scanner_runs
        SET metadata_json = (
            SELECT jsonb_object_agg(key, CASE
                WHEN value #>> '{}' ~ '^https?://' THEN to_jsonb(regexp_replace(value #>> '{}', '^https?://[^/]+/', ''))
                ELSE value
            END)
            FROM jsonb_each(COALESCE(metadata_json, '{}'::jsonb))
        )
        WHERE metadata_json IS NOT NULL;
        """
    )

    op.execute(
        """
        UPDATE exports
        SET storage_uri = regexp_replace(storage_uri, '^https?://[^/]+/', '')
        WHERE storage_uri ~ '^https?://';
        """
    )

    op.execute(
        """
        UPDATE scans
        SET error_message = 'An internal error occurred. Please try again later.'
        WHERE error_message IS NOT NULL
          AND (
            error_message ILIKE '%token%'
            OR error_message ILIKE '%secret%'
            OR error_message ILIKE '%authorization%'
            OR error_message ILIKE '%password%'
            OR error_message ILIKE '%github%'
            OR error_message ILIKE '%traceback%'
            OR error_message ILIKE '%credential%'
            OR error_message ILIKE '%key%'
          );
        """
    )

    op.execute(
        """
        UPDATE scanner_runs
        SET error_message = 'An internal error occurred. Please try again later.'
        WHERE error_message IS NOT NULL
          AND (
            error_message ILIKE '%token%'
            OR error_message ILIKE '%secret%'
            OR error_message ILIKE '%authorization%'
            OR error_message ILIKE '%password%'
            OR error_message ILIKE '%github%'
            OR error_message ILIKE '%traceback%'
            OR error_message ILIKE '%credential%'
            OR error_message ILIKE '%key%'
          );
        """
    )

    op.execute(
        """
        UPDATE exports
        SET error_message = 'An internal error occurred. Please try again later.'
        WHERE error_message IS NOT NULL
          AND (
            error_message ILIKE '%token%'
            OR error_message ILIKE '%secret%'
            OR error_message ILIKE '%authorization%'
            OR error_message ILIKE '%password%'
            OR error_message ILIKE '%github%'
            OR error_message ILIKE '%traceback%'
            OR error_message ILIKE '%credential%'
            OR error_message ILIKE '%key%'
          );
        """
    )


def downgrade() -> None:
    pass
