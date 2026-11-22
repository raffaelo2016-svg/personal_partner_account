"""Relax legacy NOT NULL constraints on optional task fields.

Revision ID: b8d4c2e7f901
Revises: e4c8b2d7a901
Create Date: 2026-11-22 11:15:00.000000

The ORM has allowed tasks without a client or deadline for a long time, but the
original migration chain declared both columns NOT NULL. Production already
accepts these rows; this migration removes the stale constraints for fresh
databases as well.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8d4c2e7f901"
down_revision: str | None = "e4c8b2d7a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ALTER COLUMN client_id DROP NOT NULL")
    op.execute("ALTER TABLE tasks ALTER COLUMN due_date DROP NOT NULL")


def downgrade() -> None:
    # Existing production rows may already have NULL values; restoring NOT NULL
    # would fail and is not required for the application.
    pass
