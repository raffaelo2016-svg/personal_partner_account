"""Tombstones for documents deleted from the cabinet.

Revision ID: f7c2b8e14d90
Revises: c7e4a1b9d206
Create Date: 2026-10-29 17:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7c2b8e14d90"
down_revision: str | None = "c7e4a1b9d206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_deletion_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_disk_file_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id",
            "bitrix_disk_file_id",
            name="uq_file_deletion_tombstones_client_disk_file",
        ),
    )
    op.create_index(
        op.f("ix_file_deletion_tombstones_client_id"),
        "file_deletion_tombstones",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_file_deletion_tombstones_client_id"), table_name="file_deletion_tombstones")
    op.drop_table("file_deletion_tombstones")
