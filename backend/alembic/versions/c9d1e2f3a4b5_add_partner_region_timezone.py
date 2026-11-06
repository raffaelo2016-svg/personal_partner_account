"""Partner region and timezone.

Revision ID: c9d1e2f3a4b5
Revises: b6e2f4a90c17
Create Date: 2026-11-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d1e2f3a4b5"
down_revision: str | None = "b6e2f4a90c17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column("partners", sa.Column("timezone", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "timezone")
    op.drop_column("partners", "region")
