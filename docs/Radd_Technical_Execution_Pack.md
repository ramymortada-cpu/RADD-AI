# TECHNICAL EXECUTION PACK — CURSOR IMPLEMENTATION GUIDE

**Purpose:** Everything a developer needs to build this product in Cursor. No strategy. No theory. Just what to build, how to structure it, and in what order.

**Governing documents:** Founder Control Document v2, Founder Execution Plan v1
**Source of truth:** TECH-STACK-MEMO-v1, TECHNICAL-ARCHITECTURE-v1, DATA-MODEL-v1, ENGINEERING-EXECUTION-PLAN-v1, API-INTEGRATION-SPEC-v1, PRD-v1, DEPLOYMENT-DEVOPS-BLUEPRINT-v1

Version 1.0 | March 2026

---

## 1. MVP SCOPE

### 1.1 Exact MVP Definition

A WhatsApp bot that receives Arabic customer messages, classifies intent, responds from a merchant's knowledge base (template or RAG), escalates to a human with full context when uncertain, and logs everything in an RTL admin dashboard.

### 1.2 In Scope

| Component | Details |
|-----------|---------|
| **WhatsApp integration** | Receive via Meta webhook. Send via Cloud API. HMAC verification. Message deduplication. |
| **Arabic text processing** | Normalization (tashkeel, Alef/Ya, whitespace). Dialect detection v0 (rule-based Gulf/Egyptian/MSA). |
| **Intent classification** | v0: keyword + TF-IDF for 6 intents. v1 (Sprint 2): AraBERT fine-tuned. |
| **Template response engine** | 5 parameterized templates per dialect: greeting, order_status, shipping, return_policy, store_hours. |
| **RAG pipeline** | KB upload + chunking + embedding (text-embedding-3-small) + Qdrant vector search + PostgreSQL BM25 + RRF fusion + GPT-4.1-mini generation + NLI verification. |
| **Confidence routing** | `min(C_intent, C_retrieval, C_verify)`. Auto (≥0.85), soft escalation (0.60–0.84), hard escalation (<0.60). |
| **Escalation** | Hard: queue for agent + context package + WebSocket notification. Soft: AI draft + agent approves/edits. |
| **Salla integration** | get_order_status via Salla API. |
| **Admin dashboard** | Conversation viewer, KB management (CRUD + review), escalation queue, confidence settings, 8 KPI cards. RTL-first. |
| **Safety** | PII redaction (regex + NER), audit trail, RLS tenant isolation, prompt injection guards. |
| **Auth** | Custom JWT. Roles: owner, admin, agent, reviewer. RBAC middleware. |

### 1.3 Out of Scope (Do Not Build)

Web chat, email, voice. Levantine/Maghreb dialects. Assisted review mode. Advanced analytics/export. Auto KB ingestion from URLs. Callback scheduling. Agent performance metrics. Custom tenant branding. Mobile responsive admin. SOC 2 controls. Multi-region deployment.

### 1.4 What MVP Must Prove

1. Arabic AI CS responds accurately enough for merchant trust (>90% accuracy, <3% hallucination)
2. Saudi e-commerce merchants will pay ~$500/month
3. Architecture is sound (<4s P95, >99.5% uptime, zero SEV-1)

### 1.5 What MVP Must Not Try to Do

Replace human CS entirely. Handle every possible query type. Support multiple channels. Optimize for 1000+ tenants. Be pixel-perfect on every screen.

---

## 2. RECOMMENDED STACK

All decisions below are confirmed from TECH-STACK-MEMO-v1 Decision Log. These are not suggestions.

### 2.1 Stack Table

| Layer | Technology | Version | Reasoning |
|-------|-----------|---------|-----------|
| **Frontend** | Next.js + React + shadcn/ui + Tailwind CSS | 15 / 19 / latest / 4 | RTL-native via Tailwind. shadcn gives professional components. SSR for dashboard performance. |
| **Backend** | FastAPI + uvicorn + gunicorn | latest / latest | Python required for Arabic NLP ecosystem (AraBERT, CAMeL Tools, HF Transformers). FastAPI gives auto OpenAPI docs + Pydantic validation. |
| **Language** | Python 3.12 (backend) + TypeScript 5.x (frontend) | 3.12 / 5.x | Python for AI pipeline. TypeScript for UI. No polyglot backend. |
| **Database** | PostgreSQL via Neon Serverless | 16 | Standard PostgreSQL. Neon gives serverless scaling + branching for staging. RLS for tenant isolation. |
| **Cache/Queue** | Redis via Upstash | 7 | Session management + message queue (Redis Streams) + rate limiting. Upstash is serverless, cheap. |
| **Vector DB** | Qdrant (self-hosted on ECS) | 1.12 | No managed vector DB in GCC region. Self-hosted. Re-indexable from source docs. |
| **Auth** | Custom JWT + PostgreSQL RLS | — | Simple. No external auth service. JWT for API auth. RLS for data isolation. |
| **LLM** | OpenAI GPT-4.1-mini | latest | Best Arabic generation quality per cost. Swap to Jais/ALLaM if needed. |
| **Embeddings** | OpenAI text-embedding-3-small | latest | 1536 dimensions. Good Arabic performance. $0.02/1M tokens. |
| **NLI** | Cross-lingual NLI model (joeddav/xlm-roberta-large-xnli) | latest | Verifies response is grounded in source passages. |
| **Cloud** | AWS (me-south-1 Bahrain) | — | GCC data residency. PDPL compliance. 3 AZs. |
| **Compute** | ECS Fargate | — | Serverless containers. No cluster management. Cheaper than EKS ($73/mo saved). |
| **CDN** | CloudFront | — | Frontend static assets. |
| **Storage** | S3 (me-south-1) | — | KB documents, audit exports, backups. |
| **Monitoring** | Grafana Cloud (free tier) | — | Logs + metrics + dashboards. Upgrade to Pro ($29/mo) when free tier exceeded. |
| **CI/CD** | GitHub Actions | — | Lint → test → build → deploy to ECS. |
| **Package mgmt** | uv (Python) + pnpm (Node) | latest | uv is 10-100× faster than pip. pnpm is faster than npm. |
| **Migration** | Alembic | latest | SQLAlchemy-based. Reversible migrations. |
| **Testing** | pytest + Vitest + Playwright | latest | pytest for backend. Vitest for frontend unit. Playwright for E2E. |

### 2.2 What to Use Now vs Later

| Now (MVP) | Later (Post-Pilot) |
|-----------|-------------------|
| Keyword intent classifier (v0) | AraBERT fine-tuned (v1) |
| Rule-based dialect detection | ML-based dialect classifier |
| PostgreSQL FTS (BM25) | OpenSearch (if FTS quality insufficient) |
| Grafana Cloud free tier | Grafana Pro or Datadog |
| Manual tenant provisioning | Automated self-serve onboarding |
| ECS Fargate | EKS (when >5 services) |
| Neon PostgreSQL | AWS RDS (if data residency mandated) |
| Single region (Bahrain) | Multi-region (if UAE/Egypt demand) |

### 2.3 Explicitly Rejected

| Technology | Why Rejected |
|-----------|-------------|
| LangChain/LangGraph | Unnecessary abstraction. Custom pipeline is simpler and more controllable. |
| Microservices | Operational overhead kills a 1-2 person team. Modular monolith. |
| EKS/Kubernetes | $73/mo control plane + complexity. ECS Fargate does the same for MVP. |
| Supabase | No Bahrain region. |
| Firebase | No Bahrain region. Google ecosystem lock-in. |
| Vercel (for backend) | No Bahrain region for serverless functions. Frontend hosting only is possible. |

---

## 3. DATABASE SCHEMA

### 3.1 Core Entities (MVP — 12 Tables)

The full data model has 28 entities (DATA-MODEL-v1). For Sprint 1, build 7 core tables. Expand to 12 by Sprint 3. Full 19 MVP tables by Sprint 5.

#### Sprint 1 Tables (7)

```
workspaces
  id              UUID PK DEFAULT gen_random_uuid()
  name            VARCHAR(255) NOT NULL
  slug            VARCHAR(100) UNIQUE NOT NULL
  settings        JSONB DEFAULT '{}'     -- confidence thresholds, business hours, etc.
  plan            VARCHAR(20) DEFAULT 'pilot'  -- pilot, asasi, growth, enterprise
  status          VARCHAR(20) DEFAULT 'active' -- active, suspended, churned
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

users
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  email           VARCHAR(255) NOT NULL
  password_hash   VARCHAR(255) NOT NULL
  name            VARCHAR(255) NOT NULL
  role            VARCHAR(20) NOT NULL    -- owner, admin, agent, reviewer
  is_active       BOOLEAN DEFAULT true
  last_login_at   TIMESTAMPTZ
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
  UNIQUE(workspace_id, email)

customers
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  channel_identifier_hash  VARCHAR(64) NOT NULL  -- SHA-256 of phone number
  channel_type    VARCHAR(20) DEFAULT 'whatsapp'
  display_name    VARCHAR(255)           -- from WhatsApp profile
  language        VARCHAR(10)            -- detected: ar-SA, ar-EG, ar
  metadata        JSONB DEFAULT '{}'
  first_seen_at   TIMESTAMPTZ DEFAULT now()
  last_seen_at    TIMESTAMPTZ DEFAULT now()
  created_at      TIMESTAMPTZ DEFAULT now()
  UNIQUE(workspace_id, channel_identifier_hash)

channels
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  type            VARCHAR(20) NOT NULL   -- whatsapp (MVP only)
  name            VARCHAR(255)
  is_active       BOOLEAN DEFAULT true
  config          JSONB NOT NULL         -- wa_phone_number_id, wa_business_account_id, wa_api_token (ref)
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

conversations
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  customer_id     UUID FK → customers NOT NULL
  channel_id      UUID FK → channels NOT NULL
  status          VARCHAR(20) DEFAULT 'active'  -- active, waiting_agent, resolved, expired
  assigned_user_id UUID FK → users              -- NULL = unassigned
  intent          VARCHAR(50)                    -- classified intent
  dialect         VARCHAR(20)                    -- gulf, egyptian, msa, unknown
  confidence_score DECIMAL(4,3)                  -- overall min(intent, retrieval, verify)
  resolution_type VARCHAR(20)                    -- auto_template, auto_rag, escalated_hard, escalated_soft
  message_count   INTEGER DEFAULT 0
  first_message_at TIMESTAMPTZ
  last_message_at  TIMESTAMPTZ
  resolved_at     TIMESTAMPTZ
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

messages
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  conversation_id UUID FK → conversations NOT NULL
  sender_type     VARCHAR(20) NOT NULL   -- customer, system, agent
  content         TEXT NOT NULL           -- message text
  content_normalized TEXT                 -- after Arabic normalization
  external_id     VARCHAR(255)           -- WhatsApp message ID (dedup)
  confidence      JSONB                  -- {intent: 0.92, retrieval: 0.88, verify: 0.85}
  source_passages JSONB                  -- [{chunk_id, score, text_preview}]
  template_id     UUID                   -- if template response
  metadata        JSONB DEFAULT '{}'     -- delivery status, etc.
  created_at      TIMESTAMPTZ DEFAULT now()
  UNIQUE(external_id) WHERE external_id IS NOT NULL

audit_log
  id              BIGSERIAL PK
  workspace_id    UUID FK → workspaces NOT NULL
  user_id         UUID FK → users       -- NULL for system actions
  action          VARCHAR(100) NOT NULL  -- message.sent, kb.updated, escalation.created, etc.
  entity_type     VARCHAR(50)            -- conversation, kb_document, user, etc.
  entity_id       UUID
  details         JSONB DEFAULT '{}'
  ip_address      VARCHAR(45)
  created_at      TIMESTAMPTZ DEFAULT now()
```

#### Sprint 2–3 Tables (add 3)

```
kb_documents
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  title           VARCHAR(500) NOT NULL
  content         TEXT NOT NULL
  content_type    VARCHAR(20) NOT NULL   -- faq, policy, product_info, general
  status          VARCHAR(20) DEFAULT 'draft' -- draft, review, approved, archived
  language        VARCHAR(10) DEFAULT 'ar'
  uploaded_by_user_id UUID FK → users NOT NULL
  approved_by_user_id UUID FK → users
  version         INTEGER DEFAULT 1
  parent_document_id UUID FK → kb_documents  -- version chain
  metadata        JSONB DEFAULT '{}'
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
  deleted_at      TIMESTAMPTZ            -- soft delete

kb_chunks
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  document_id     UUID FK → kb_documents NOT NULL
  content         TEXT NOT NULL
  content_normalized TEXT NOT NULL        -- for FTS
  chunk_index     INTEGER NOT NULL
  token_count     INTEGER
  embedding_id    VARCHAR(255)           -- Qdrant point ID
  is_active       BOOLEAN DEFAULT true
  created_at      TIMESTAMPTZ DEFAULT now()

response_templates
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  intent_id       VARCHAR(50) NOT NULL   -- greeting, order_status, shipping, etc.
  dialect         VARCHAR(20) NOT NULL   -- gulf, egyptian, msa
  content         TEXT NOT NULL           -- template with {param} slots
  parameters      JSONB DEFAULT '[]'     -- [{name, type, required}]
  is_active       BOOLEAN DEFAULT true
  usage_count     INTEGER DEFAULT 0
  approved_by_user_id UUID FK → users
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

#### Sprint 4–5 Tables (add 2)

```
escalation_events
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  conversation_id UUID FK → conversations NOT NULL
  trigger_message_id UUID FK → messages
  escalation_type VARCHAR(20) NOT NULL   -- hard, soft, manual, system
  reason          VARCHAR(50)            -- low_confidence, angry_customer, complex_query, etc.
  confidence_at_escalation DECIMAL(4,3)
  context_package JSONB NOT NULL         -- {summary, recent_messages[], customer_info, intent, kb_gaps}
  assigned_user_id UUID FK → users
  status          VARCHAR(20) DEFAULT 'pending' -- pending, accepted, resolved, expired
  accepted_at     TIMESTAMPTZ
  resolved_at     TIMESTAMPTZ
  resolution_notes TEXT
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

tickets
  id              UUID PK DEFAULT gen_random_uuid()
  workspace_id    UUID FK → workspaces NOT NULL
  conversation_id UUID FK → conversations
  customer_id     UUID FK → customers NOT NULL
  assigned_user_id UUID FK → users
  subject         VARCHAR(500) NOT NULL
  status          VARCHAR(20) DEFAULT 'open' -- open, in_progress, waiting, resolved, closed
  priority        VARCHAR(20) DEFAULT 'medium' -- low, medium, high, urgent
  category        VARCHAR(50)
  notes           TEXT
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
  resolved_at     TIMESTAMPTZ
```

### 3.2 RLS Policy (Apply to ALL Tables)

```sql
-- Enable RLS on every table
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see rows matching their workspace
CREATE POLICY workspace_isolation ON {table}
  USING (workspace_id = current_setting('app.current_workspace_id')::uuid);

-- Set workspace context on every request (in FastAPI middleware)
-- SET LOCAL app.current_workspace_id = '{workspace_id}';
```

### 3.3 State Machines

**Conversation:** `active` → `waiting_agent` → `active` / `resolved` / `expired`
**Escalation:** `pending` → `accepted` → `resolved` / `expired`
**KB Document:** `draft` → `review` → `approved` → `archived`
**Ticket:** `open` → `in_progress` → `waiting` → `resolved` → `closed`

---

## 4. FOLDER / PROJECT STRUCTURE

```
radd/                              # Monorepo root
├── apps/
│   ├── api/                       # Python FastAPI backend
│   │   ├── alembic/               # Database migrations
│   │   │   ├── versions/          # Migration files
│   │   │   └── env.py
│   │   ├── radd/                  # Main package (renamed from chatpod)
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # FastAPI app entry
│   │   │   ├── config.py          # Settings from env
│   │   │   ├── deps.py            # Dependency injection (db, redis, qdrant)
│   │   │   │
│   │   │   ├── auth/              # Authentication module
│   │   │   │   ├── router.py      # /auth/* routes
│   │   │   │   ├── service.py     # JWT logic, password hashing
│   │   │   │   ├── middleware.py   # RBAC middleware
│   │   │   │   └── schemas.py     # Pydantic models
│   │   │   │
│   │   │   ├── webhooks/          # WhatsApp webhook handler
│   │   │   │   ├── router.py      # /webhooks/whatsapp
│   │   │   │   ├── verify.py      # HMAC verification
│   │   │   │   └── parser.py      # Message parsing + normalization
│   │   │   │
│   │   │   ├── conversations/     # Conversation management
│   │   │   │   ├── router.py      # /conversations/* CRUD
│   │   │   │   ├── service.py     # Business logic
│   │   │   │   ├── schemas.py
│   │   │   │   └── models.py      # SQLAlchemy models
│   │   │   │
│   │   │   ├── pipeline/          # AI orchestration (no LangChain)
│   │   │   │   ├── orchestrator.py    # Main pipeline: message → response
│   │   │   │   ├── normalizer.py      # Arabic text normalization
│   │   │   │   ├── dialect.py         # Dialect detection (v0 rules, v1 ML)
│   │   │   │   ├── intent.py          # Intent classification (v0 keyword, v1 AraBERT)
│   │   │   │   ├── retriever.py       # Hybrid retrieval (Qdrant + BM25 + RRF)
│   │   │   │   ├── generator.py       # GPT-4.1-mini RAG generation
│   │   │   │   ├── verifier.py        # NLI grounding verification
│   │   │   │   ├── confidence.py      # Confidence scoring + routing
│   │   │   │   ├── guardrails.py      # PII redaction, prompt injection, toxicity
│   │   │   │   └── templates.py       # Template response engine
│   │   │   │
│   │   │   ├── knowledge/         # KB management
│   │   │   │   ├── router.py      # /knowledge/* CRUD
│   │   │   │   ├── service.py
│   │   │   │   ├── chunker.py     # Document chunking
│   │   │   │   ├── embedder.py    # Embedding generation
│   │   │   │   └── schemas.py
│   │   │   │
│   │   │   ├── escalation/        # Escalation engine
│   │   │   │   ├── router.py      # /escalations/*
│   │   │   │   ├── service.py     # Escalation logic + context package builder
│   │   │   │   └── schemas.py
│   │   │   │
│   │   │   ├── actions/           # External action execution
│   │   │   │   ├── router.py
│   │   │   │   ├── salla.py       # Salla API integration
│   │   │   │   └── base.py        # Action protocol interface
│   │   │   │
│   │   │   ├── admin/             # Admin API (dashboard backend)
│   │   │   │   ├── router.py      # /admin/* analytics, settings
│   │   │   │   ├── analytics.py   # KPI calculations
│   │   │   │   └── schemas.py
│   │   │   │
│   │   │   ├── whatsapp/          # WhatsApp Cloud API client
│   │   │   │   ├── client.py      # Send message, mark read, etc.
│   │   │   │   └── types.py       # WhatsApp message types
│   │   │   │
│   │   │   └── db/                # Database utilities
│   │   │       ├── base.py        # SQLAlchemy base, session factory
│   │   │       ├── models.py      # All SQLAlchemy models (or split per module)
│   │   │       └── session.py     # Async session management + RLS context
│   │   │
│   │   ├── workers/               # Background workers
│   │   │   ├── message_worker.py  # Redis Streams consumer → pipeline
│   │   │   └── kb_indexer.py      # Document embedding + Qdrant indexing
│   │   │
│   │   ├── scripts/               # Utility scripts
│   │   │   ├── seed.py            # Seed data for development
│   │   │   └── benchmark.py       # NLP benchmark runner
│   │   │
│   │   ├── tests/
│   │   │   ├── conftest.py        # Fixtures (test db, test client, test workspace)
│   │   │   ├── test_webhooks.py
│   │   │   ├── test_pipeline.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_rls.py        # Cross-tenant isolation tests
│   │   │   └── test_arabic.py     # Arabic normalization + dialect tests
│   │   │
│   │   ├── pyproject.toml         # Python dependencies (uv)
│   │   └── alembic.ini
│   │
│   └── web/                       # Next.js frontend
│       ├── app/
│       │   ├── layout.tsx         # Root layout (RTL, Arabic fonts)
│       │   ├── (auth)/
│       │   │   └── login/page.tsx
│       │   └── (dashboard)/
│       │       ├── layout.tsx     # Dashboard layout (sidebar, header)
│       │       ├── page.tsx       # Live operations (KPI cards + feed)
│       │       ├── conversations/
│       │       │   ├── page.tsx   # Conversation list
│       │       │   └── [id]/page.tsx  # Conversation detail
│       │       ├── knowledge/
│       │       │   └── page.tsx   # KB management
│       │       ├── escalations/
│       │       │   └── page.tsx   # Escalation queue
│       │       └── settings/
│       │           └── page.tsx   # Thresholds, business hours, agents
│       ├── components/
│       │   ├── ui/                # shadcn/ui components
│       │   ├── conversations/     # Conversation-specific components
│       │   ├── knowledge/         # KB-specific components
│       │   └── layout/            # Sidebar, header, RTL wrapper
│       ├── lib/
│       │   ├── api.ts             # API client (generated from OpenAPI)
│       │   ├── auth.ts            # JWT handling
│       │   └── utils.ts
│       ├── styles/
│       │   └── globals.css        # Tailwind + RTL + Arabic fonts
│       ├── package.json
│       └── next.config.ts
│
├── infrastructure/
│   ├── docker-compose.yml         # Local dev: PostgreSQL, Redis, Qdrant, MinIO
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.web
│   └── terraform/                 # IaC (Sprint 5+)
│       ├── main.tf
│       ├── ecs.tf
│       └── variables.tf
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Lint + test + type-check
│       └── deploy.yml             # Build + push + deploy
│
├── docs/
│   └── developer-start-guide.md   # 5-page guide linking to relevant spec sections
│
├── Makefile                       # make up, make migrate, make seed, make api, make web, make test
├── .env.example
└── README.md
```

### 4.1 Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Tables | plural, snake_case | `conversations`, `kb_documents` |
| Columns | snake_case, FK = `{table_singular}_id` | `workspace_id`, `assigned_user_id` |
| Python modules | snake_case | `message_worker.py` |
| Python classes | PascalCase | `ConversationService` |
| API routes | kebab-case, plural nouns | `/api/v1/conversations`, `/api/v1/kb-documents` |
| Pydantic schemas | PascalCase + suffix | `ConversationCreate`, `MessageResponse` |
| React components | PascalCase | `ConversationDetail.tsx` |
| CSS | Tailwind utilities | RTL via `dir="rtl"` on root |

---

## 5. CURSOR BUILD ORDER

### 5.1 Vertical Slice Sequence

```
SLICE 1 (Sprint 1, Weeks 3-5): Template Response Path
  WhatsApp message in → normalized → intent classified → template response out → logged
  ↓
SLICE 2 (Sprint 2-3, Weeks 5-8): RAG Response Path  
  Complex query → KB retrieved → RAG generated → NLI verified → confidence routed → response out
  ↓
SLICE 3 (Sprint 4, Weeks 9-10): Escalation + Actions
  Low confidence → escalation queued → agent notified → context delivered → Salla order lookup
  ↓
SLICE 4 (Sprint 5, Weeks 11-12): Admin Dashboard + Safety
  Merchant sees conversations → manages KB → handles escalations → adjusts settings → PII redacted
  ↓
SLICE 5 (Sprint 6, Weeks 13-14): Hardening + Pilot
  Security audit → load test → Arabic review → 38-item checklist → shadow mode → go live
```

### 5.2 Exact Implementation Order (Day by Day for Sprint 1)

| Day | Build | Output |
|-----|-------|--------|
| 1 | docker-compose.yml (PostgreSQL 16, Redis 7, Qdrant 1.12, MinIO) | `make up` starts all services |
| 1 | .env.example with all required vars | Documented configuration |
| 1 | Makefile with all shortcuts | `make up/down/migrate/seed/api/web/test` |
| 2 | FastAPI project scaffold: main.py, config.py, deps.py | `make api` starts server on :8000 |
| 2 | SQLAlchemy base + session factory + RLS middleware | Database connection with tenant context |
| 3 | Alembic setup + first migration: 7 core tables + RLS policies | `make migrate` creates all tables |
| 3 | Seed script: 1 workspace, 2 users (owner + agent), 1 channel | `make seed` populates dev data |
| 4 | Auth module: login, JWT issue/refresh, RBAC middleware | POST /auth/login returns JWT |
| 4 | Health endpoint + OpenAPI docs | GET /health returns 200, /docs shows Swagger |
| 5 | WhatsApp webhook verification endpoint | Meta verification challenge passes |
| 5 | WhatsApp webhook receiver: parse + HMAC verify + dedup | Incoming messages accepted |
| 6 | Arabic normalizer: tashkeel, Alef/Ya, whitespace, tatweel | 50 test strings pass |
| 6 | Dialect detector v0: keyword lists for Gulf/Egyptian/MSA | Detects dialect on 100 test messages |
| 7 | Redis session management: create, get, expire (30 min) | Sessions tracked per customer |
| 7 | Conversation + customer creation on first message | New message creates records |
| 8 | Intent classifier v0: keyword + TF-IDF for 6 intents | >70% accuracy on 100 test queries |
| 8 | Template response engine: 5 templates × 3 dialects = 15 responses | Correct template selected |
| 9 | Message worker: Redis Streams consumer → pipeline orchestrator | Async processing pipeline |
| 9 | WhatsApp client: send text message via Cloud API | Response delivered to customer |
| 10 | End-to-end test: send WhatsApp message → get correct template response | **SLICE 1 COMPLETE** |

### 5.3 What Should Be Stubbed Initially

| Component | Stub Implementation | Replace In |
|-----------|-------------------|:----------:|
| Confidence scoring | Return `{intent: C, retrieval: 1.0, verify: 1.0}` for templates | Sprint 3 |
| RAG pipeline | Return "سأحولك لأحد فريقنا لمساعدتك" for non-template intents | Sprint 2 |
| Escalation engine | Log `escalation_needed` event, no routing | Sprint 4 |
| Admin dashboard | Grafana dashboards + direct DB queries | Sprint 5 |
| Salla integration | Return mock order data | Sprint 4 |
| PII redaction | Pass-through (no redaction) | Sprint 5 |
| NLI verification | Return `confidence: 0.90` for all RAG responses | Sprint 3 |

### 5.4 What Must Be Manually Tested Before Proceeding

| Checkpoint | After | Test | Pass Criteria |
|-----------|-------|------|--------------|
| WhatsApp round-trip | Sprint 1 Day 10 | Real phone → test number → response | Correct Arabic template in <3s |
| Cross-tenant isolation | Sprint 1 Day 3 | Create 2 workspaces, query each, verify zero leakage | 100% isolation |
| Arabic normalization | Sprint 1 Day 6 | 50 messages with tashkeel, varied Alef forms | All correct |
| Intent accuracy | Sprint 1 Day 8 | 100 Arabic CS queries | >70% on v0 |
| KB retrieval | Sprint 2 end | 50 queries against 30-doc KB | Correct passage in top 3 for >80% |
| RAG accuracy | Sprint 3 end | 200 queries across paths | >90% accurate, <3% hallucination |
| Escalation flow | Sprint 4 end | 20 low-confidence queries | All escalated with correct context |
| PII redaction | Sprint 5 end | 50 messages with phones, names, IDs | >95% recall |
| Full pilot readiness | Sprint 6 end | 38-item checklist | All pass |

---

## 6. FULL IMPLEMENTATION ROADMAP

### Sprint 0 — Foundation (Week 3, 3 days)

**Objective:** Running dev environment. Database schema. FastAPI scaffold.

**Deliverables:**
- docker-compose.yml (PG, Redis, Qdrant, MinIO)
- Alembic + 7-table migration with RLS
- FastAPI app with health endpoint
- Auth module (JWT login + RBAC)
- Makefile + .env.example + seed script

**Validation:** `make up && make migrate && make seed && make api` → server runs, login works, /docs shows Swagger.

**Risks:** None significant. This is scaffolding.

**Success criteria:** A developer can clone the repo, run 4 commands, and have a working API server with auth.

---

### Sprint 1 — Template Response Path (Weeks 3–5, 10 days)

**Objective:** WhatsApp message in → template response out → logged. First vertical slice.

**Deliverables:**
- WhatsApp webhook handler (receive, verify, dedup)
- Arabic normalizer + dialect detector v0
- Session management (Redis)
- Intent classifier v0 (keyword, 6 intents)
- Template engine (5 intents × 3 dialects)
- Message worker (Redis Streams → pipeline)
- WhatsApp response delivery
- Conversation + message logging

**Validation:** Send real WhatsApp message → get correct Arabic template response.

**Risks:** WhatsApp API integration details. Meta rate limits.

**Success criteria:** End-to-end template path works with real WhatsApp message.

**Go/no-go:** Template path works → proceed to Sprint 2. Fails → debug, do not proceed.

---

### Sprint 2 — Knowledge Retrieval (Weeks 5–6, 10 days)

**Objective:** KB documents can be uploaded, chunked, embedded, and searched.

**Deliverables:**
- KB document CRUD API
- Document chunker (semantic boundaries, 200–500 token chunks)
- Embedding generator (text-embedding-3-small)
- Qdrant collection management (per workspace)
- PostgreSQL FTS index on chunks (Arabic tsvector)
- Hybrid retrieval: Qdrant vector + PG BM25 + RRF fusion
- kb_documents + kb_chunks + response_templates tables

**Validation:** Upload 30 FAQs. Query in Arabic. Correct passage in top 3 for >80% of queries.

**Risks:** Arabic tokenization for BM25. Qdrant indexing performance. Chunk size tuning.

**Success criteria:** Retrieval quality >80% relevance on sample KB.

---

### Sprint 3 — RAG Generation + Verification (Weeks 7–8, 10 days)

**Objective:** Complex queries get grounded Arabic responses verified against source.

**Deliverables:**
- GPT-4.1-mini RAG generation with Arabic system prompt
- Source passage injection into prompt
- NLI verification (xlm-roberta-large-xnli)
- Full confidence scoring: min(C_intent, C_retrieval, C_verify)
- Template vs RAG routing based on confidence
- Response quality logging (for threshold calibration)

**Validation:** 200 test queries. >90% accurate. <3% hallucination.

**Risks:** Arabic NLI accuracy (75–80% expected). Hallucination rate. Latency.

**Success criteria:** RAG path produces accurate, grounded Arabic responses. Confidence routing correctly separates template from RAG from escalation.

**Go/no-go:** Hallucination >5% → tighten thresholds, expand templates, reduce RAG surface. Hallucination <3% → proceed.

---

### Sprint 4 — Escalation + Actions (Weeks 9–10, 10 days)

**Objective:** Low confidence → agent gets the conversation with context. Order status works.

**Deliverables:**
- Escalation engine (hard + soft)
- Context package builder (summary, recent messages, customer info, intent, KB gaps)
- Agent queue (sorted by priority, time)
- WebSocket real-time notifications to agents
- Salla API integration (get_order_status)
- escalation_events + tickets tables
- Basic agent response flow (accept → respond → resolve)

**Validation:** 20 low-confidence queries → all escalated with correct context package. Salla order lookup returns correct data.

**Risks:** Salla API access. WebSocket reliability. Context package completeness.

**Success criteria:** Escalation works end-to-end. Agent gets useful context. Order status returns real data.

---

### Sprint 5 — Admin Dashboard + Safety (Weeks 11–12, 10 days)

**Objective:** Merchant can see and control the system. PII is protected.

**Deliverables:**
- Next.js admin dashboard (RTL-first, shadcn/ui)
- Live operations page: 8 KPI cards + conversation feed
- Conversation detail: message thread + context panel
- KB management: upload, edit, review workflow, approve/reject
- Escalation queue: cards + accept + resolve
- Settings: confidence thresholds, business hours, agent management
- PII redaction pipeline (regex + NER + over-redact)
- Audit trail viewer (filterable log)

**Validation:** Merchant can: view live conversations, upload KB doc, approve it, see it used in responses, adjust thresholds, handle escalation.

**Risks:** RTL layout bugs. Dashboard performance. PII redaction recall.

**Success criteria:** Dashboard is functional, RTL-correct, and usable by a non-technical merchant.

---

### Sprint 6 — Hardening + Pilot (Weeks 13–14, 10 days)

**Objective:** System is safe for real customer data. Pilot customer onboarded.

**Deliverables:**
- Security audit: OWASP LLM Top 10, prompt injection testing
- Load test: 50 concurrent sessions, P95 <4s
- Arabic response review: 500 conversations across all paths
- 38-item pilot readiness checklist (ENGINEERING-PLAN §12)
- Pilot customer KB loaded + agents trained + dry run
- Shadow mode deployment (system processes, does not send)

**Validation:** All 38 items pass. 48 hours shadow mode with zero critical errors.

**Risks:** Security findings. Dashboard incomplete. Pilot customer not ready.

**Success criteria:** Pilot-ready. Shadow mode clean. Customer confirmed.

---

## 7. API / WEBHOOK / FLOW PLAN

### 7.1 Major Routes

```
Auth
  POST   /api/v1/auth/login              → JWT tokens
  POST   /api/v1/auth/refresh             → new access token
  GET    /api/v1/auth/me                  → current user

Webhooks
  GET    /api/v1/webhooks/whatsapp        → Meta verification challenge
  POST   /api/v1/webhooks/whatsapp        → inbound message handler

Conversations
  GET    /api/v1/conversations            → list (paginated, filtered)
  GET    /api/v1/conversations/:id        → detail with messages
  PATCH  /api/v1/conversations/:id        → update status/assignment
  POST   /api/v1/conversations/:id/messages → agent sends message

Knowledge
  GET    /api/v1/kb/documents             → list documents
  POST   /api/v1/kb/documents             → upload document
  PATCH  /api/v1/kb/documents/:id         → update
  DELETE /api/v1/kb/documents/:id         → soft delete
  POST   /api/v1/kb/documents/:id/approve → approve for use
  GET    /api/v1/kb/templates             → list templates
  POST   /api/v1/kb/templates             → create template

Escalations
  GET    /api/v1/escalations              → queue (pending, sorted by time)
  POST   /api/v1/escalations/:id/accept   → agent accepts
  POST   /api/v1/escalations/:id/resolve  → agent resolves

Admin
  GET    /api/v1/admin/analytics           → KPI dashboard data
  GET    /api/v1/admin/settings            → workspace settings
  PATCH  /api/v1/admin/settings            → update settings
  GET    /api/v1/admin/audit-log           → audit trail (paginated)
  GET    /api/v1/admin/users               → user management
  POST   /api/v1/admin/users               → create user

Health
  GET    /health                           → service health
  GET    /ready                            → readiness (DB + Redis + Qdrant)
```

### 7.2 WhatsApp Webhook Flow

```
Meta sends POST /webhooks/whatsapp
  → Verify HMAC-SHA256 signature
  → Parse message (text only; reject media with Arabic message)
  → Check dedup (external_id in Redis, 5-min TTL)
  → ACK with 200 (within 500ms)
  → Enqueue to Redis Stream: messages:{workspace_id}
  → Return

Message Worker picks up from Redis Stream
  → Load/create customer record (by phone hash)
  → Load/create conversation (by customer + channel, 30-min session window)
  → Normalize Arabic text
  → Detect dialect
  → Run pipeline orchestrator
  → Store message + response in DB
  → Send response via WhatsApp Cloud API
  → Update conversation metadata
  → Emit audit event
```

### 7.3 Pipeline Orchestrator Flow

```
Input: normalized Arabic message + conversation context

1. INTENT CLASSIFICATION
   v0: keyword + TF-IDF → intent + C_intent
   v1: AraBERT → intent + C_intent

2. ROUTING DECISION
   if C_intent ≥ 0.85 AND intent in template_intents:
     → TEMPLATE PATH
   else:
     → RAG PATH

3a. TEMPLATE PATH
   Select template by (intent, dialect, workspace)
   Fill parameters (customer name, order number, etc.)
   Set C_retrieval = 1.0, C_verify = 1.0
   → confidence = min(C_intent, 1.0, 1.0) = C_intent
   → RESPOND

3b. RAG PATH
   Retrieve: Qdrant vector search + PG BM25 → RRF fusion → top 5 passages
   Set C_retrieval = top passage score
   Generate: GPT-4.1-mini with system prompt + passages + conversation history
   Verify: NLI check (response entailed by passages?)
   Set C_verify = NLI confidence
   → confidence = min(C_intent, C_retrieval, C_verify)

4. CONFIDENCE ROUTING
   if confidence ≥ 0.85: → RESPOND (auto)
   if 0.60 ≤ confidence < 0.85: → SOFT ESCALATE (draft + agent review)
   if confidence < 0.60: → HARD ESCALATE (agent takes over)

5. RESPOND
   Apply guardrails (PII check, prohibited phrases, length)
   Send via WhatsApp
   Log message with confidence + source passages

6. ESCALATE
   Build context package: {summary, messages, customer, intent, confidence, kb_gaps}
   Create escalation_event record
   Notify agent via WebSocket
   Send customer: "سأحولك لأحد فريقنا لمساعدتك" (if hard)
```

### 7.4 Escalation Flow

```
HARD ESCALATION:
  System → customer: "I'm connecting you with our team"
  System → creates escalation_event (type: hard, status: pending)
  System → WebSocket notification to available agents
  Agent → accepts escalation → status: accepted
  Agent → reads context package (conversation history, intent, KB gaps)
  Agent → responds via dashboard → message sent to WhatsApp
  Agent → resolves → status: resolved, adds resolution notes

SOFT ESCALATION:
  System → generates draft response (not sent)
  System → creates escalation_event (type: soft, status: pending)
  System → WebSocket notification with draft
  Agent → reviews draft → approves (sends as-is) or edits (modifies then sends)
  Agent → resolves
```

---

## 8. FIRST CURSOR PROMPTS

These are the exact prompts to give Cursor, in sequence. Each prompt builds on the previous output.

### Prompt 1: Project Scaffold

```
Create a Python FastAPI project with the following structure:
- Monorepo with apps/api/ for the backend
- Use uv for Python package management (pyproject.toml)
- FastAPI with uvicorn, async SQLAlchemy, alembic for migrations
- Project package name: radd
- Entry point: radd/main.py with a FastAPI app
- Config: radd/config.py using pydantic-settings loading from .env
- Dependencies: radd/deps.py with async database session, Redis client, and health check
- Health endpoint at GET /health returning {"status": "ok", "version": "0.1.0"}
- OpenAPI docs at /docs
- CORS middleware allowing all origins (dev only)
- Create a Makefile with targets: up (docker compose), down, migrate, seed, api, test
- Create docker-compose.yml with: PostgreSQL 16 (port 5432), Redis 7 (port 6379), Qdrant 1.12 (ports 6333/6334), MinIO (ports 9000/9001)
- Create .env.example with all required variables
- The project is an Arabic-first customer service automation system for Saudi e-commerce.
```

### Prompt 2: Database Schema + Auth

```
Add to the radd FastAPI project:

1. SQLAlchemy async models for these 7 tables (all with UUID primary keys, workspace_id FK, created_at/updated_at):
   - workspaces (name, slug, settings JSONB, plan, status)
   - users (workspace_id, email, password_hash, name, role, is_active)
   - customers (workspace_id, channel_identifier_hash, channel_type, display_name, language)
   - channels (workspace_id, type, name, is_active, config JSONB)
   - conversations (workspace_id, customer_id, channel_id, status, assigned_user_id, intent, dialect, confidence_score, resolution_type, message_count)
   - messages (workspace_id, conversation_id, sender_type, content, content_normalized, external_id, confidence JSONB, source_passages JSONB, template_id)
   - audit_log (workspace_id, user_id, action, entity_type, entity_id, details JSONB)

2. RLS policies: enable RLS on all tables, create workspace_isolation policy using current_setting('app.current_workspace_id').

3. Alembic migration for all 7 tables.

4. Auth module at radd/auth/:
   - POST /api/v1/auth/login (email + password → JWT access + refresh tokens)
   - POST /api/v1/auth/refresh (refresh token → new access token)
   - GET /api/v1/auth/me (returns current user)
   - RBAC middleware that checks user.role against required role for each endpoint
   - Password hashing with bcrypt via passlib
   - JWT with python-jose, 15-min access token, 7-day refresh token

5. Seed script at scripts/seed.py creating: 1 workspace "Demo Store", 1 owner user, 1 agent user, 1 WhatsApp channel.

Use async SQLAlchemy with asyncpg. All queries must go through the RLS-enabled session that sets app.current_workspace_id.
```

### Prompt 3: WhatsApp Webhook + Arabic Pipeline v0

```
Add to the radd project:

1. WhatsApp webhook at radd/webhooks/:
   - GET /api/v1/webhooks/whatsapp — Meta verification challenge (hub.mode, hub.verify_token, hub.challenge)
   - POST /api/v1/webhooks/whatsapp — receive inbound messages
   - HMAC-SHA256 signature verification using Meta app secret
   - Parse text messages, extract: sender phone, message body, timestamp, message_id
   - Reject non-text messages with Arabic response: "عذراً، حالياً نقدر نساعدك بالرسائل النصية فقط"
   - Dedup via Redis (external_id, 5-min TTL)
   - ACK with 200 immediately, enqueue to Redis Stream

2. Arabic text processor at radd/pipeline/:
   - normalizer.py: remove tashkeel (diacritics), normalize Alef variants (أإآ→ا), normalize Ya (ى→ي), remove tatweel, normalize whitespace
   - dialect.py v0: rule-based detection using keyword markers:
     Gulf: وش، ليش، عشان، كذا، إيش، يبيله، حق
     Egyptian: إيه، ليه، عشان، كده، بتاع، يعني
     Default: MSA if no markers detected
   - intent.py v0: keyword matching for 6 intents:
     greeting (مرحبا، السلام، هلا)
     order_status (طلب، طلبي، وين طلبي، تتبع)
     shipping (شحن، توصيل، يوصل، متى يوصل)
     return_policy (إرجاع، ارجاع، استرجاع، رد المبلغ)
     store_hours (ساعات، دوام، متى تفتحون، مواعيد)
     other (anything not matched)
     Return intent + confidence score (1.0 for exact match, 0.7 for partial, 0.3 for other)

3. Template engine at radd/pipeline/templates.py:
   - 5 intents × 3 dialects (gulf, egyptian, msa) = 15 templates
   - Templates are stored in response_templates table but hardcoded initially
   - Support parameter slots: {customer_name}, {order_number}, {store_name}
   - Example Gulf greeting: "أهلاً وسهلاً! كيف أقدر أساعدك اليوم؟"

4. Pipeline orchestrator at radd/pipeline/orchestrator.py:
   - Input: raw message text + conversation context
   - Steps: normalize → detect dialect → classify intent → select template → format response
   - For non-template intents (other): return stub escalation message "سأحولك لأحد فريقنا لمساعدتك"
   - Return: {response_text, intent, dialect, confidence, resolution_type}

5. Message worker at radd/workers/message_worker.py:
   - Consume from Redis Stream messages:{workspace_id}
   - Load/create customer by phone hash
   - Load/create conversation (30-min session window)
   - Run pipeline orchestrator
   - Store message + response in database
   - Send response via WhatsApp Cloud API

6. WhatsApp client at radd/whatsapp/client.py:
   - send_text_message(phone_number, message, workspace_config)
   - mark_as_read(message_id, workspace_config)
   - Uses httpx async client
```

### Prompt 4: KB + RAG Pipeline (Sprint 2–3)

```
Add knowledge base and RAG pipeline to the radd project:

1. KB tables (new Alembic migration):
   - kb_documents (workspace_id, title, content, content_type, status, language, uploaded_by, approved_by, version)
   - kb_chunks (workspace_id, document_id, content, content_normalized, chunk_index, token_count, embedding_id, is_active)
   - response_templates (move from hardcoded to DB)

2. KB API at radd/knowledge/:
   - GET /api/v1/kb/documents — list with pagination + status filter
   - POST /api/v1/kb/documents — upload (title + content + type)
   - PATCH /api/v1/kb/documents/:id — update content
   - DELETE /api/v1/kb/documents/:id — soft delete
   - POST /api/v1/kb/documents/:id/approve — set status=approved, trigger re-indexing

3. Document processing pipeline:
   - chunker.py: split document into 200-500 token chunks at semantic boundaries (paragraph, section)
   - embedder.py: generate embeddings via OpenAI text-embedding-3-small (1536 dim)
   - Qdrant collection per workspace: "kb_{workspace_id}"
   - Store embeddings in Qdrant with payload: {chunk_id, document_id, workspace_id}
   - KB indexer worker: triggered on document approval, processes chunks + embeddings

4. Hybrid retrieval at radd/pipeline/retriever.py:
   - Vector search: Qdrant similarity search, top 10 results
   - Keyword search: PostgreSQL full-text search on kb_chunks.content_normalized using Arabic tsvector, top 10 results
   - RRF fusion: Reciprocal Rank Fusion combining both result sets
   - Return top 5 passages with scores
   - C_retrieval = score of top passage (normalized 0-1)

5. RAG generation at radd/pipeline/generator.py:
   - System prompt (Arabic): "You are a customer service assistant. Answer ONLY from the provided passages. If the answer is not in the passages, say you cannot answer. Respond in {dialect} Arabic. Be clear, concise, helpful."
   - User message + top 5 passages + last 3 conversation messages as context
   - GPT-4.1-mini via OpenAI API
   - Parse response, extract source passage references

6. NLI verification at radd/pipeline/verifier.py:
   - Use joeddav/xlm-roberta-large-xnli to check: is the generated response entailed by the source passages?
   - C_verify = NLI entailment probability
   - If C_verify < 0.60: reject response, use escalation stub instead

7. Update orchestrator:
   - If intent confidence ≥ 0.85 AND intent is template-eligible → template path
   - Else → RAG path (retrieve → generate → verify)
   - Full confidence = min(C_intent, C_retrieval, C_verify)
   - Route: ≥0.85 auto-send, 0.60-0.84 soft-escalate (stub for now), <0.60 hard-escalate (stub)
```

### Prompt 5: Escalation + Salla (Sprint 4)

```
Add escalation system and Salla integration to the radd project:

1. New tables (Alembic migration):
   - escalation_events (workspace_id, conversation_id, trigger_message_id, type, reason, confidence, context_package JSONB, assigned_user_id, status, resolution_notes)
   - tickets (workspace_id, conversation_id, customer_id, assigned_user_id, subject, status, priority, category, notes)

2. Escalation service at radd/escalation/:
   - Build context package: {summary (last 5 messages), recent_messages[], customer_info, detected_intent, confidence_scores, kb_gap_indicators}
   - Hard escalation: create event, notify agent, send customer Arabic message
   - Soft escalation: create event with AI draft response, notify agent
   - Agent accept/resolve flow
   - GET /api/v1/escalations — queue sorted by created_at
   - POST /api/v1/escalations/:id/accept
   - POST /api/v1/escalations/:id/resolve

3. WebSocket notifications:
   - WS endpoint at /ws/agent/{user_id}
   - Notify on: new escalation, conversation assignment, system alerts
   - Agent presence tracking (online/away/offline)

4. Salla integration at radd/actions/salla.py:
   - get_order_status(order_id, workspace_salla_config) → {order_id, status, tracking_number, estimated_delivery, items}
   - Handle Salla OAuth token refresh
   - Action protocol: detect "order status" intent with order number → call Salla API → format Arabic response
   - Fallback: if Salla API fails, escalate with context "could not retrieve order"

5. Update pipeline orchestrator:
   - Replace escalation stubs with real escalation flow
   - Add action detection: if intent=order_status and order_number extracted → call Salla
   - Update conversation status on escalation
```

### Prompt 6: Admin Dashboard (Sprint 5)

```
Create the Next.js admin dashboard at apps/web/:

1. Setup:
   - Next.js 15 + React 19 + TypeScript
   - Tailwind CSS 4 with RTL support (dir="rtl" on html)
   - shadcn/ui components
   - Arabic font: Noto Sans Arabic (Google Fonts)
   - API client generated from FastAPI OpenAPI spec

2. Layout:
   - RTL sidebar navigation (right side)
   - Pages: Dashboard (live ops), Conversations, Knowledge, Escalations, Settings
   - Arabic labels throughout. English as fallback.
   - Dark/light mode via system preference

3. Dashboard page (/ ):
   - 8 KPI cards: active conversations, automation rate, avg response time, escalation rate, CSAT, messages today, pending escalations, hallucination rate
   - Live conversation feed (most recent, sorted by last message)
   - WebSocket for real-time updates

4. Conversations page:
   - List view: status filter, search, date range
   - Detail view: message thread (chat bubble UI), context panel (customer info, intent, confidence, source passages)
   - Agent can respond from detail view

5. Knowledge page:
   - Document list with status badges (draft, review, approved, archived)
   - Upload form (title + content + type)
   - Review/approve workflow: admin reviews → approves → triggers indexing
   - Template management: view/edit templates per intent per dialect

6. Escalations page:
   - Queue of pending escalations sorted by time
   - Card shows: customer name, intent, confidence, time waiting
   - Click to expand: full context package + conversation thread
   - Accept + resolve buttons

7. Settings page:
   - Confidence thresholds (auto/soft/hard sliders)
   - Business hours configuration
   - Agent management (add/remove/change role)
   - WhatsApp connection status
   - Salla connection status
```

---

That is the complete technical execution pack. Everything Cursor needs to build this product, in the right order, with the right structure. The next step is opening Cursor and running Prompt 1.
