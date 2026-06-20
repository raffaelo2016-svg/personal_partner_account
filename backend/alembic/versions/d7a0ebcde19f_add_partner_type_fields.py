"""add_partner_type_fields

Revision ID: d7a0ebcde19f
Revises: 9e1a01f76a16
Create Date: 2026-03-17 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a0ebcde19f"
down_revision: str | None = "9e1a01f76a16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("partner_type", sa.String(20), server_default="individual", nullable=False))
    op.add_column("partners", sa.Column("short_name", sa.String(255), nullable=True))
    op.add_column("partners", sa.Column("full_legal_name", sa.String(500), nullable=True))
    op.add_column("partners", sa.Column("legal_address", sa.String(500), nullable=True))
    op.add_column("partners", sa.Column("postal_address", sa.String(500), nullable=True))
    op.add_column("partners", sa.Column("kpp", sa.String(9), nullable=True))

    op.alter_column("partners", "phone", type_=sa.String(30), existing_type=sa.String(20))


def downgrade() -> None:
    op.alter_column("partners", "phone", type_=sa.String(20), existing_type=sa.String(30))

    op.drop_column("partners", "kpp")
    op.drop_column("partners", "postal_address")
    op.drop_column("partners", "legal_address")
    op.drop_column("partners", "full_legal_name")
    op.drop_column("partners", "short_name")
    op.drop_column("partners", "partner_type")
