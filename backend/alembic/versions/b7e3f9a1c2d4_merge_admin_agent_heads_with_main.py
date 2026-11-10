"""merge admin/agent heads with main

Revision ID: b7e3f9a1c2d4
Revises: 4d7f2a9c1e55, c3e9a1f4b872
Create Date: 2026-11-10 20:22:50.630734

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b7e3f9a1c2d4"
down_revision: tuple[str, str] = ("4d7f2a9c1e55", "c3e9a1f4b872")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
