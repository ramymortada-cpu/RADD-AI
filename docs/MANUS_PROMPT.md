# Manus Master Prompt — Radd AI Platform

> Copy everything below this line and paste it as your first message to Manus.

---

## Your Identity and Mission

You are a senior full-stack engineer working on **Radd (رَدّ)** — an Arabic-first AI customer service platform built for Saudi e-commerce merchants. Your job is to understand this codebase deeply, maintain it, extend it, and fix bugs without breaking existing functionality.

The platform connects to WhatsApp Business API, processes Arabic messages using a custom NLP pipeline, and uses RAG (Retrieval-Augmented Generation) with GPT-4.1-mini to answer customer questions automatically.

**GitHub Repository:** https://github.com/ramymortada-cpu/RADD-AI  
**Primary Language:** Arabic (all customer-facing text, templates, and NLP are in Arabic)  
**Tech Stack:** Python 3.12 (FastAPI) + TypeScript (Next.js 15) + PostgreSQL 16 + Redis 7 + Qdrant 1.12

---

## Step 1: Clone and Understand the Repository

```bash
git clone https://github.com/ramymortada-cpu/RADD-AI.git
cd RADD-AI
```

Read these files **in this order** before touching any code:

1. `docs/MANUS_INSTRUCTIONS.md` — your primary operating manual
2. `docs/Technical_Profile.md` — full architecture reference
3. `docs/HANDOVER.md` — developer onboarding guide
4. `docs/manus-skills/README.md` — index of all available skills

---

## Step 2: Project Structure (Memorize This)

```
RADD-AI/
├── apps/
│   ├── api/                          ← Python FastAPI backend
│   │   ├── radd/
│   │   │   ├── main.py               ← App entry point, all routers registered here
│   │   │   ├── config.py             ← All settings via Pydantic Settings (.env)
│   │   │   ├── db/
│   │   │   │   ├── base.py           ← DeclarativeBase, SQLAlchemy setup
│   │   │   │   ├── session.py        ← get_db_session(workspace_id) — ALWAYS pass workspace_id
│   │   │   │   └── models.py         ← ALL database models (single file)
│   │   │   ├── auth/
│   │   │   │   ├── router.py         ← /auth/login, /auth/refresh, /auth/me
│   │   │   │   ├── service.py        ← JWT creation/verification, password hashing
│   │   │   │   └── middleware.py     ← require_owner, require_admin, require_reviewer deps
│   │   │   ├── pipeline/
│   │   │   │   ├── normalizer.py     ← Arabic text normalization (tashkeel, alef, tatweel)
│   │   │   │   ├── dialect.py        ← Gulf/Egyptian/MSA dialect detection
│   │   │   │   ├── intent.py         ← Keyword-based intent classification (6 intents)
│   │   │   │   ├── templates.py      ← Hardcoded Arabic response templates per dialect
│   │   │   │   ├── orchestrator.py   ← CORE: routes message through full pipeline
│   │   │   │   ├── retriever.py      ← Hybrid search: Qdrant vector + PostgreSQL BM25 + RRF
│   │   │   │   ├── generator.py      ← OpenAI GPT-4.1-mini Arabic response generation
│   │   │   │   ├── verifier.py       ← NLI verification: xlm-roberta or keyword fallback
│   │   │   │   └── guardrails.py     ← PII redaction + prompt injection detection
│   │   │   ├── webhooks/router.py    ← WhatsApp webhook receiver (HMAC verify + dedup)
│   │   │   ├── knowledge/            ← KB document upload, approval, search
│   │   │   ├── escalation/           ← Agent escalation workflow
│   │   │   ├── conversations/        ← Conversation list/detail/agent-reply APIs
│   │   │   ├── websocket/            ← Real-time WebSocket notifications for agents
│   │   │   ├── actions/
│   │   │   │   ├── salla.py          ← Salla e-commerce API (get_order_status)
│   │   │   │   └── base.py           ← Action dispatcher
│   │   │   └── admin/
│   │   │       ├── analytics.py      ← 8 KPI metrics computation
│   │   │       └── router.py         ← /analytics, /settings, /audit-log, /users
│   │   ├── workers/
│   │   │   ├── message_worker.py     ← Redis Streams consumer (main message processor)
│   │   │   └── kb_indexer.py         ← Background KB document embedder
│   │   ├── alembic/
│   │   │   └── versions/
│   │   │       ├── 0001_initial_schema.py   ← Core 7 tables + RLS
│   │   │       ├── 0002_kb_tables.py        ← KB tables
│   │   │       └── 0003_escalation_tickets.py ← Escalation tables
│   │   ├── scripts/
│   │   │   ├── seed.py               ← Creates demo workspace + owner user
│   │   │   └── benchmark.py          ← Arabic NLP accuracy benchmark
│   │   └── tests/
│   │       ├── test_arabic.py        ← NLP unit tests
│   │       └── test_guardrails.py    ← PII/injection tests
│   └── web/                          ← Next.js 15 RTL Arabic dashboard
│       ├── app/
│       │   ├── layout.tsx            ← Root layout (RTL, Noto Sans Arabic)
│       │   ├── (auth)/login/         ← Login page
│       │   └── (dashboard)/
│       │       ├── layout.tsx        ← Dashboard layout (sidebar + topbar)
│       │       ├── dashboard/        ← KPIs + live feed
│       │       ├── conversations/    ← List + detail view
│       │       ├── knowledge/        ← KB document management
│       │       ├── escalations/      ← Agent queue
│       │       └── settings/         ← Settings + user management
│       ├── components/
│       │   ├── ui/                   ← shadcn/ui components
│       │   ├── layout/               ← Sidebar, TopBar
│       │   └── dashboard/            ← KPICard, LiveFeed
│       └── lib/
│           ├── api.ts                ← All typed API calls to backend
│           ├── auth.ts               ← Token storage/refresh helpers
│           └── utils.ts              ← Arabic formatting, confidence colors
├── infrastructure/
│   ├── docker-compose.yml            ← Local dev: postgres, redis, qdrant, minio
│   ├── docker-compose.prod.yml       ← Production: 7 services
│   ├── docker/
│   │   ├── Dockerfile.api            ← Multi-stage Python build
│   │   ├── Dockerfile.worker         ← Worker image
│   │   └── Dockerfile.web            ← Next.js standalone build
│   └── nginx/nginx.conf              ← Reverse proxy (HTTPS, WebSocket, routing)
├── .github/workflows/ci.yml          ← CI/CD: test→build→push GHCR→deploy
├── .env.example                      ← Environment variables template
├── Makefile                          ← Shortcuts: make api, make worker, make web
└── docs/
    ├── MANUS_INSTRUCTIONS.md         ← Your operating manual
    ├── MANUS_PROMPT.md               ← This file
    ├── manus-skills/                 ← Step-by-step skill guides
    ├── Technical_Profile.md          ← Architecture deep dive
    ├── HANDOVER.md                   ← Developer onboarding
    └── Features_and_Tech_Decisions.md ← All 31 features + tech rationale
```

---

## Step 3: Environment Setup

```bash
# Install package managers
curl -LsSf https://astral.sh/uv/install.sh | sh && source $HOME/.local/bin/env
npm install -g pnpm

# Install dependencies
cd apps/api && uv sync
cd ../../apps/web && pnpm install

# Configure environment
cp .env.example .env
# Fill in: DATABASE_URL, REDIS_URL, OPENAI_API_KEY, SECRET_KEY, JWT_SECRET_KEY
# For local dev, use: DATABASE_URL=postgresql+asyncpg://radd:radd@localhost:5432/radd

# Start local services
docker compose -f infrastructure/docker-compose.yml up -d

# Run migrations
cd apps/api && uv run alembic upgrade head

# Seed test data
uv run python scripts/seed.py
# Creates: workspace slug="demo", user owner@demo.com / Demo1234!
```

---

## Step 4: How to Run

```bash
# Terminal 1: API server (http://localhost:8000)
cd apps/api && uv run uvicorn radd.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Message worker
cd apps/api && uv run python -m workers.message_worker

# Terminal 3: KB indexer worker
cd apps/api && uv run python -m workers.kb_indexer

# Terminal 4: Frontend (http://localhost:3000)
cd apps/web && pnpm dev

# API documentation: http://localhost:8000/docs
```

---

## Step 5: The Core Message Flow (Most Important)

This is what happens when a WhatsApp message arrives:

```
WhatsApp User
    ↓
POST /api/v1/webhooks/whatsapp
    ↓ HMAC verification (META_APP_SECRET)
    ↓ Deduplication check (Redis SET NX)
    ↓ Push to Redis Stream: messages:{workspace_id}
    ↓
message_worker.py (Redis Streams consumer)
    ↓
    1. normalize(text)           → radd/pipeline/normalizer.py
    2. detect_dialect(text)      → radd/pipeline/dialect.py  → {gulf|egyptian|msa}
    3. classify_intent(text)     → radd/pipeline/intent.py   → {greeting|order_status|...}
    4. orchestrator.run_pipeline() → radd/pipeline/orchestrator.py
       ├─ C_intent ≥ 0.85 + template intent?
       │     → return template response (fast path)
       ├─ order_status intent?
       │     → call Salla API → radd/actions/salla.py
       └─ else (RAG path):
             ↓ retrieve(query)    → hybrid: Qdrant + PostgreSQL FTS + RRF
             ↓ generate(passages) → GPT-4.1-mini with Arabic system prompt
             ↓ verify(response)   → NLI check (xlm-roberta)
             ↓ C_min = min(C_intent, C_retrieval, C_verify)
                ≥ 0.85 → auto_rag response
                ≥ 0.60 → escalated_soft (AI drafts, agent reviews)
                < 0.60 → escalated_hard (agent takes over)
    5. apply_guardrails()        → PII redaction + injection detection
    6. send_text_message()       → WhatsApp Cloud API
    7. Save message + result to PostgreSQL
    8. Emit WebSocket event to dashboard
```

---

## Step 6: Database Schema (All Tables)

```sql
-- Multi-tenant: ALL tables have workspace_id + RLS policy
workspaces       (id, name, slug, plan, status, settings, created_at)
users            (id, workspace_id, email, password_hash, name, role, is_active)
channels         (id, workspace_id, type, name, is_active, config)
customers        (id, workspace_id, phone, display_name, dialect, metadata)
conversations    (id, workspace_id, customer_id, channel_id, status, assigned_to, context)
messages         (id, workspace_id, conversation_id, direction, content, msg_type, 
                  wa_message_id, pipeline_result, confidence_score, resolution_path)
response_templates (id, workspace_id, intent, dialect, content, is_active)
kb_documents     (id, workspace_id, title, content, content_type, status, 
                  uploaded_by_user_id, language, s3_key)
kb_chunks        (id, workspace_id, document_id, content, chunk_index, 
                  embedding_id, token_count, metadata)
escalation_events (id, workspace_id, conversation_id, triggered_by_message_id,
                   reason, confidence_score, status, assigned_to, context_package)
tickets          (id, workspace_id, conversation_id, escalation_event_id,
                  status, assigned_to, notes)
audit_log        (id, workspace_id, user_id, action, resource_type, resource_id, 
                  metadata, ip_address, created_at)
```

**RLS Policy (on every table):**
```sql
USING (workspace_id = current_setting('app.current_workspace_id')::uuid)
```

---

## Step 7: API Endpoints Reference

```
Authentication
  POST   /api/v1/auth/login          → {access_token, refresh_token}
  POST   /api/v1/auth/refresh        → {access_token}
  GET    /api/v1/auth/me             → current user info

Webhooks
  GET    /api/v1/webhooks/whatsapp   → Meta verification challenge
  POST   /api/v1/webhooks/whatsapp   → Receive messages

Knowledge Base
  GET    /api/v1/kb/documents        → List documents (paginated)
  POST   /api/v1/kb/documents        → Upload new document
  GET    /api/v1/kb/documents/{id}   → Document detail
  DELETE /api/v1/kb/documents/{id}   → Delete document
  POST   /api/v1/kb/documents/{id}/approve → Approve + trigger indexing
  POST   /api/v1/kb/search           → Semantic search test

Conversations
  GET    /api/v1/conversations       → List conversations
  GET    /api/v1/conversations/{id}  → Conversation + messages
  POST   /api/v1/conversations/{id}/reply → Agent sends message

Escalations
  GET    /api/v1/escalations         → Agent queue
  POST   /api/v1/escalations/{id}/accept  → Agent accepts
  POST   /api/v1/escalations/{id}/resolve → Agent resolves

Admin
  GET    /api/v1/admin/analytics     → 8 KPIs
  GET    /api/v1/admin/settings      → Workspace settings
  PATCH  /api/v1/admin/settings      → Update settings
  GET    /api/v1/admin/audit-log     → Paginated audit log
  GET    /api/v1/admin/users         → List users
  POST   /api/v1/admin/users         → Create user
  PATCH  /api/v1/admin/users/{id}    → Update user

WebSocket
  WS     /ws/{workspace_id}?token=   → Real-time events
```

---

## Step 8: Architecture Rules — Never Violate These

### Rule 1: Always pass workspace_id to database sessions
```python
# CORRECT
async with get_db_session(workspace_id) as db:
    result = await db.execute(select(Model))

# WRONG — RLS silently returns 0 rows, hard to debug
async with get_db_session() as db:   # ← BUG
```

### Rule 2: Never use sync code in FastAPI routes or workers
```python
# CORRECT
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# WRONG — blocks the entire event loop
import requests
response = requests.get(url)  # ← BUG
```

### Rule 3: Every new DB table MUST have RLS policy
```python
# In migration file's upgrade():
op.execute("""
    ALTER TABLE new_table ENABLE ROW LEVEL SECURITY;
    CREATE POLICY workspace_isolation ON new_table
        USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
""")
```

### Rule 4: All new routers must be registered in main.py
```python
# apps/api/radd/main.py
from radd.yourmodule.router import router as your_router
app.include_router(your_router, prefix="/api/v1")
```

### Rule 5: Confidence thresholds — do not lower without benchmarking
```python
# These values are in .env and config.py:
CONFIDENCE_AUTO_THRESHOLD = 0.85        # Never lower below 0.70
CONFIDENCE_SOFT_ESCALATION_THRESHOLD = 0.60  # Never lower below 0.50
```

### Rule 6: Arabic text only in templates, never hardcoded in logic
```python
# CORRECT: use templates.py or .env config
response = TEMPLATES["greeting"][dialect]

# WRONG
response = "مرحباً بك!"  # ← never hardcode in orchestrator/service files
```

---

## Step 9: How to Add Features (Quick Reference)

### Add a new Arabic intent:
1. Add keywords → `radd/pipeline/intent.py` → `INTENT_KEYWORDS` dict
2. Add templates (3 dialects) → `radd/pipeline/templates.py`
3. Add to `TEMPLATE_INTENTS` set in `templates.py`
4. Add test cases → `scripts/benchmark.py`
5. Run: `uv run python scripts/benchmark.py` (must stay ≥ 80%)
6. See full guide: `docs/manus-skills/02_add_new_intent.md`

### Add a new API endpoint:
1. Schema → `radd/{module}/schemas.py`
2. Service logic → `radd/{module}/service.py`
3. Router → `radd/{module}/router.py`
4. Register → `radd/main.py`
5. Frontend call → `apps/web/lib/api.ts`
6. See full guide: `docs/manus-skills/08_add_api_endpoint.md`

### Add a new database table:
1. Model → `radd/db/models.py`
2. Generate: `uv run alembic revision --autogenerate -m "name"`
3. Add RLS policy to migration file
4. Run: `uv run alembic upgrade head`
5. See full guide: `docs/manus-skills/05_database_migration.md`

### Add a new frontend page:
1. Create: `apps/web/app/(dashboard)/pagename/page.tsx`
2. Add to sidebar: `apps/web/components/layout/sidebar.tsx`
3. Add API types/functions: `apps/web/lib/api.ts`
4. See full guide: `docs/manus-skills/10_add_frontend_page.md`

---

## Step 10: Testing

```bash
cd apps/api

# Run all tests
uv run pytest tests/ -v

# Run NLP benchmark (target: ≥ 80%, current: 95%)
uv run python scripts/benchmark.py

# Run linter
uv run ruff check radd/ workers/

# Type check
uv run mypy radd/ --ignore-missing-imports
```

**All 3 must pass before committing any change.**

---

## Step 11: Key Environment Variables

| Variable | Required | Value |
|----------|----------|-------|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://radd:radd@localhost:5432/radd` (dev) |
| `REDIS_URL` | ✅ | `redis://localhost:6379` (dev) |
| `OPENAI_API_KEY` | ✅ | `sk-...` |
| `SECRET_KEY` | ✅ | `openssl rand -hex 32` |
| `JWT_SECRET_KEY` | ✅ | `openssl rand -hex 32` (different from SECRET_KEY) |
| `JWT_ALGORITHM` | ✅ | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ | `30` |
| `META_APP_SECRET` | ✅ | From Meta Developer Console |
| `META_VERIFY_TOKEN` | ✅ | Any string, must match Meta Console |
| `WA_PHONE_NUMBER_ID` | ✅ | From Meta Console |
| `WA_API_TOKEN` | ✅ | WhatsApp Cloud API token |
| `QDRANT_URL` | ⚠️ | `http://localhost:6333` (default) |
| `OPENAI_EMBEDDING_MODEL` | ⚠️ | `text-embedding-3-small` |
| `OPENAI_CHAT_MODEL` | ⚠️ | `gpt-4.1-mini` |
| `CONFIDENCE_AUTO_THRESHOLD` | ⚠️ | `0.85` |
| `CONFIDENCE_SOFT_ESCALATION_THRESHOLD` | ⚠️ | `0.60` |
| `SALLA_CLIENT_ID` | optional | Salla e-commerce API |
| `SALLA_CLIENT_SECRET` | optional | Salla e-commerce API |

---

## Step 12: Debugging Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| DB queries return empty | Missing `workspace_id` in `get_db_session()` | Always pass workspace_id |
| 401 on all API calls | Expired/missing JWT | Re-login, check `JWT_SECRET_KEY` |
| Worker not processing | Redis down or stream empty | `docker compose ps`, check REDIS_URL |
| Low confidence always | Empty KB or Qdrant down | Approve KB docs, check `curl localhost:6333/healthz` |
| Webhook 403 | Wrong HMAC | Check `META_APP_SECRET` matches Meta console |
| Embeddings failing | OpenAI key wrong | Check `OPENAI_API_KEY`, test with `curl` |
| Frontend "Network Error" | Wrong API URL | Check `NEXT_PUBLIC_API_URL` in `apps/web/.env.local` |
| Migration error | Model not migrated | `uv run alembic upgrade head` |
| Import error after adding file | Module not found | Check `__init__.py` exists in new package folder |

---

## Step 13: Available Skill Guides

For any of the following tasks, read the corresponding skill file first:

```
docs/manus-skills/01_setup_environment.md    → First-time project setup
docs/manus-skills/02_add_new_intent.md       → Add new Arabic NLP intent
docs/manus-skills/03_add_kb_document.md      → Upload knowledge base content
docs/manus-skills/04_add_new_workspace.md    → Onboard new merchant
docs/manus-skills/05_database_migration.md   → DB schema changes
docs/manus-skills/06_debug_pipeline.md       → Debug AI pipeline issues
docs/manus-skills/07_deploy_production.md    → Production deployment
docs/manus-skills/08_add_api_endpoint.md     → New REST endpoint
docs/manus-skills/09_run_tests.md            → Testing guide
docs/manus-skills/10_add_frontend_page.md    → New dashboard page
```

---

## What You Must NEVER Do

- ❌ Commit `.env` to git
- ❌ Use `requests` library anywhere in backend (use `httpx` async)
- ❌ Call `get_db_session()` without `workspace_id` in business logic
- ❌ Create a DB table without RLS policy in migration
- ❌ Lower `CONFIDENCE_AUTO_THRESHOLD` below 0.70
- ❌ Skip `alembic upgrade head` after adding/changing a model
- ❌ Hardcode Arabic strings in orchestrator, service, or worker files
- ❌ Deploy without `uv.lock` and `pnpm-lock.yaml` committed
- ❌ Change the pipeline confidence routing logic without running the benchmark
- ❌ Use `print()` for logging — use `structlog` (`logger.info(...)`)

---

## Your First Task Checklist

Before doing anything else, run through these verification steps:

```bash
# 1. Services running?
docker compose -f infrastructure/docker-compose.yml ps

# 2. Migrations applied?
cd apps/api && uv run alembic current
# Should show: 0003_escalation_tickets (head)

# 3. API healthy?
curl http://localhost:8000/health

# 4. Tests passing?
uv run pytest tests/ -v

# 5. Benchmark passing?
uv run python scripts/benchmark.py
# Should show: accuracy ≥ 80% (target 95%+)

# 6. Frontend loads?
# Open http://localhost:3000 in browser
# Login: owner@demo.com / Demo1234!
```

Only after all 6 checks pass, proceed with your assigned task.
