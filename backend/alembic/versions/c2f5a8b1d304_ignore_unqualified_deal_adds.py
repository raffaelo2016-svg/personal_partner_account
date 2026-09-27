"""Ignore unqualified deals that are not cabinet clients yet.

Revision ID: c2f5a8b1d304
Revises: b9d2e4f6a801
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2f5a8b1d304"
down_revision: str | None = "b9d2e4f6a801"
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
    # The acknowledged receipts represent deals that had never become cabinet
    # clients. Reopening them during a rollback would recreate service noise.
    pass
