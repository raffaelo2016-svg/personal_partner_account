"""add telegram notifications

Revision ID: 4b8c2d6e9f10
Revises: 3a7b9c1d5e20
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b8c2d6e9f10"
down_revision: str | None = "3a7b9c1d5e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("telegram_notifications", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column("notification_preferences", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("notification_preferences", sa.Column("telegram_username", sa.String(length=64), nullable=True))
    op.add_column("notification_preferences", sa.Column("telegram_connected_at", sa.DateTime(), nullable=True))
    op.add_column(
        "notification_preferences",
        sa.Column("telegram_connect_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("telegram_connect_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_notification_preferences_telegram_chat_id",
        "notification_preferences",
        ["telegram_chat_id"],
    )
    op.create_index(
        "ix_notification_preferences_telegram_connect_token_hash",
        "notification_preferences",
        ["telegram_connect_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_preferences_telegram_connect_token_hash", table_name="notification_preferences")
    op.drop_constraint(
        "uq_notification_preferences_telegram_chat_id",
        "notification_preferences",
        type_="unique",
    )
    op.drop_column("notification_preferences", "telegram_connect_expires_at")
    op.drop_column("notification_preferences", "telegram_connect_token_hash")
    op.drop_column("notification_preferences", "telegram_connected_at")
    op.drop_column("notification_preferences", "telegram_username")
    op.drop_column("notification_preferences", "telegram_chat_id")
    op.drop_column("notification_preferences", "telegram_notifications")
