"""add_chat_attachment_assignments (production chain).

Revision ID: c3e9a1f4b872
Revises: f8a3c1d2e4b6
Create Date: 2026-11-03 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3e9a1f4b872"
down_revision: str | None = "f8a3c1d2e4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_attachment_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_message_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column("document_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('assigned', 'ignored')",
            name="ck_chat_attachment_assignments_status",
        ),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file_uploads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_chat_attachment_assignments_message",
        "chat_attachment_assignments",
        ["chat_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_chat_attachment_assignments_status",
        "chat_attachment_assignments",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_chat_attachment_assignments_client_id",
        "chat_attachment_assignments",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_attachment_assignments_client_id", table_name="chat_attachment_assignments")
    op.drop_index("ix_chat_attachment_assignments_status", table_name="chat_attachment_assignments")
    op.drop_index("uq_chat_attachment_assignments_message", table_name="chat_attachment_assignments")
    op.drop_table("chat_attachment_assignments")
