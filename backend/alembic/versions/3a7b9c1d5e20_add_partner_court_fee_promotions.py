"""Add time-limited free-client promotions to partner court fees."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3a7b9c1d5e20"
down_revision: str | None = "f4c2a9d8e701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "partners",
        sa.Column("free_client_limit", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("partners", sa.Column("promotion_start_date", sa.Date(), nullable=True))
    op.add_column("partners", sa.Column("promotion_end_date", sa.Date(), nullable=True))

    op.add_column(
        "court_fees",
        sa.Column("base_amount", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "court_fees",
        sa.Column("discount_amount", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute("UPDATE court_fees SET base_amount = amount")


def downgrade() -> None:
    op.drop_column("court_fees", "discount_amount")
    op.drop_column("court_fees", "base_amount")
    op.drop_column("partners", "promotion_end_date")
    op.drop_column("partners", "promotion_start_date")
    op.drop_column("partners", "free_client_limit")
