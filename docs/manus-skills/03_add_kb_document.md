# Skill: Add Knowledge Base Document and Index It

## When to Use
When a merchant wants to add store policies, FAQs, or product information for the AI to use in answering customer questions.

## Two Methods

---

## Method A: Via API (Recommended for Production)

### Step 1: Login and get token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_slug": "demo",
    "email": "owner@demo.com",
    "password": "Demo1234!"
  }'
# Save the access_token from response
TOKEN="eyJ..."
```

### Step 2: Create the document
```bash
curl -X POST http://localhost:8000/api/v1/kb/documents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "سياسة الإرجاع",
    "content": "يمكن إرجاع المنتجات خلال 14 يوماً من تاريخ الاستلام بشرط أن تكون بحالتها الأصلية...",
    "content_type": "text/plain"
  }'
# Save the document id from response
DOC_ID="uuid-here"
```

### Step 3: Approve the document (triggers auto-indexing)
```bash
curl -X POST http://localhost:8000/api/v1/kb/documents/$DOC_ID/approve \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Wait for indexing to complete
The `kb_indexer` worker handles indexing automatically. Check status:
```bash
curl http://localhost:8000/api/v1/kb/documents/$DOC_ID \
  -H "Authorization: Bearer $TOKEN"
# status should change to "approved" after indexing
```

---

## Method B: Via Script (Bulk import)

### Create a Python script
```python
# scripts/import_kb.py
import asyncio
from radd.db.session import get_db_session
from radd.db.models import KBDocument
import uuid

WORKSPACE_ID = uuid.UUID("your-workspace-id")
ADMIN_USER_ID = uuid.UUID("your-admin-user-id")

DOCUMENTS = [
    {
        "title": "سياسة الإرجاع",
        "content": """
        يمكن إرجاع المنتجات خلال 14 يوماً من تاريخ الاستلام.
        شروط الإرجاع:
        - يجب أن يكون المنتج بحالته الأصلية وغير مستخدم
        - يجب الاحتفاظ بالفاتورة الأصلية
        - لا يُقبل إرجاع المنتجات الغذائية والعطور
        """,
        "content_type": "text/plain",
    },
]

async def import_docs():
    async with get_db_session(WORKSPACE_ID) as db:
        for doc_data in DOCUMENTS:
            doc = KBDocument(
                workspace_id=WORKSPACE_ID,
                uploaded_by_user_id=ADMIN_USER_ID,
                status="review",
                language="ar",
                **doc_data,
            )
            db.add(doc)
        await db.flush()
        print(f"Imported {len(DOCUMENTS)} documents")

asyncio.run(import_docs())
```

Run it:
```bash
cd apps/api && uv run python scripts/import_kb.py
```

---

## Verification

### Check document is indexed
```sql
-- Run in PostgreSQL
SELECT d.title, d.status, COUNT(c.id) as chunks, 
       COUNT(CASE WHEN c.embedding_id IS NOT NULL THEN 1 END) as indexed_chunks
FROM kb_documents d
LEFT JOIN kb_chunks c ON c.document_id = d.id
WHERE d.workspace_id = 'your-workspace-id'
GROUP BY d.id, d.title, d.status;
```

### Test retrieval works
```bash
curl -X POST http://localhost:8000/api/v1/kb/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "ما هي سياسة الإرجاع؟", "top_k": 3}'
```

## Common Issues

**"No embeddings found" after approval:**
→ Check `kb_indexer` worker is running
→ Check `OPENAI_API_KEY` is set correctly
→ Check Qdrant is running: `curl http://localhost:6333/healthz`

**Document stuck in "review" status:**
→ Manually approve via API or dashboard
→ Check worker logs for errors
