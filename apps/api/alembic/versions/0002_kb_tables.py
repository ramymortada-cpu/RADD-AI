"""KB tables: kb_documents, kb_chunks, response_templates

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, TSVECTOR

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── kb_documents ─────────────────────────────────────────────────────────
    op.create_table(
        "kb_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),   # faq, policy, product_info, general
        sa.Column("status", sa.String(20), server_default="draft"),  # draft, review, approved, archived
        sa.Column("language", sa.String(10), server_default="ar"),
        sa.Column("uploaded_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("parent_document_id", UUID(as_uuid=True), sa.ForeignKey("kb_documents.id"), nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kb_documents_workspace_id", "kb_documents", ["workspace_id"])
    op.create_index("ix_kb_documents_status", "kb_documents", ["workspace_id", "status"])

    # ─── kb_chunks ────────────────────────────────────────────────────────────
    op.create_table(
        "kb_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_normalized", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),   # Qdrant point ID
        sa.Column("tsv", TSVECTOR, nullable=True),                  # PostgreSQL FTS
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_kb_chunks_workspace_id", "kb_chunks", ["workspace_id"])
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    op.create_index("ix_kb_chunks_is_active", "kb_chunks", ["workspace_id", "is_active"])
    # GIN index for full-text search
    op.execute("CREATE INDEX ix_kb_chunks_tsv ON kb_chunks USING GIN(tsv)")

    # Trigger to auto-update tsv on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION kb_chunks_tsv_update() RETURNS trigger AS $$
        BEGIN
            NEW.tsv := to_tsvector('simple', coalesce(NEW.content_normalized, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER kb_chunks_tsv_trigger
        BEFORE INSERT OR UPDATE ON kb_chunks
        FOR EACH ROW EXECUTE FUNCTION kb_chunks_tsv_update();
    """)

    # ─── response_templates ───────────────────────────────────────────────────
    op.create_table(
        "response_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("intent_id", sa.String(50), nullable=False),
        sa.Column("dialect", sa.String(20), nullable=False),        # gulf, egyptian, msa
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("parameters", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "intent_id", "dialect", name="uq_templates_workspace_intent_dialect"),
    )
    op.create_index("ix_response_templates_workspace_id", "response_templates", ["workspace_id"])

    # ─── RLS for new tables ───────────────────────────────────────────────────
    for table in ["kb_documents", "kb_chunks", "response_templates"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY workspace_isolation ON {table}
            USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid)
        """)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS kb_chunks_tsv_trigger ON kb_chunks")
    op.execute("DROP FUNCTION IF EXISTS kb_chunks_tsv_update()")
    for table in ["response_templates", "kb_chunks", "kb_documents"]:
        op.drop_table(table)
