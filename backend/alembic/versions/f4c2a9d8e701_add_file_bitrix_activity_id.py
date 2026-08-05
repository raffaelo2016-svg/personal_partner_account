"""Add Bitrix24 CRM activity reference to imported files."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c2a9d8e701"
down_revision: str | None = "d2f4a6b8c901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("file_uploads", sa.Column("bitrix_activity_id", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("file_uploads", "bitrix_activity_id")
