"""chat_delivery_status: is_read bool → delivery_status varchar

Revision ID: a1b2c3d4e5f6
Revises: f1a9c7e50b42
Create Date: 2026-04-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a9c7e50b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("delivery_status", sa.String(10), server_default="sent", nullable=False))
    # Migrate data: is_read=true → 'read', is_read=false → 'sent'
    op.execute("UPDATE chat_messages SET delivery_status = CASE WHEN is_read = true THEN 'read' ELSE 'sent' END")
    op.drop_column("chat_messages", "is_read")


def downgrade() -> None:
    op.add_column("chat_messages", sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.execute("UPDATE chat_messages SET is_read = (delivery_status = 'read')")
    op.drop_column("chat_messages", "delivery_status")
