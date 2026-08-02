"""add Bitrix24 chat sync state

Revision ID: b7e2c9d41f08
Revises: a6d14c2e9f30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2c9d41f08"
down_revision: str | None = "a6d14c2e9f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bitrix_installations", sa.Column("im_event_offset", sa.BigInteger(), nullable=True))
    op.add_column(
        "bitrix_installations",
        sa.Column("im_event_subscribed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="cabinet"),
    )
    op.add_column(
        "chat_messages",
        sa.Column("bitrix_sync_status", sa.String(length=20), nullable=False, server_default="not_scheduled"),
    )
    op.add_column("chat_messages", sa.Column("bitrix_sync_error_code", sa.String(length=100), nullable=True))
    op.add_column("chat_messages", sa.Column("bitrix_message_id", sa.String(length=100), nullable=True))
    op.add_column("chat_messages", sa.Column("bitrix_author_id", sa.String(length=100), nullable=True))
    op.add_column("chat_messages", sa.Column("bitrix_sync_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chat_messages", sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_chat_messages_bitrix_sync_status",
        "chat_messages",
        "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
    )
    op.create_index("ix_chat_messages_bitrix_sync_status", "chat_messages", ["bitrix_sync_status"])
    op.create_index(
        "uq_chat_messages_bitrix_message_id",
        "chat_messages",
        ["bitrix_message_id"],
        unique=True,
        postgresql_where=sa.text("bitrix_message_id IS NOT NULL"),
    )
    op.create_table(
        "chat_message_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("chat_message_id", sa.Uuid(), nullable=True),
        sa.Column("bitrix_event_id", sa.BigInteger(), nullable=False),
        sa.Column("bitrix_message_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["bitrix_installations.member_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["chat_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "bitrix_event_id", name="uq_chat_message_events_remote"),
    )
    op.create_index("ix_chat_message_events_member_id", "chat_message_events", ["member_id"])
    op.create_index("ix_chat_message_events_room_id", "chat_message_events", ["room_id"])
    op.create_index(
        "ix_chat_message_events_room_date",
        "chat_message_events",
        ["room_id", "event_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_message_events_room_date", table_name="chat_message_events")
    op.drop_index("ix_chat_message_events_room_id", table_name="chat_message_events")
    op.drop_index("ix_chat_message_events_member_id", table_name="chat_message_events")
    op.drop_table("chat_message_events")
    op.drop_index("uq_chat_messages_bitrix_message_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_bitrix_sync_status", table_name="chat_messages")
    op.drop_constraint("ck_chat_messages_bitrix_sync_status", "chat_messages", type_="check")
    for column in (
        "bitrix_synced_at",
        "bitrix_sync_requested_at",
        "bitrix_author_id",
        "bitrix_message_id",
        "bitrix_sync_error_code",
        "bitrix_sync_status",
        "origin",
    ):
        op.drop_column("chat_messages", column)
    op.drop_column("bitrix_installations", "im_event_subscribed_at")
    op.drop_column("bitrix_installations", "im_event_offset")
