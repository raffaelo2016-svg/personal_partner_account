"""add_chat_message_attachments

Revision ID: 19bb05cadd01
Revises: c4d5e6f7a8b9
Create Date: 2026-07-08 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19bb05cadd01"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("attachment_s3_key", sa.String(length=500), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_filename", sa.String(length=255), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_size", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_mime_type", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "attachment_mime_type")
    op.drop_column("chat_messages", "attachment_size")
    op.drop_column("chat_messages", "attachment_filename")
    op.drop_column("chat_messages", "attachment_s3_key")
