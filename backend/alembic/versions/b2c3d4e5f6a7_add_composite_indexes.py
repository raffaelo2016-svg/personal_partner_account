"""add composite indexes for query optimization

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-13 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_court_fees_partner_status_deleted",
        "court_fees",
        ["partner_id", "status", "deleted_at"],
    )
    op.create_index(
        "ix_court_fees_status_due_date_deleted",
        "court_fees",
        ["status", "due_date", "deleted_at"],
    )
    op.create_index(
        "ix_clients_partner_deleted",
        "clients",
        ["partner_id", "deleted_at"],
    )
    op.create_index(
        "ix_notifications_user_is_read",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "ix_chat_messages_sender_id",
        "chat_messages",
        ["sender_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_index("ix_notifications_user_is_read", table_name="notifications")
    op.drop_index("ix_clients_partner_deleted", table_name="clients")
    op.drop_index("ix_court_fees_status_due_date_deleted", table_name="court_fees")
    op.drop_index("ix_court_fees_partner_status_deleted", table_name="court_fees")
