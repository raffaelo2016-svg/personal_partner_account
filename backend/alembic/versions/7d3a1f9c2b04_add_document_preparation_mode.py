"""add document preparation mode to clients

Revision ID: 7d3a1f9c2b04
Revises: 5c9d3e7f0a21
Create Date: 2026-10-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d3a1f9c2b04"
down_revision: str | None = "5c9d3e7f0a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "document_preparation_mode",
            sa.String(length=20),
            server_default="uritech",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_clients_document_preparation_mode",
        "clients",
        "document_preparation_mode IN ('uritech', 'partner')",
    )
    op.add_column(
        "clients",
        sa.Column("document_generation_data", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("clients", "document_generation_data")
    op.drop_constraint("ck_clients_document_preparation_mode", "clients", type_="check")
    op.drop_column("clients", "document_preparation_mode")
