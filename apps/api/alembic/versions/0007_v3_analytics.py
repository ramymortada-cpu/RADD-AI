"""V3 Analytics: accepted_at on escalation_events, message_type on messages

Revision ID: 0007_v3_analytics
Revises: 0006_v2_features
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_v3_analytics"
down_revision = "0006_v2_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add accepted_at to escalation_events (for first-response-time metric)
    op.add_column(
        "escalation_events",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add message_type to messages (text, image, audio, etc.)
    op.add_column(
        "messages",
        sa.Column("message_type", sa.String(20), server_default="text"),
    )

    # Index for agent performance query
    try:
        op.create_index(
            "ix_escalation_events_assigned_user",
            "escalation_events",
            ["assigned_user_id", "workspace_id", "created_at"],
        )
    except Exception:
        pass  # Index may already exist


def downgrade() -> None:
    try:
        op.drop_index("ix_escalation_events_assigned_user", "escalation_events")
    except Exception:
        pass
    op.drop_column("messages", "message_type")
    op.drop_column("escalation_events", "accepted_at")
