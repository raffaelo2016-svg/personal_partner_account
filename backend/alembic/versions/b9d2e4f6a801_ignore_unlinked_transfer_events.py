"""Ignore unlinked deal updates caused by funnel transfers.

Revision ID: b9d2e4f6a801
Revises: a8f31d6c209e
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d2e4f6a801"
down_revision: str | None = "a8f31d6c209e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE bitrix_inbound_events AS event
            SET status = 'ignored',
                error_code = NULL,
                processed_at = COALESCE(processed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE event.remote_entity_type = 'client_deal'
              AND event.event_name = 'ONCRMDEALUPDATE'
              AND event.status = 'failed'
              AND event.error_code = 'PARTNER_NOT_LINKED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM bitrix_entity_maps AS mapping
                  WHERE mapping.member_id = event.member_id
                    AND mapping.local_entity_type = 'client_deal'
                    AND mapping.bitrix_entity_type = 'crm_deal'
                    AND mapping.bitrix_entity_id = event.remote_entity_id
              )
            """
        )
    )


def downgrade() -> None:
    # This migration acknowledges historical service receipts. Reopening them
    # during a rollback would recreate already triaged administrator warnings.
    pass
