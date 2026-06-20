"""cascade_delete_file_uploads

Revision ID: c3f1a2b4e567
Revises: d7a0ebcde19f
Create Date: 2026-03-31 12:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1a2b4e567"
down_revision: str | None = "d7a0ebcde19f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("file_uploads_client_id_fkey", "file_uploads", type_="foreignkey")
    op.create_foreign_key(
        "file_uploads_client_id_fkey",
        "file_uploads",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("file_uploads_client_id_fkey", "file_uploads", type_="foreignkey")
    op.create_foreign_key(
        "file_uploads_client_id_fkey",
        "file_uploads",
        "clients",
        ["client_id"],
        ["id"],
    )
