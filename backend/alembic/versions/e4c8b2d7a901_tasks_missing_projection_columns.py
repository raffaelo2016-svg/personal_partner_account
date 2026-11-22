"""Repair tasks projection columns missing from the migration chain.

Revision ID: e4c8b2d7a901
Revises: f3a7c9e1b204
Create Date: 2026-11-22 11:00:00.000000

The Task ORM already uses partner_id, due_at, bitrix_imported and
bitrix_published. They exist in production, but were never added by a
migration, so a fresh database could not run the task workspace. IF NOT
EXISTS keeps this safe for the existing production schema.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4c8b2d7a901"
down_revision: str | None = "f3a7c9e1b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS partner_id UUID")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_imported BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS bitrix_published BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_partner_id ON tasks (partner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_due_at ON tasks (due_at)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'tasks_partner_id_fkey'
            ) THEN
                ALTER TABLE tasks
                    ADD CONSTRAINT tasks_partner_id_fkey
                    FOREIGN KEY (partner_id) REFERENCES partners(id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # These columns are part of the base schema used by the application and
    # production. Dropping them on downgrade would destroy live task data.
    pass
