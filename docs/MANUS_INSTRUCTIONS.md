# Manus Agent Instructions — Radd AI Platform

## Project Identity
You are working on **Radd (رَدّ)**, an Arabic-first AI customer service platform for Saudi e-commerce merchants. The platform integrates with WhatsApp Business API and uses RAG (Retrieval-Augmented Generation) with dialect-aware Arabic NLP.

**GitHub:** https://github.com/ramymortada-cpu/RADD-AI  
**Stack:** Python 3.12 (FastAPI) + TypeScript (Next.js 15) + PostgreSQL 16 + Redis 7 + Qdrant 1.12

---

## Project Structure (Critical to Understand)

```
radd/
├── apps/api/radd/          ← FastAPI backend (Python)
│   ├── pipeline/           ← Core NLP (normalizer→dialect→intent→RAG→verify→guardrails)
│   ├── webhooks/           ← WhatsApp webhook receiver
│   ├── knowledge/          ← KB document management
│   ├── escalation/         ← Agent escalation workflow
│   ├── conversations/      ← Conversation management API
│   ├── websocket/          ← Real-time WebSocket notifications
│   ├── actions/            ← Salla e-commerce API integration
│   ├── admin/              ← KPI analytics + settings + users
│   ├── auth/               ← JWT + RBAC (owner/admin/agent/reviewer)
│   └── db/                 ← SQLAlchemy models + RLS sessions
├── apps/api/workers/       ← Background workers (message + kb_indexer)
├── apps/api/alembic/       ← Database migrations (3 files)
├── apps/web/               ← Next.js 15 RTL Arabic dashboard
├── infrastructure/         ← Docker, Nginx, docker-compose
├── .github/workflows/      ← CI/CD pipeline
└── docs/                   ← Technical docs + handover
```

---

## Environment Setup (Always Do First)

```bash
# Step 1: Install Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Step 2: Install Node package manager
npm install -g pnpm

# Step 3: Install all dependencies
cd apps/api && uv sync
cd apps/web && pnpm install

# Step 4: Copy and configure environment
cp .env.example .env
# REQUIRED minimum fields:
# DATABASE_URL=postgresql+asyncpg://...
# REDIS_URL=redis://...
# OPENAI_API_KEY=sk-...
# SECRET_KEY=<random 64 chars>
# JWT_SECRET_KEY=<different random 64 chars>

# Step 5: Start local services
docker compose -f infrastructure/docker-compose.yml up -d

# Step 6: Run migrations
cd apps/api && uv run alembic upgrade head

# Step 7: Seed test data
cd apps/api && uv run python scripts/seed.py
```

**Default test credentials after seed:**
- Workspace slug: `demo`
- Email: `owner@demo.com`  
- Password: `Demo1234!`

---

## Running the Application

```bash
# Terminal 1: API server
cd apps/api && uv run uvicorn radd.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Message worker
cd apps/api && uv run python -m workers.message_worker

# Terminal 3: Frontend
cd apps/web && pnpm dev

# API docs: http://localhost:8000/docs
# Dashboard: http://localhost:3000
```

Or use the Makefile shortcuts:
```bash
make api     # FastAPI on :8000
make worker  # Message worker
make web     # Next.js on :3000
```

---

## Critical Architecture Rules (Never Violate)

### 1. Database Sessions MUST use workspace_id
```python
# CORRECT — always pass workspace_id to get_db_session
async with get_db_session(workspace_id) as db:
    result = await db.execute(select(Model))

# WRONG — missing workspace_id means RLS returns 0 rows silently
async with get_db_session() as db:  # ← BUG
    result = await db.execute(select(Model))
```

### 2. Pipeline Confidence Routing (never change thresholds without testing)
```
C_min = min(C_intent, C_retrieval, C_verify)
≥ 0.85 → auto_rag       (AI responds directly)
≥ 0.60 → escalated_soft  (AI drafts, agent reviews)
< 0.60 → escalated_hard  (agent takes over immediately)
```

### 3. All new routers must be registered in main.py
```python
# apps/api/radd/main.py
app.include_router(your_router, prefix="/api/v1")
```

### 4. Every new DB table needs RLS policy
```sql
-- In migration file:
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON your_table
    USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
```

### 5. Async everywhere in backend
```python
# CORRECT
async def handler():
    result = await db.execute(...)
    response = await httpx_client.get(...)

# WRONG — blocks the event loop
def handler():
    result = requests.get(...)  # ← never use requests in FastAPI
```

---

## Adding New Features (Step-by-step)

### Adding a new API endpoint:
1. Create schema in `radd/{module}/schemas.py` (Pydantic models)
2. Create service in `radd/{module}/service.py` (business logic)
3. Create router in `radd/{module}/router.py` (FastAPI routes)
4. Register router in `radd/main.py`
5. Add API function in `apps/web/lib/api.ts`

### Adding a new DB table:
1. Add SQLAlchemy model in `radd/db/models.py`
2. Create migration: `cd apps/api && uv run alembic revision --autogenerate -m "table_name"`
3. Add RLS policy to migration file
4. Run: `uv run alembic upgrade head`

### Adding a new intent to NLP:
1. Add keyword list in `radd/pipeline/intent.py`
2. Add templates (3 dialects) in `radd/pipeline/templates.py`
3. Run benchmark: `uv run python scripts/benchmark.py` (must stay ≥ 80%)

---

## Testing

```bash
# Run all backend tests
cd apps/api && uv run pytest tests/ -v

# Run NLP benchmark (must achieve ≥ 80% — currently 95%)
cd apps/api && uv run python scripts/benchmark.py

# Run specific test file
uv run pytest tests/test_arabic.py -v
uv run pytest tests/test_guardrails.py -v

# Run with coverage
uv run pytest tests/ --cov=radd --cov-report=term-missing
```

---

## Key Files Quick Reference

| Task | File |
|------|------|
| Change confidence thresholds | `.env` → `CONFIDENCE_AUTO_THRESHOLD` |
| Add new Arabic keywords for intent | `radd/pipeline/intent.py` |
| Add new response template | `radd/pipeline/templates.py` |
| Change AI model | `.env` → `OPENAI_CHAT_MODEL` |
| Add new API endpoint | `radd/{module}/router.py` + `main.py` |
| Add new DB table | `radd/db/models.py` + new Alembic migration |
| Add new PII pattern | `radd/pipeline/guardrails.py` → `_PII_PATTERNS` |
| Change escalation logic | `radd/escalation/service.py` |
| Change webhook handling | `radd/webhooks/router.py` |
| Change worker logic | `workers/message_worker.py` |
| Change frontend page | `apps/web/app/(dashboard)/` |
| Change API client | `apps/web/lib/api.ts` |

---

## Common Debugging

### API returns 0 results from DB
→ Missing `workspace_id` in `get_db_session()` call. RLS is silently filtering everything.

### Worker not processing messages
→ Check Redis is running: `docker compose ps`
→ Check stream exists: `redis-cli XLEN messages:{workspace_id}`

### Embeddings not working
→ Check `OPENAI_API_KEY` in `.env`
→ Check Qdrant is running: `curl http://localhost:6333/healthz`

### WhatsApp webhook not receiving
→ Check `META_VERIFY_TOKEN` matches Meta Console
→ Webhook URL must be HTTPS (use ngrok for local testing)
→ Check HMAC secret: `META_APP_SECRET` in `.env`

### NLP confidence always low
→ Check KB has approved documents with embeddings
→ Check `kb_chunks.embedding_id` is not NULL after indexing
→ Run: `SELECT COUNT(*) FROM kb_chunks WHERE embedding_id IS NOT NULL;`

### Frontend shows "Unauthorized"
→ Token expired → re-login
→ Check `NEXT_PUBLIC_API_URL` in `apps/web/.env.local`

---

## Deployment (Production)

```bash
# Generate lockfiles first (required for Docker)
cd apps/api && uv lock
cd apps/web && pnpm install  # generates pnpm-lock.yaml

# Build Docker images
docker build -f infrastructure/docker/Dockerfile.api -t radd-api:latest .
docker build -f infrastructure/docker/Dockerfile.worker -t radd-worker:latest .
docker build -f infrastructure/docker/Dockerfile.web -t radd-web:latest .

# Deploy with compose
docker compose -f infrastructure/docker-compose.prod.yml up -d

# Run migrations in production
docker compose -f infrastructure/docker-compose.prod.yml exec api alembic upgrade head
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `SECRET_KEY` | ✅ | App secret (64 random chars) |
| `JWT_SECRET_KEY` | ✅ | JWT signing key (different from SECRET_KEY) |
| `OPENAI_API_KEY` | ✅ | For embeddings + GPT-4.1-mini |
| `META_APP_SECRET` | ✅ | WhatsApp HMAC verification |
| `META_VERIFY_TOKEN` | ✅ | WhatsApp webhook verify token |
| `WA_PHONE_NUMBER_ID` | ✅ | WhatsApp Business phone ID |
| `WA_API_TOKEN` | ✅ | WhatsApp Cloud API token |
| `SALLA_CLIENT_ID` | ⚠️ | Salla API (optional if no e-commerce) |
| `QDRANT_URL` | ⚠️ | Default: http://localhost:6333 |
| `CONFIDENCE_AUTO_THRESHOLD` | ⚠️ | Default: 0.85 |
| `CONFIDENCE_SOFT_ESCALATION_THRESHOLD` | ⚠️ | Default: 0.60 |

---

## What NOT to Do

- ❌ Never commit `.env` file to git
- ❌ Never use `requests` library in FastAPI code (use `httpx` async)
- ❌ Never call `get_db_session()` without `workspace_id` inside business logic
- ❌ Never add a DB table without RLS policy
- ❌ Never change `CONFIDENCE_AUTO_THRESHOLD` below 0.70 (hallucination risk)
- ❌ Never skip `alembic upgrade head` after adding a model
- ❌ Never hardcode Arabic text in Python files — use templates or config
- ❌ Never deploy without generating `uv.lock` and `pnpm-lock.yaml` first
