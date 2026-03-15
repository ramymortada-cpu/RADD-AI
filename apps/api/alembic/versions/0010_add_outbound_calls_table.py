"""add outbound_calls table

Revision ID: 0010
Revises: 0009_shopify_support
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010"
down_revision = "0009_shopify_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbound_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("order_id", sa.String(100), nullable=False),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("store_name", sa.String(200), nullable=True),
        sa.Column("call_type", sa.String(50), nullable=False, server_default="order_confirmation"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("call_sid", sa.String(100), nullable=True),
        sa.Column("customer_response", sa.String(10), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_channel", sa.String(30), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("ALTER TABLE outbound_calls ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY workspace_isolation ON outbound_calls
        USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid)
    """)
    op.execute("ALTER TABLE outbound_calls FORCE ROW LEVEL SECURITY")

    op.create_index("ix_outbound_calls_workspace_status", "outbound_calls", ["workspace_id", "status"])
    op.create_index("ix_outbound_calls_order_id", "outbound_calls", ["order_id"])
    op.create_index("ix_outbound_calls_call_sid", "outbound_calls", ["call_sid"])


def downgrade() -> None:
    op.drop_table("outbound_calls")
