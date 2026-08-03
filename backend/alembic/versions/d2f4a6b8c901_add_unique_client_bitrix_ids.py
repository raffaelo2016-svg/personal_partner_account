"""add unique client Bitrix identifiers

Revision ID: d2f4a6b8c901
Revises: c81f7a2d940e
Create Date: 2026-08-04 01:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2f4a6b8c901"
down_revision: str | None = "c81f7a2d940e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_clients_bitrix_contact_id",
        "clients",
        ["bitrix_contact_id"],
        unique=True,
        postgresql_where=sa.text("bitrix_contact_id IS NOT NULL"),
    )
    op.create_index(
        "uq_clients_bitrix_deal_id",
        "clients",
        ["bitrix_deal_id"],
        unique=True,
        postgresql_where=sa.text("bitrix_deal_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_clients_bitrix_deal_id", table_name="clients")
    op.drop_index("uq_clients_bitrix_contact_id", table_name="clients")
