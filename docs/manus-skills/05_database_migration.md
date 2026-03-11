# Skill: Create and Run Database Migration

## When to Use
When you add a new table, column, or index to the database schema.

## Full Workflow

### Step 1: Modify the model in models.py
```python
# apps/api/radd/db/models.py

class YourNewTable(Base):
    __tablename__ = "your_new_table"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = now_utc()
```

**Adding a column to existing table:**
```python
# Add to existing model class:
new_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

### Step 2: Generate migration automatically
```bash
cd apps/api
uv run alembic revision --autogenerate -m "add_your_new_table"
```
This creates: `alembic/versions/0004_add_your_new_table.py`

### Step 3: Review and add RLS (for new tables only)
Open the generated migration file and add RLS policy in the `upgrade()` function:

```python
def upgrade() -> None:
    # ... auto-generated table creation ...
    
    # ADD THIS for new tables with workspace_id:
    op.execute("""
        ALTER TABLE your_new_table ENABLE ROW LEVEL SECURITY;
        CREATE POLICY workspace_isolation ON your_new_table
            USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
    """)
```

And in `downgrade()`:
```python
def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS workspace_isolation ON your_new_table;")
    op.drop_table("your_new_table")
```

### Step 4: Apply migration
```bash
cd apps/api
uv run alembic upgrade head
```
Expected: `Running upgrade 0003_escalation_tickets -> 0004_add_your_new_table`

### Step 5: Verify
```bash
# Check current migration state
uv run alembic current

# Check migration history
uv run alembic history
```

---

## Rolling Back a Migration

```bash
# Rollback one step
uv run alembic downgrade -1

# Rollback to specific version
uv run alembic downgrade 0002_kb_tables

# Rollback everything
uv run alembic downgrade base
```

---

## Common Migration Patterns

### Add index
```python
op.create_index("ix_table_column", "table_name", ["column_name"])
```

### Add JSONB column with default
```python
op.add_column("table_name", 
    sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False))
```

### Add FTS (Full-Text Search) for Arabic
```python
op.execute("""
    ALTER TABLE your_table ADD COLUMN tsv tsvector;
    CREATE INDEX ix_your_table_tsv ON your_table USING gin(tsv);
    CREATE OR REPLACE FUNCTION update_tsv_your_table()
    RETURNS trigger AS $$
    BEGIN
        NEW.tsv := to_tsvector('arabic', coalesce(NEW.content, ''));
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_tsv_your_table
        BEFORE INSERT OR UPDATE ON your_table
        FOR EACH ROW EXECUTE FUNCTION update_tsv_your_table();
""")
```

---

## Troubleshooting

**"Target database is not up to date"**
```bash
uv run alembic upgrade head
```

**"Can't locate revision"**
```bash
uv run alembic history  # check what's available
uv run alembic current  # check current state
```

**Migration fails with RLS error**
→ Make sure you're connected as superuser in dev
→ Add `SET session_replication_role = replica;` temporarily if needed
