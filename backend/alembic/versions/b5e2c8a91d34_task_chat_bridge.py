"""Общий чат задачи: связь обсуждения в кабинете с чатом задачи Битрикс24.

Revision ID: b5e2c8a91d34
Revises: a9c4e7f21b03
Create Date: 2026-11-25 16:05:00.000000

Обсуждение задачи в кабинете и чат задачи в Битрикс24 — одно общение.
Задача запоминает диалог своего чата, а сообщение — своё происхождение и
удалённый идентификатор, чтобы не дублировать импорт.

IF NOT EXISTS/NOT NULL-переходы безопасны для уже существующей базы.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b5e2c8a91d34"
down_revision: str | None = "a9c4e7f21b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_chat_dialog_id VARCHAR(50)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_bitrix_chat_dialog_id ON tasks (bitrix_chat_dialog_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_chat_states (
            task_id UUID PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
            last_polled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )

    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS origin VARCHAR(20) NOT NULL DEFAULT 'cabinet'")
    op.execute(
        "ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_sync_status VARCHAR(20) "
        "NOT NULL DEFAULT 'not_scheduled'"
    )
    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_sync_error_code VARCHAR(100)")
    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_message_id VARCHAR(100)")
    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_author_id VARCHAR(100)")
    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS external_author_name VARCHAR(255)")
    op.execute(
        "ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_sync_requested_at TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute("ALTER TABLE task_messages ADD COLUMN IF NOT EXISTS bitrix_synced_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_messages_bitrix_message_id "
        "ON task_messages (bitrix_message_id) WHERE bitrix_message_id IS NOT NULL"
    )
    op.execute("ALTER TABLE task_messages ALTER COLUMN author_id DROP NOT NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_chat_states")
    op.execute("DROP INDEX IF EXISTS uq_task_messages_bitrix_message_id")
    op.execute("DROP INDEX IF EXISTS ix_tasks_bitrix_chat_dialog_id")
    for column in (
        "origin",
        "bitrix_sync_status",
        "bitrix_sync_error_code",
        "bitrix_message_id",
        "bitrix_author_id",
        "external_author_name",
        "bitrix_sync_requested_at",
        "bitrix_synced_at",
    ):
        op.execute(f"ALTER TABLE task_messages DROP COLUMN IF EXISTS {column}")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS bitrix_chat_dialog_id")
