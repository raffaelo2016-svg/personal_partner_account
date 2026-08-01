"""add Bitrix24 synchronization core

Revision ID: 50c73f9a12de
Revises: 24b7a96e5c01
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "50c73f9a12de"
down_revision: str | None = "24b7a96e5c01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bitrix_entity_maps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("local_entity_type", sa.String(length=50), nullable=False),
        sa.Column("local_entity_id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_entity_type", sa.String(length=50), nullable=False),
        sa.Column("bitrix_entity_id", sa.String(length=100), nullable=False),
        sa.Column("sync_version", sa.Integer(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["bitrix_installations.member_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "bitrix_entity_type", "bitrix_entity_id", name="uq_bitrix_entity_maps_remote"),
        sa.UniqueConstraint("member_id", "local_entity_type", "local_entity_id", name="uq_bitrix_entity_maps_local"),
    )
    op.create_index("ix_bitrix_entity_maps_member_id", "bitrix_entity_maps", ["member_id"])
    op.create_index("ix_bitrix_entity_maps_local_entity_id", "bitrix_entity_maps", ["local_entity_id"])
    op.create_index("ix_bitrix_entity_maps_verification", "bitrix_entity_maps", ["member_id", "last_verified_at"])

    op.create_table(
        "bitrix_inbound_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'completed', 'failed', 'ignored')",
            name="ck_bitrix_inbound_events_status",
        ),
        sa.ForeignKeyConstraint(["member_id"], ["bitrix_installations.member_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "event_key", name="uq_bitrix_inbound_events_key"),
    )
    op.create_index("ix_bitrix_inbound_events_member_id", "bitrix_inbound_events", ["member_id"])
    op.create_index("ix_bitrix_inbound_events_work", "bitrix_inbound_events", ["status", "created_at"])

    op.create_table(
        "bitrix_outbox_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("operation_key", sa.String(length=160), nullable=False),
        sa.Column("local_entity_type", sa.String(length=50), nullable=False),
        sa.Column("local_entity_id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_method", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("result_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'retry', 'failed')",
            name="ck_bitrix_outbox_operations_status",
        ),
        sa.ForeignKeyConstraint(["member_id"], ["bitrix_installations.member_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "operation_key", name="uq_bitrix_outbox_operation_key"),
    )
    op.create_index("ix_bitrix_outbox_operations_member_id", "bitrix_outbox_operations", ["member_id"])
    op.create_index("ix_bitrix_outbox_operations_local_entity_id", "bitrix_outbox_operations", ["local_entity_id"])
    op.create_index("ix_bitrix_outbox_operations_correlation_id", "bitrix_outbox_operations", ["correlation_id"])
    op.create_index(
        "ix_bitrix_outbox_ready",
        "bitrix_outbox_operations",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("bitrix_outbox_operations")
    op.drop_table("bitrix_inbound_events")
    op.drop_table("bitrix_entity_maps")
