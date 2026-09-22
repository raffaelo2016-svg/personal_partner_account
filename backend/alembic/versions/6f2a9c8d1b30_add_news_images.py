"""Add optional cover image to partner news.

Revision ID: 6f2a9c8d1b30
Revises: 5c9d3e7f0a21
"""

import sqlalchemy as sa

from alembic import op

revision: str = "6f2a9c8d1b30"
down_revision: str | None = "5c9d3e7f0a21"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("news_posts", sa.Column("image_s3_key", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("news_posts", "image_s3_key")
