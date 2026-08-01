"""add partner Bitrix24 sync state

Revision ID: 71ad0f1c6b33
Revises: 50c73f9a12de
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "71ad0f1c6b33"
down_revision: str | None = "50c73f9a12de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "partners",
        sa.Column("bitrix_sync_status", sa.String(length=20), nullable=False, server_default="not_scheduled"),
    )
    op.add_column("partners", sa.Column("bitrix_sync_error_code", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("bitrix_partner_item_id", sa.String(length=100), nullable=True))
    op.add_column(
        "partners",
        sa.Column("bitrix_collab_status", sa.String(length=20), nullable=False, server_default="not_linked"),
    )
    op.add_column("partners", sa.Column("bitrix_collab_id", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("bitrix_chat_id", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("bitrix_root_folder_id", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("bitrix_sync_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("partners", sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_partners_bitrix_sync_status",
        "partners",
        "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed', 'conflict')",
    )
    op.create_check_constraint(
        "ck_partners_bitrix_collab_status",
        "partners",
        "bitrix_collab_status IN ('not_linked', 'binding_required', 'linked')",
    )
    op.create_index("ix_partners_bitrix_sync_status", "partners", ["bitrix_sync_status"])


def downgrade() -> None:
    op.drop_index("ix_partners_bitrix_sync_status", table_name="partners")
    op.drop_constraint("ck_partners_bitrix_collab_status", "partners", type_="check")
    op.drop_constraint("ck_partners_bitrix_sync_status", "partners", type_="check")
    for column in (
        "bitrix_synced_at",
        "bitrix_sync_requested_at",
        "bitrix_root_folder_id",
        "bitrix_chat_id",
        "bitrix_collab_id",
        "bitrix_collab_status",
        "bitrix_partner_item_id",
        "bitrix_sync_error_code",
        "bitrix_sync_status",
    ):
        op.drop_column("partners", column)
