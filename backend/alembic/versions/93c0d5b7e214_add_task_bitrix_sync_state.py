"""add task Bitrix24 sync state

Revision ID: 93c0d5b7e214
Revises: 82b9e4a6c103
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "93c0d5b7e214"
down_revision: str | None = "82b9e4a6c103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("bitrix_sync_status", sa.String(length=20), nullable=False, server_default="not_scheduled"),
    )
    op.add_column("tasks", sa.Column("bitrix_sync_error_code", sa.String(length=100), nullable=True))
    op.add_column("tasks", sa.Column("bitrix_task_id", sa.String(length=100), nullable=True))
    op.add_column("tasks", sa.Column("bitrix_sync_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_tasks_bitrix_sync_status",
        "tasks",
        "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
    )
    op.create_index("ix_tasks_bitrix_sync_status", "tasks", ["bitrix_sync_status"])
    op.add_column("bitrix_inbound_events", sa.Column("remote_entity_type", sa.String(length=50), nullable=True))
    op.add_column("bitrix_inbound_events", sa.Column("remote_entity_id", sa.String(length=100), nullable=True))
    op.create_index(
        "ix_bitrix_inbound_events_remote",
        "bitrix_inbound_events",
        ["member_id", "remote_entity_type", "remote_entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bitrix_inbound_events_remote", table_name="bitrix_inbound_events")
    op.drop_column("bitrix_inbound_events", "remote_entity_id")
    op.drop_column("bitrix_inbound_events", "remote_entity_type")
    op.drop_index("ix_tasks_bitrix_sync_status", table_name="tasks")
    op.drop_constraint("ck_tasks_bitrix_sync_status", "tasks", type_="check")
    for column in (
        "bitrix_synced_at",
        "bitrix_sync_requested_at",
        "bitrix_task_id",
        "bitrix_sync_error_code",
        "bitrix_sync_status",
    ):
        op.drop_column("tasks", column)
