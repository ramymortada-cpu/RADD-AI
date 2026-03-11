"""Escalation events + tickets tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── escalation_events ────────────────────────────────────────────────────
    op.create_table(
        "escalation_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("trigger_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("escalation_type", sa.String(20), nullable=False),   # hard, soft, manual, system
        sa.Column("reason", sa.String(50), nullable=True),             # low_confidence, angry, complex, etc.
        sa.Column("confidence_at_escalation", sa.Numeric(4, 3), nullable=True),
        sa.Column("context_package", JSONB, nullable=False, server_default="{}"),
        sa.Column("assigned_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),  # pending, accepted, resolved, expired
        sa.Column("rag_draft", sa.Text, nullable=True),                # soft escalation draft response
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_escalation_events_workspace_id", "escalation_events", ["workspace_id"])
    op.create_index("ix_escalation_events_status", "escalation_events", ["workspace_id", "status"])
    op.create_index("ix_escalation_events_conversation_id", "escalation_events", ["conversation_id"])

    # ─── tickets ──────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("assigned_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),     # open, in_progress, waiting, resolved, closed
        sa.Column("priority", sa.String(20), server_default="medium"), # low, medium, high, urgent
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tickets_workspace_id", "tickets", ["workspace_id"])
    op.create_index("ix_tickets_status", "tickets", ["workspace_id", "status"])
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])

    # ─── RLS ──────────────────────────────────────────────────────────────────
    for table in ["escalation_events", "tickets"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY workspace_isolation ON {table}
            USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid)
        """)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in ["tickets", "escalation_events"]:
        op.drop_table(table)
