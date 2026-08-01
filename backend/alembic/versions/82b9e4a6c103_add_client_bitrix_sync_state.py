"""add client Bitrix24 sync state

Revision ID: 82b9e4a6c103
Revises: 71ad0f1c6b33
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "82b9e4a6c103"
down_revision: str | None = "71ad0f1c6b33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("bitrix_sync_status", sa.String(length=20), nullable=False, server_default="not_scheduled"),
    )
    op.add_column("clients", sa.Column("bitrix_sync_error_code", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("bitrix_contact_id", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("bitrix_deal_id", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("bitrix_sync_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_clients_bitrix_sync_status",
        "clients",
        "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
    )
    op.create_index("ix_clients_bitrix_sync_status", "clients", ["bitrix_sync_status"])


def downgrade() -> None:
    op.drop_index("ix_clients_bitrix_sync_status", table_name="clients")
    op.drop_constraint("ck_clients_bitrix_sync_status", "clients", type_="check")
    for column in (
        "bitrix_synced_at",
        "bitrix_sync_requested_at",
        "bitrix_deal_id",
        "bitrix_contact_id",
        "bitrix_sync_error_code",
        "bitrix_sync_status",
    ):
        op.drop_column("clients", column)
