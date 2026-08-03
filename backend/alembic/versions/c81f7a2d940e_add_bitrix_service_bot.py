"""add Bitrix24 service bot state

Revision ID: c81f7a2d940e
Revises: b7e2c9d41f08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c81f7a2d940e"
down_revision: str | None = "b7e2c9d41f08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bitrix_installations", sa.Column("im_bot_id", sa.BigInteger(), nullable=True))
    op.add_column("bitrix_installations", sa.Column("im_bot_event_offset", sa.BigInteger(), nullable=True))
    op.add_column("partners", sa.Column("bitrix_chat_bot_joined_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "bitrix_chat_bot_joined_at")
    op.drop_column("bitrix_installations", "im_bot_event_offset")
    op.drop_column("bitrix_installations", "im_bot_id")
