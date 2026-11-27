"""Приём задач из Битрикс24 в кабинет партнёра.

Revision ID: b3d7f1c9a2e4
Revises: c1d3a5e70b22, 4d7f2a9c1e55, c3e9a1f4b872
Create Date: 2026-11-27 12:00:00.000000

Двусторонний контур из ТЗ «Передача задач из Битрикс24 в ЛКП»:

* у задачи появляется происхождение (кабинет или шлюз), ссылка и постановщик
  из Битрикса, клиент по сделке, причина отклонения;
* отдельная таблица ``bitrix_task_status_changes`` хранит историю смены
  статусов для шлюза: потеря ``next_since`` не приводит к потере изменений;
* частичный уникальный индекс не даёт создать вторую задачу с тем же номером
  Битрикса.

Мердж трёх веток миграций: down_revision перечисляет все головы.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3d7f1c9a2e4"
down_revision: str | tuple[str, ...] | None = ("c1d3a5e70b22", "4d7f2a9c1e55", "c3e9a1f4b872")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS origin VARCHAR(20) NOT NULL DEFAULT 'cabinet'")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_url VARCHAR(500)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_author_name VARCHAR(255)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_author_id VARCHAR(50)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_client_name VARCHAR(255)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_deal_id VARCHAR(100)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_status VARCHAR(20)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_updated_at TIMESTAMP")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reject_reason TEXT")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_gateway_bitrix_task_id "
        "ON tasks (bitrix_task_id) WHERE origin = 'bitrix_gateway'"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bitrix_task_status_changes (
            id UUID PRIMARY KEY,
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            bitrix_task_id VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL,
            changed_at TIMESTAMP NOT NULL,
            author_name VARCHAR(255) NOT NULL,
            author_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            reject_reason TEXT,
            origin VARCHAR(20) NOT NULL DEFAULT 'cabinet',
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bitrix_task_status_changes_changed ON bitrix_task_status_changes (changed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bitrix_task_status_changes_task "
        "ON bitrix_task_status_changes (task_id, changed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bitrix_task_status_changes_remote ON bitrix_task_status_changes (bitrix_task_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bitrix_task_status_changes_task_id ON bitrix_task_status_changes (task_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bitrix_task_status_changes")
    op.execute("DROP INDEX IF EXISTS uq_tasks_gateway_bitrix_task_id")
    for column in (
        "origin",
        "bitrix_url",
        "bitrix_author_name",
        "bitrix_author_id",
        "bitrix_client_name",
        "bitrix_deal_id",
        "bitrix_status",
        "bitrix_updated_at",
        "reject_reason",
        "status_changed_at",
    ):
        op.execute(f"ALTER TABLE tasks DROP COLUMN IF EXISTS {column}")
