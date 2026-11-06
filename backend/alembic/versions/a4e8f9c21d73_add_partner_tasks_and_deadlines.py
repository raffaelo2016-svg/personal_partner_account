"""Add direct partner ownership and optional precise task deadlines.

Revision ID: a4e8f9c21d73
Revises: 9f4b7c2d8e01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "a4e8f9c21d73"
down_revision: str | None = "9f4b7c2d8e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A targeted deployment may already have installed these additive changes
    # without advancing the shared Alembic revision past unrelated migrations.
    # Inspect only online; offline generation still emits the complete migration.
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("tasks")} if inspector else {}
    foreign_keys = inspector.get_foreign_keys("tasks") if inspector else []
    indexes = inspector.get_indexes("tasks") if inspector else []
    if "partner_id" not in columns:
        op.add_column("tasks", sa.Column("partner_id", sa.Uuid(), nullable=True))
    if not any(
        fk["constrained_columns"] == ["partner_id"]
        and fk["referred_table"] == "partners"
        and fk["referred_columns"] == ["id"]
        for fk in foreign_keys
    ):
        op.create_foreign_key("tasks_partner_id_fkey", "tasks", "partners", ["partner_id"], ["id"])
    if not any(index["column_names"] == ["partner_id"] and not index["unique"] for index in indexes):
        op.create_index("ix_tasks_partner_id", "tasks", ["partner_id"])
    op.execute(
        "UPDATE tasks SET partner_id = clients.partner_id FROM clients "
        "WHERE tasks.client_id = clients.id AND tasks.partner_id IS NULL"
    )
    if "client_id" not in columns or not columns["client_id"]["nullable"]:
        op.alter_column("tasks", "client_id", existing_type=sa.Uuid(), nullable=True)
    if "due_date" not in columns or not columns["due_date"]["nullable"]:
        op.alter_column("tasks", "due_date", existing_type=sa.Date(), nullable=True)
    # UTCDateTime writes UTC without a zone, matching the existing ORM convention.
    if "due_at" not in columns:
        op.add_column("tasks", sa.Column("due_at", sa.DateTime(), nullable=True))
    if not any(index["column_names"] == ["due_at"] and not index["unique"] for index in indexes):
        op.create_index("ix_tasks_due_at", "tasks", ["due_at"])
    if "bitrix_imported" not in columns:
        op.add_column("tasks", sa.Column("bitrix_imported", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.execute(
            """
            UPDATE tasks SET bitrix_imported = TRUE
            WHERE bitrix_task_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM bitrix_outbox_operations outbox
                WHERE outbox.local_entity_type = 'task' AND outbox.local_entity_id = tasks.id
                  AND outbox.bitrix_method = 'tasks.task.add'
            )
            """
        )
    if "bitrix_published" not in columns:
        op.add_column("tasks", sa.Column("bitrix_published", sa.Boolean(), nullable=False, server_default=sa.true()))
    # Earlier workers replaced the lifecycle status. Future reads derive overdue
    # from the deadline and retain pending/in_progress when deadlines are moved.
    op.execute("UPDATE tasks SET status = 'pending' WHERE status = 'overdue'")


def downgrade() -> None:
    connection = op.get_bind()
    incompatible = connection.scalar(
        sa.text("SELECT count(*) FROM tasks WHERE client_id IS NULL OR due_date IS NULL")
    )
    if incompatible:
        raise RuntimeError("Cannot downgrade: tasks without a client or deadline require the new schema")
    op.drop_column("tasks", "bitrix_published")
    op.drop_column("tasks", "bitrix_imported")
    op.drop_index("ix_tasks_due_at", table_name="tasks")
    op.drop_column("tasks", "due_at")
    op.alter_column("tasks", "due_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("tasks", "client_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_tasks_partner_id", table_name="tasks")
    op.drop_constraint("tasks_partner_id_fkey", "tasks", type_="foreignkey")
    op.drop_column("tasks", "partner_id")
