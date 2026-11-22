"""Progress of the partner training course.

Revision ID: a9c4e7f21b03
Revises: b8d4c2e7f901
Create Date: 2026-11-22 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c4e7f21b03"
down_revision: str | None = "b8d4c2e7f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_lesson_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_key", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "lesson_key"),
    )


def downgrade() -> None:
    op.drop_table("training_lesson_progress")
