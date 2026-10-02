"""Add partner news and per-user reading receipts.

Revision ID: 5c9d3e7f0a21
Revises: 4b8c2d6e9f10
"""

import sqlalchemy as sa

from alembic import op

revision: str = "5c9d3e7f0a21"
down_revision: str | None = "4b8c2d6e9f10"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "news_posts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("important", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_acknowledgement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_news_posts_status_published", "news_posts", ["status", "published_at"])
    op.create_table(
        "news_receipts",
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("news_posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_news_receipts_user_id", "news_receipts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_news_receipts_user_id", table_name="news_receipts")
    op.drop_table("news_receipts")
    op.drop_index("ix_news_posts_status_published", table_name="news_posts")
    op.drop_table("news_posts")
