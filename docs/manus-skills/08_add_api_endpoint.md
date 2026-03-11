# Skill: Add a New API Endpoint

## When to Use
When you need to expose new functionality via the REST API.

## Complete Example: Adding a "Search Conversations" endpoint

### Step 1: Define Pydantic schemas
```python
# apps/api/radd/conversations/schemas.py — ADD:
from pydantic import BaseModel
from typing import Optional

class ConversationSearchRequest(BaseModel):
    query: str
    status: Optional[str] = None
    limit: int = 20

class ConversationSearchResult(BaseModel):
    id: str
    customer_name: Optional[str]
    last_message_preview: str
    status: str
    relevance_score: float
```

### Step 2: Add service logic
```python
# apps/api/radd/conversations/service.py — ADD:
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import uuid

async def search_conversations(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query: str,
    status: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text search on conversation messages."""
    sql = """
        SELECT DISTINCT
            c.id,
            cu.display_name as customer_name,
            c.status,
            m.content as last_message_preview,
            ts_rank(to_tsvector('arabic', m.content), 
                    plainto_tsquery('arabic', :query)) as score
        FROM conversations c
        JOIN customers cu ON cu.id = c.customer_id
        JOIN messages m ON m.conversation_id = c.id
        WHERE c.workspace_id = :wid
          AND to_tsvector('arabic', m.content) @@ plainto_tsquery('arabic', :query)
          {status_filter}
        ORDER BY score DESC
        LIMIT :limit
    """.format(
        status_filter="AND c.status = :status" if status else ""
    )
    
    params = {"wid": str(workspace_id), "query": query, "limit": limit}
    if status:
        params["status"] = status
    
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result.fetchall()]
```

### Step 3: Add route to router
```python
# apps/api/radd/conversations/router.py — ADD:
from radd.conversations.service import search_conversations
from radd.conversations.schemas import ConversationSearchRequest

@router.post("/search")
async def search_convs(
    body: ConversationSearchRequest,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    async with get_db_session(current.workspace_id) as db:
        results = await search_conversations(
            db=db,
            workspace_id=current.workspace_id,
            query=body.query,
            status=body.status,
            limit=body.limit,
        )
    return {"items": results, "total": len(results)}
```

### Step 4: Verify router is registered in main.py
```python
# apps/api/radd/main.py — should already have:
app.include_router(conversations_router, prefix="/api/v1")
# If conversations_router not registered, add it.
```

### Step 5: Add TypeScript function in frontend API client
```typescript
// apps/web/lib/api.ts — ADD:
export type SearchResult = {
  id: string;
  customer_name: string | null;
  last_message_preview: string;
  status: string;
  relevance_score: number;
};

export const searchConversations = (query: string, status?: string) =>
  apiFetch<{ items: SearchResult[]; total: number }>("/conversations/search", {
    method: "POST",
    body: JSON.stringify({ query, status, limit: 20 }),
  });
```

### Step 6: Test the endpoint
```bash
# Get token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"workspace_slug":"demo","email":"owner@demo.com","password":"Demo1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Test the new endpoint
curl -X POST http://localhost:8000/api/v1/conversations/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "طلب متأخر", "status": "active"}'
```

---

## RBAC Reference for Endpoints

```python
from radd.auth.middleware import require_owner, require_admin, require_reviewer

# require_reviewer = owner + admin + agent + reviewer (read-only is ok)
@router.get("/something")
async def read_something(current: Annotated[CurrentUser, Depends(require_reviewer)]):

# require_admin = owner + admin only
@router.post("/something")  
async def create_something(current: Annotated[CurrentUser, Depends(require_admin)]):

# require_owner = owner only
@router.delete("/something")
async def delete_something(current: Annotated[CurrentUser, Depends(require_owner)]):
```

---

## Common Patterns

### Paginated list endpoint
```python
@router.get("/items")
async def list_items(
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    async with get_db_session(current.workspace_id) as db:
        q = select(YourModel).where(YourModel.workspace_id == current.workspace_id)
        if status:
            q = q.where(YourModel.status == status)
        
        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        items = (await db.execute(q.offset((page-1)*page_size).limit(page_size))).scalars().all()
    
    return {"items": items, "total": total, "page": page, "page_size": page_size}
```
