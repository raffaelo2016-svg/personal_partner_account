"""персональные учётные записи администраторов

Revision ID: 9b1c4d7e2f30
Revises: c7e4a1b9d206
Create Date: 2026-11-06 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9b1c4d7e2f30"
down_revision: str | None = "c7e4a1b9d206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: персональные данные входа ---------------------------------
    op.add_column("users", sa.Column("login", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_legacy_shared", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("users", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_login", "users", ["login"], unique=True)
    op.create_foreign_key(
        "fk_users_created_by",
        "users",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- приглашения -------------------------------------------------------
    op.create_table(
        "invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="admin"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invites_email", "invites", ["email"])
    op.create_index("ix_invites_token_hash", "invites", ["token_hash"], unique=True)

    # --- ключи первичной настройки ----------------------------------------
    op.create_table(
        "bootstrap_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bootstrap_tokens_token_hash", "bootstrap_tokens", ["token_hash"], unique=True)

    # --- журнал: детали события -------------------------------------------
    op.add_column("audit_logs", sa.Column("actor_label", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("target_label", sa.String(255), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(16), server_default="success", nullable=False),
    )
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "result")
    op.drop_column("audit_logs", "target_label")
    op.drop_column("audit_logs", "actor_label")

    op.drop_index("ix_bootstrap_tokens_token_hash", table_name="bootstrap_tokens")
    op.drop_table("bootstrap_tokens")

    op.drop_index("ix_invites_token_hash", table_name="invites")
    op.drop_index("ix_invites_email", table_name="invites")
    op.drop_table("invites")

    op.drop_constraint("fk_users_created_by", "users", type_="foreignkey")
    op.drop_index("ix_users_login", table_name="users")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "created_by")
    op.drop_column("users", "is_legacy_shared")
    op.drop_column("users", "login")
