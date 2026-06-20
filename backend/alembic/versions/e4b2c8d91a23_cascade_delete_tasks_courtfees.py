"""cascade_delete_tasks_and_court_fees_client_fk

Revision ID: e4b2c8d91a23
Revises: c3f1a2b4e567
Create Date: 2026-04-01 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4b2c8d91a23"
down_revision: str | None = "c3f1a2b4e567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("tasks_client_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(
        "tasks_client_id_fkey",
        "tasks",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("court_fees_client_id_fkey", "court_fees", type_="foreignkey")
    op.create_foreign_key(
        "court_fees_client_id_fkey",
        "court_fees",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("tasks_client_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(
        "tasks_client_id_fkey",
        "tasks",
        "clients",
        ["client_id"],
        ["id"],
    )

    op.drop_constraint("court_fees_client_id_fkey", "court_fees", type_="foreignkey")
    op.create_foreign_key(
        "court_fees_client_id_fkey",
        "court_fees",
        "clients",
        ["client_id"],
        ["id"],
    )
