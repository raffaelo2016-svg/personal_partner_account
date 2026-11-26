"""ФИО сотрудника в учётной записи.

Revision ID: c1d3a5e70b22
Revises: b5e2c8a91d34
Create Date: 2026-11-26 10:10:00.000000

В обсуждении задачи вместо адреса почты показываем человеческое имя.
У партнёра имя берётся из карточки партнёра, а у сотрудника ЮРИТЕХ раньше
его не было вовсе — добавляем поле ``users.full_name``.

IF NOT EXISTS безопасен для уже существующей базы.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1d3a5e70b22"
down_revision: str | None = "b5e2c8a91d34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS full_name")
