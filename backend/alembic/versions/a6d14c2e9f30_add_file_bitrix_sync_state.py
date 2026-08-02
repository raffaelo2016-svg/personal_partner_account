"""add file Bitrix24 sync state

Revision ID: a6d14c2e9f30
Revises: 93c0d5b7e214
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6d14c2e9f30"
down_revision: str | None = "93c0d5b7e214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("file_uploads", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "file_uploads",
        sa.Column("bitrix_sync_status", sa.String(length=20), nullable=False, server_default="not_scheduled"),
    )
    op.add_column("file_uploads", sa.Column("bitrix_sync_error_code", sa.String(length=100), nullable=True))
    op.add_column("file_uploads", sa.Column("bitrix_timeline_comment_id", sa.String(length=100), nullable=True))
    op.add_column("file_uploads", sa.Column("bitrix_disk_file_id", sa.String(length=100), nullable=True))
    op.add_column("file_uploads", sa.Column("bitrix_sync_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("file_uploads", sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_file_uploads_bitrix_sync_status",
        "file_uploads",
        "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
    )
    op.create_index("ix_file_uploads_bitrix_sync_status", "file_uploads", ["bitrix_sync_status"])
    op.create_index(
        "uq_file_uploads_client_content_sha256",
        "file_uploads",
        ["client_id", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("content_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_file_uploads_client_content_sha256", table_name="file_uploads")
    op.drop_index("ix_file_uploads_bitrix_sync_status", table_name="file_uploads")
    op.drop_constraint("ck_file_uploads_bitrix_sync_status", "file_uploads", type_="check")
    for column in (
        "bitrix_synced_at",
        "bitrix_sync_requested_at",
        "bitrix_disk_file_id",
        "bitrix_timeline_comment_id",
        "bitrix_sync_error_code",
        "bitrix_sync_status",
        "content_sha256",
    ):
        op.drop_column("file_uploads", column)
