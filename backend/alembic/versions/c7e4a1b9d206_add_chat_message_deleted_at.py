"""add chat_message deleted_at (soft delete)

Revision ID: c7e4a1b9d206
Revises: 7d3a1f9c2b04
Create Date: 2026-10-02 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e4a1b9d206"
down_revision: str | None = "7d3a1f9c2b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_chat_messages_deleted_at", "chat_messages", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_messages_deleted_at", table_name="chat_messages")
    op.drop_column("chat_messages", "deleted_at")
