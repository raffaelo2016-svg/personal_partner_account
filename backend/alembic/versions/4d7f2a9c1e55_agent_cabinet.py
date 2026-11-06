"""агентский кабинет: агенты, начисления, заявки на выплату

Revision ID: 4d7f2a9c1e55
Revises: 9b1c4d7e2f30
Create Date: 2026-11-06 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4d7f2a9c1e55"
down_revision: str | None = "9b1c4d7e2f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("requisites_recipient_type", sa.String(20), nullable=False, server_default="individual"),
        sa.Column("requisites", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("requisites_status", sa.String(20), nullable=False, server_default="empty"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agents_code", "agents", ["code"], unique=True)
    op.create_index("ix_agents_status", "agents", ["status"])

    op.create_table(
        "agent_accruals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("partner_id", sa.Uuid(), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="accrued"),
        sa.Column("reason", sa.String(100), nullable=False, server_default="procedure_started"),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("client_id", name="uq_agent_accruals_client"),
    )
    op.create_index("ix_agent_accruals_agent_id", "agent_accruals", ["agent_id"])
    op.create_index("ix_agent_accruals_partner_id", "agent_accruals", ["partner_id"])
    op.create_index("ix_agent_accruals_client_id", "agent_accruals", ["client_id"])
    op.create_index("ix_agent_accruals_status", "agent_accruals", ["status"])
    op.create_index("ix_agent_accruals_agent_status", "agent_accruals", ["agent_id", "status"])

    op.create_table(
        "agent_payout_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("period", sa.String(7), nullable=False, server_default=""),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_payout_requests_agent_id", "agent_payout_requests", ["agent_id"])
    op.create_index("ix_agent_payout_requests_status", "agent_payout_requests", ["status"])

    op.add_column("partners", sa.Column("agent_id", sa.Uuid(), nullable=True))
    op.add_column("partners", sa.Column("agent_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_partners_agent_id", "partners", ["agent_id"])
    op.create_foreign_key(
        "fk_partners_agent_id", "partners", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_partners_agent_id", "partners", type_="foreignkey")
    op.drop_index("ix_partners_agent_id", table_name="partners")
    op.drop_column("partners", "agent_linked_at")
    op.drop_column("partners", "agent_id")

    op.drop_index("ix_agent_payout_requests_status", table_name="agent_payout_requests")
    op.drop_index("ix_agent_payout_requests_agent_id", table_name="agent_payout_requests")
    op.drop_table("agent_payout_requests")

    op.drop_index("ix_agent_accruals_agent_status", table_name="agent_accruals")
    op.drop_index("ix_agent_accruals_status", table_name="agent_accruals")
    op.drop_index("ix_agent_accruals_client_id", table_name="agent_accruals")
    op.drop_index("ix_agent_accruals_partner_id", table_name="agent_accruals")
    op.drop_index("ix_agent_accruals_agent_id", table_name="agent_accruals")
    op.drop_table("agent_accruals")

    op.drop_index("ix_agents_status", table_name="agents")
    op.drop_index("ix_agents_code", table_name="agents")
    op.drop_table("agents")
