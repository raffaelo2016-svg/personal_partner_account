"""Partner region and timezone (production chain).

Revision ID: f8a3c1d2e4b6
Revises: f7c2b8e14d90
Create Date: 2026-11-02 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8a3c1d2e4b6"
down_revision: str | None = "f7c2b8e14d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("timezone", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "timezone")
    op.drop_column("partners", "region")
