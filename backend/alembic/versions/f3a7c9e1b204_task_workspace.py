"""Task workspace: review flow, files, messages and history.

Revision ID: f3a7c9e1b204
Revises: b7e3f9a1c2d4
Create Date: 2026-11-22 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a7c9e1b204"
down_revision: str | None = "b7e3f9a1c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("review_requested_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("review_requested_by", sa.Uuid(), nullable=True))
    op.create_index("ix_tasks_review_requested_at", "tasks", ["review_requested_at"])
    op.create_foreign_key(
        "fk_tasks_review_requested_by_users",
        "tasks",
        "users",
        ["review_requested_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "task_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=500), nullable=False),
        sa.Column("s3_key", sa.String(length=500), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index("ix_task_files_task_id", "task_files", ["task_id"])
    op.create_index("ix_task_files_client_id", "task_files", ["client_id"])
    op.create_index("ix_task_files_task_created", "task_files", ["task_id", "created_at"])
    op.create_index("ix_task_files_client_created", "task_files", ["client_id", "created_at"])

    op.create_table(
        "task_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_messages_task_id", "task_messages", ["task_id"])
    op.create_index("ix_task_messages_author_id", "task_messages", ["author_id"])
    op.create_index("ix_task_messages_deleted_at", "task_messages", ["deleted_at"])
    op.create_index("ix_task_messages_task_created", "task_messages", ["task_id", "created_at"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_task_created", "task_events", ["task_id", "created_at"])

    op.create_table(
        "task_read_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_id", name="uq_task_read_states_user_task"),
    )
    op.create_index("ix_task_read_states_user_id", "task_read_states", ["user_id"])
    op.create_index("ix_task_read_states_task_id", "task_read_states", ["task_id"])


def downgrade() -> None:
    op.drop_table("task_read_states")
    op.drop_table("task_events")
    op.drop_table("task_messages")
    op.drop_table("task_files")
    op.drop_constraint("fk_tasks_review_requested_by_users", "tasks", type_="foreignkey")
    op.drop_index("ix_tasks_review_requested_at", table_name="tasks")
    op.drop_column("tasks", "review_requested_by")
    op.drop_column("tasks", "review_requested_at")
