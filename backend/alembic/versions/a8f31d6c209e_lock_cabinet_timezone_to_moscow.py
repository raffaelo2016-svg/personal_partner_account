"""Lock the cabinet timezone to Moscow.

Revision ID: a8f31d6c209e
Revises: f4c2a9d8e701
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8f31d6c209e"
down_revision: str | None = "f4c2a9d8e701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE system_settings SET value = 'Europe/Moscow' WHERE key = 'timezone'",
    )


def downgrade() -> None:
    # The previous arbitrary value cannot be reconstructed safely.
    pass
