"""add_bitrix_installations

Revision ID: 24b7a96e5c01
Revises: 19bb05cadd01
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24b7a96e5c01"
down_revision: str | None = "19bb05cadd01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "bitrix_installations",
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("portal_domain", sa.String(length=255), nullable=False),
        sa.Column("client_endpoint", sa.String(length=500), nullable=False),
        sa.Column("server_endpoint", sa.String(length=500), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("application_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("installed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("member_id"),
        sa.UniqueConstraint("portal_domain"),
    )


def downgrade() -> None:
    op.drop_table("bitrix_installations")
