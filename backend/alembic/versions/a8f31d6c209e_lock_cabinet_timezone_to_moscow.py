"""Lock the cabinet timezone to Moscow.

Revision ID: a8f31d6c209e
Revises: 6f2a9c8d1b30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8f31d6c209e"
down_revision: str | None = "6f2a9c8d1b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE system_settings SET value = 'Europe/Moscow' WHERE key = 'timezone'",
    )


def downgrade() -> None:
    # The previous arbitrary value cannot be reconstructed safely.
    pass
