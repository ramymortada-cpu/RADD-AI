# الملف التعريفي التقني — منصة رَدّ (Radd)
**الإصدار:** 0.1.0 | **التاريخ:** مارس 2026

---

## 1. نظرة عامة

**رَدّ** منصة SaaS لأتمتة خدمة عملاء التجارة الإلكترونية عبر واتساب، مصممة للسوق السعودي والخليجي. تعتمد المنصة على نموذج RAG (Retrieval-Augmented Generation) مدمج بمعالجة متخصصة للغة العربية بلهجاتها المتعددة.

### المشكلة التي تحلها
التجار السعوديون يستقبلون مئات الرسائل اليومية على واتساب (استفسارات طلبات، شحن، إرجاع). الموظف البشري لا يتسع للحجم — رَدّ يرد تلقائياً بـ **دقة 95%** مع إحالة الحالات المعقدة للموظف.

### المستخدم المستهدف
متجر سعودي يعمل على منصة **سلة**، حجم رسائل يومي 50–500، فريق خدمة عملاء 1–5 موظفين.

---

## 2. مكدس التقنيات (Tech Stack)

### Backend
| المكوّن | التقنية | الإصدار | الغرض |
|---------|---------|---------|-------|
| إطار العمل | FastAPI | 0.115+ | REST API + WebSocket |
| ASGI Server | Uvicorn + Gunicorn | 0.32+ | Production server |
| قاعدة البيانات | PostgreSQL | 16 | البيانات الأساسية + RLS |
| ORM | SQLAlchemy (asyncio) | 2.0+ | Async DB layer |
| Migrations | Alembic | 1.14+ | Schema versioning |
| Cache / Queue | Redis 7 + Streams | 5.2+ | Sessions + message queue |
| Vector DB | Qdrant | 1.12 | Embeddings + similarity search |
| Object Storage | MinIO (dev) / S3 (prod) | — | ملفات KB |
| Package Manager | uv | 0.5+ | Python deps (fast) |
| Language | Python | 3.12 | — |

### AI / NLP
| المكوّن | التقنية | الغرض |
|---------|---------|-------|
| Embeddings | OpenAI `text-embedding-3-small` | 1536 dim، تحويل النصوص لمتجهات |
| توليد الردود | OpenAI `gpt-4.1-mini` | RAG generation، Arabic dialect-aware |
| التحقق (NLI) | `joeddav/xlm-roberta-large-xnli` | Hallucination detection |
| التطبيع | Custom regex (Python) | تنظيف النص العربي |
| تصنيف اللهجة | Rule-based keyword matching | Gulf / Egyptian / MSA |
| تصنيف النية | Keyword-based (v0) | 6 نوايا |

### Frontend
| المكوّن | التقنية | الإصدار |
|---------|---------|---------|
| إطار العمل | Next.js | 15.2 |
| UI Library | React | 19 |
| اللغة | TypeScript | 5.7 |
| CSS | Tailwind CSS | 4.0 |
| Components | Radix UI primitives | — |
| Arabic Font | Noto Sans Arabic | Google Fonts |
| Package Manager | pnpm | 9 |
| الاتجاه | RTL كامل (`dir="rtl"`) | — |

### Infrastructure
| المكوّن | التقنية |
|---------|---------|
| Containers | Docker + Docker Compose |
| Reverse Proxy | Nginx 1.27 (SSL + routing) |
| CI/CD | GitHub Actions |
| Container Registry | GitHub Container Registry (GHCR) |
| Production DB | Neon Serverless PostgreSQL |
| Production Redis | Upstash Serverless Redis |
| Production Deploy | VPS + docker-compose / SSH deploy |

---

## 3. بنية المشروع (Monorepo)

```
radd/
├── apps/
│   ├── api/                         ← FastAPI backend
│   │   ├── radd/
│   │   │   ├── admin/               ← KPI analytics + settings + user mgmt
│   │   │   ├── auth/                ← JWT + RBAC (4 roles)
│   │   │   ├── actions/             ← External API integrations (Salla)
│   │   │   ├── conversations/       ← Agent conversation management
│   │   │   ├── db/                  ← Models + sessions + RLS
│   │   │   ├── escalation/          ← Escalation queue + agent workflow
│   │   │   ├── knowledge/           ← KB CRUD + chunking + embedding
│   │   │   ├── pipeline/            ← Core NLP pipeline (7 stages)
│   │   │   ├── webhooks/            ← WhatsApp Meta webhook
│   │   │   ├── websocket/           ← Real-time agent notifications
│   │   │   └── whatsapp/            ← WhatsApp Cloud API client
│   │   ├── workers/
│   │   │   ├── message_worker.py    ← Redis Streams consumer (main loop)
│   │   │   └── kb_indexer.py        ← Document indexing worker
│   │   ├── alembic/versions/        ← 3 migration files
│   │   ├── scripts/                 ← seed.py + benchmark.py
│   │   └── tests/                   ← pytest unit tests
│   └── web/                         ← Next.js 15 dashboard
│       ├── app/
│       │   ├── (auth)/login/
│       │   └── (dashboard)/
│       │       ├── dashboard/       ← KPI + live feed
│       │       ├── conversations/   ← List + chat detail
│       │       ├── knowledge/       ← Document management
│       │       ├── escalations/     ← Agent queue
│       │       └── settings/        ← Workspace + users
│       ├── components/
│       │   ├── ui/                  ← Button, Card, Badge, Input, Textarea
│       │   ├── layout/              ← Sidebar RTL + TopBar
│       │   └── dashboard/           ← KPICard + LiveFeed
│       └── lib/
│           ├── api.ts               ← Typed API client
│           ├── auth.ts              ← Token management
│           └── utils.ts             ← Arabic date/label helpers
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api           ← Multi-stage, non-root, Gunicorn
│   │   ├── Dockerfile.worker        ← HuggingFace model cache volume
│   │   └── Dockerfile.web           ← Next.js standalone output
│   ├── nginx/nginx.conf             ← SSL + WebSocket + routing
│   ├── docker-compose.yml           ← Local dev (pg + redis + qdrant + minio)
│   └── docker-compose.prod.yml      ← Production stack (7 services)
├── .github/workflows/ci.yml         ← 4-job CI/CD pipeline
├── Makefile                         ← Developer commands
└── .env.example                     ← 30+ environment variables
```

---

## 4. مخطط قاعدة البيانات

### الجداول (9 جداول)

#### `workspaces` — المتاجر المشتركة
```
id (UUID PK) | name | slug (unique) | settings (JSONB) | plan | status | created_at | updated_at
```
- `settings` JSONB: confidence_thresholds، business_hours، escalation_messages
- `plan`: pilot / growth / scale
- **RLS:** كل جدول محمي بـ `app.current_workspace_id`

#### `users` — موظفو المتجر
```
id | workspace_id (FK) | email (unique per workspace) | password_hash | name
role (owner|admin|agent|reviewer) | is_active | last_login_at
```
- Roles hierarchy: `owner > admin > agent > reviewer`
- كلمات المرور: bcrypt hash

#### `customers` — عملاء واتساب
```
id | workspace_id (FK) | channel_identifier_hash (SHA-256 phone)
channel_type | display_name | language | metadata (JSONB)
first_seen_at | last_seen_at
```
- الهاتف مخزن كـ hash فقط لحماية الخصوصية
- `UniqueConstraint(workspace_id, channel_identifier_hash)`

#### `channels` — قنوات التواصل
```
id | workspace_id (FK) | type (whatsapp) | name | is_active
config (JSONB: wa_phone_number_id, wa_business_account_id)
```

#### `conversations` — المحادثات
```
id | workspace_id (FK) | customer_id (FK) | channel_id (FK)
status (active|waiting_agent|resolved|expired)
assigned_user_id (FK, nullable) | intent | dialect
confidence_score (DECIMAL 4,3) | resolution_type
message_count | first_message_at | last_message_at | resolved_at
```
- `resolution_type`: `auto_template` | `auto_rag` | `escalated_soft` | `escalated_hard`

#### `messages` — الرسائل
```
id | workspace_id (FK) | conversation_id (FK)
sender_type (customer|system|agent) | content | content_normalized
external_id (WhatsApp message ID) | confidence (JSONB) | source_passages (JSONB)
template_id | metadata (JSONB)
```
- `confidence` JSONB: `{intent: 0.9, retrieval: 0.85, verify: 0.88}`
- `source_passages` JSONB: مقاطع KB المستخدمة في الرد

#### `kb_documents` — وثائق قاعدة المعرفة
```
id | workspace_id (FK) | title | content (Text) | content_type
status (draft|review|approved|archived) | language
uploaded_by_user_id (FK) | approved_by_user_id (FK, nullable)
version | parent_document_id (FK, self-ref) | deleted_at (soft delete)
```

#### `kb_chunks` — مقاطع الوثائق (للـ RAG)
```
id | workspace_id (FK) | document_id (FK) | content | content_normalized
chunk_index | token_count | embedding_id (Qdrant point ID) | is_active
```
- `tsv` عمود إضافي (`tsvector`) للبحث النصي BM25
- GIN index على `tsv` للأداء

#### `escalation_events` — أحداث التصعيد
```
id | workspace_id (FK) | conversation_id (FK) | trigger_message_id (FK)
escalation_type (hard|soft) | reason | confidence_at_escalation
context_package (JSONB) | assigned_user_id (FK) | status (pending|accepted|resolved|expired)
rag_draft (Text, nullable) | accepted_at | resolved_at | resolution_notes
```
- `context_package` JSONB: `{summary, recent_messages, customer_info, detected_intent, kb_gaps}`

#### `tickets` — تذاكر الدعم
```
id | workspace_id (FK) | conversation_id (FK) | customer_id (FK)
assigned_user_id (FK) | subject | status (open|in_progress|resolved|closed)
priority (low|medium|high|urgent) | category | notes | resolved_at
```

#### `audit_log` — سجل التدقيق
```
id (BigInt, auto) | workspace_id (FK) | user_id (FK, nullable)
action | entity_type | entity_id | details (JSONB) | ip_address | created_at
```

### Row Level Security (RLS)
كل جدول يحتوي على:
```sql
ALTER TABLE tablename ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON tablename
    USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
```
يُفعَّل عبر `SET LOCAL app.current_workspace_id = :workspace_id` في كل session.

---

## 5. بايبلاين معالجة الرسائل

### المسار الكامل (Message Processing Pipeline)

```
WhatsApp Message
      │
      ▼
┌─────────────────────────────────────────┐
│  1. WEBHOOK (radd/webhooks/router.py)   │
│  • HMAC-SHA256 signature verification   │
│  • Message deduplication (Redis SET)    │
│  • Enqueue → Redis Stream               │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  2. WORKER (workers/message_worker.py)  │
│  • Redis Streams XREADGROUP consumer    │
│  • Resolve Customer + Conversation      │
│  • Load conversation history (last 10)  │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  3. NLP PIPELINE (run_pipeline_async)   │
│                                         │
│  3.1 is_arabic() check                  │
│       ↓                                 │
│  3.2 normalize()                        │
│      • Remove tashkeel (حركات)          │
│      • Normalize Alef variants (أإآ→ا)  │
│      • Normalize Ya (ى→ي)              │
│      • Remove tatweel (ـ)               │
│      • Normalize whitespace             │
│       ↓                                 │
│  3.3 detect_dialect()                   │
│      • Gulf (خليجي): وش، كيفك، زين...  │
│      • Egyptian (مصري): إيه، ازيك...   │
│      • MSA (فصحى): default             │
│       ↓                                 │
│  3.4 classify_intent()                  │
│      • greeting, order_status           │
│      • shipping, return_policy          │
│      • store_hours, other               │
│      • Confidence score (0.0–1.0)       │
│       ↓                                 │
│  3.5 ROUTING DECISION:                  │
│                                         │
│  [order_status] ──→ Salla API path      │
│  [high confidence + template] → template│
│  [else] → RAG path                      │
└─────────────────────────────────────────┘
      │
      ├──── ACTION PATH ────────────────────
      │     Salla get_order_status()        
      │     • Extract order number (Arabic+Arabic-Indic numerals)
      │     • HTTP call to Salla API        
      │     • Dialect-aware Arabic response 
      │
      ├──── TEMPLATE PATH ──────────────────
      │     render_template(intent, dialect) 
      │     • 15 templates (5 intents × 3 dialects)
      │     • Parameter slots: {customer_name, order_number, store_name}
      │
      └──── RAG PATH ───────────────────────
            │
            ▼
      ┌─────────────────────────┐
      │  retrieve()             │
      │  • OpenAI embedding of query     │
      │  • Qdrant vector search (top-10) │
      │  • PG BM25 full-text search      │
      │  • RRF fusion (k=60)             │
      │  • C_retrieval score             │
      └─────────────────────────┘
            │
            ▼
      ┌─────────────────────────┐
      │  generate_rag_response()│
      │  • System prompt (Arabic)│
      │  • Dialect instruction  │
      │  • Retrieved passages   │
      │  • Last 10 messages     │
      │  • GPT-4.1-mini         │
      └─────────────────────────┘
            │
            ▼
      ┌─────────────────────────┐
      │  verify_response_fast() │
      │  • xlm-roberta NLI      │
      │  • entailment score     │
      │  • keyword fallback     │
      │  • C_verify score       │
      └─────────────────────────┘
            │
            ▼
      C_min = min(C_intent, C_retrieval, C_verify)
      
      ≥ 0.85  →  auto_rag (يرسل مباشرة)
      ≥ 0.60  →  escalated_soft (يحيل + draft للموظف)
      < 0.60  →  escalated_hard (يوقف + ينبّه الموظف)
            │
            ▼
┌─────────────────────────────────────────┐
│  4. GUARDRAILS (pipeline/guardrails.py) │
│  • PII redaction (ID، هاتف، email، IBAN)│
│  • Prompt injection detection           │
│  • Response length cap (1200 char)      │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  5. DELIVERY                            │
│  • Send via WhatsApp Cloud API          │
│  • Store message in DB                  │
│  • If escalated → create EscalationEvent│
│  • WebSocket broadcast to agents        │
└─────────────────────────────────────────┘
```

---

## 6. REST API Endpoints

### Authentication — `/api/v1/auth`
| Method | Path | الوصف | Auth |
|--------|------|-------|------|
| POST | `/login` | تسجيل دخول (workspace_slug + email + password) | — |
| POST | `/refresh` | تجديد access token | refresh_token |
| GET | `/me` | بيانات المستخدم الحالي | Bearer |

### WhatsApp Webhooks — `/api/v1/webhooks`
| Method | Path | الوصف |
|--------|------|-------|
| GET | `/whatsapp` | Meta webhook verification |
| POST | `/whatsapp` | استقبال الرسائل (HMAC verified) |

### Knowledge Base — `/api/v1/kb`
| Method | Path | الوصف | Role |
|--------|------|-------|------|
| GET | `/documents` | قائمة الوثائق (filter by status) | reviewer+ |
| POST | `/documents` | رفع وثيقة جديدة | agent+ |
| GET | `/documents/{id}` | تفاصيل وثيقة | reviewer+ |
| PATCH | `/documents/{id}` | تحديث وثيقة | admin+ |
| DELETE | `/documents/{id}` | حذف ناعم | admin+ |
| POST | `/documents/{id}/approve` | اعتماد وثيقة (triggers indexing) | admin+ |
| GET | `/templates` | قوالب الردود | reviewer+ |
| POST | `/templates` | إنشاء قالب | admin+ |
| PATCH | `/templates/{id}` | تحديث قالب | admin+ |

### Conversations — `/api/v1/conversations`
| Method | Path | الوصف | Role |
|--------|------|-------|------|
| GET | `/` | قائمة المحادثات (paginated, filter by status) | reviewer+ |
| GET | `/{id}` | تفاصيل محادثة + رسائل | reviewer+ |
| PATCH | `/{id}` | تحديث status / assigned_user | agent+ |
| POST | `/{id}/messages` | رد الموظف (يرسل واتساب + DB) | agent+ |

### Escalations — `/api/v1/escalations`
| Method | Path | الوصف | Role |
|--------|------|-------|------|
| GET | `/` | قائمة التصعيدات (filter by status) | agent+ |
| POST | `/{id}/accept` | قبول التصعيد | agent+ |
| POST | `/{id}/resolve` | إغلاق التصعيد | agent+ |

### Admin — `/api/v1/admin`
| Method | Path | الوصف | Role |
|--------|------|-------|------|
| GET | `/analytics` | 8 KPI cards | reviewer+ |
| GET | `/settings` | إعدادات المتجر | reviewer+ |
| PATCH | `/settings` | تحديث الإعدادات | admin+ |
| GET | `/audit-log` | سجل التدقيق | admin+ |
| GET | `/users` | قائمة المستخدمين | admin+ |
| POST | `/users` | إنشاء مستخدم | admin+ |
| PATCH | `/users/{id}` | تحديث مستخدم | admin+ |

### WebSocket — `/ws/agent`
```
ws://host/ws/agent?token=<JWT>
```
Events received:
- `new_escalation` — تصعيد جديد مع context_package
- `conversation_resolved` — محادثة محلولة
- `agent_presence` — حضور الموظفين (online/away/offline)
- `typing` — مؤشر الكتابة

---

## 7. مكوّنات NLP بالتفصيل

### 7.1 التطبيع (normalizer.py)
```python
TASHKEEL = re.compile(r'[\u0610-\u061A\u064B-\u065F]')
ALEF     = re.compile(r'[أإآٱ]')     # → ا
YA       = re.compile(r'ى')           # → ي
TATWEEL  = re.compile(r'\u0640')      # كشيدة
```
هدفه: رسالة "أَهْلاً بِكُمْ يا إِخوتي" → "اهلا بكم يا اخوتي"

### 7.2 تصنيف اللهجة (dialect.py)
مؤشرات خليجية: وش، كيفك، زين، ابغى، وايد، شلون، ليش، يبغى  
مؤشرات مصرية: إيه، ازيك، عامل، معاك، فين، إزاي، امتى  
القاعدة: إذا عدد مؤشرات خليجية > مصرية → `gulf`، والعكس → `egyptian`، وإلا → `msa`

### 7.3 تصنيف النية (intent.py)
6 نوايا مدعومة:

| Intent | عينة كلمات مفتاحية |
|--------|-------------------|
| `greeting` | مرحبا، السلام، هلا، أهلا |
| `order_status` | طلب، رقم الطلب، أين طلبي، تتبع |
| `shipping` | شحن، توصيل، متى يوصل، رسوم التوصيل |
| `return_policy` | إرجاع، استرداد، تبديل، رفض |
| `store_hours` | مواعيد، وقت العمل، متى تفتح |
| `other` | default |

النتيجة: `{intent, confidence, matched_keywords, all_scores}`  
معيار الثقة: `matched / (matched + 1)` مع تضخيم للكلمات المتطابقة تماماً

### 7.4 الاسترجاع الهجين — RRF (retriever.py)
```
الخطوات:
1. embed(query) → OpenAI text-embedding-3-small → vector [1536 dim]
2. Qdrant.search(vector, top_k=10) → semantic results + scores
3. PostgreSQL FTS: to_tsquery('arabic', normalized_query) → BM25 results
4. Reciprocal Rank Fusion:
   score_rrf(d) = Σ 1/(k + rank_i(d))  حيث k=60
5. Top 5 passages بعد الدمج
6. C_retrieval = top_score_normalized (0.0–1.0)
```

### 7.5 التحقق من التأطير (verifier.py)
```
النموذج: joeddav/xlm-roberta-large-xnli (cross-lingual)
المدخل: (premise=passage, hypothesis=response)
المخرج: entailment_score → C_verify

Fallback سريع: keyword_overlap(response, passages)
  overlap_ratio = |words(response) ∩ words(passages)| / |words(response)|
  C_verify_fallback = min(0.9, overlap_ratio * 2)
```

### 7.6 حماية PII (guardrails.py)
| النمط | Placeholder |
|-------|-------------|
| رقم الهوية السعودية `[12]\d{9}` | `[NATIONAL_ID]` |
| هاتف خليجي `+966 / 05xx` | `[PHONE]` |
| بريد إلكتروني | `[EMAIL]` |
| بطاقة ائتمان (16 رقم) | `[CARD]` |
| IBAN سعودي `SA...` | `[IBAN]` |
| عنوان IP | `[IP]` |
| إحداثيات GPS | `[LOCATION]` |

كشف Prompt Injection: 8 patterns (English + Arabic) تشمل "ignore all previous instructions"، "تجاهل التعليمات"، DAN mode

---

## 8. نظام الأدوار والصلاحيات (RBAC)

```
owner     → كل الصلاحيات + حذف المتجر
admin     → إدارة المستخدمين + الإعدادات + اعتماد KB
agent     → رد على المحادثات + قبول التصعيدات
reviewer  → قراءة فقط (analytics + conversations)
```

### آلية JWT
- Access token: `HS256`, expires في 15 دقيقة
- Refresh token: expires في 7 أيام، مخزن في Redis
- Payload: `{sub: user_id, workspace_id, role, exp}`

---

## 9. الـ Workers (Background Processing)

### message_worker.py
```
Redis Streams: XREADGROUP على messages:{workspace_id}
Consumer Group: radd-workers
معالجة كل رسالة:
  1. Parse message payload
  2. Resolve/create Customer record
  3. Resolve/create Conversation
  4. Load last 10 messages (history)
  5. run_pipeline_async()
  6. Apply guardrails
  7. Store messages in DB (transaction)
  8. Send WhatsApp reply
  9. If escalated: create EscalationEvent + WS broadcast
  10. XACK (acknowledge message)
```

### kb_indexer.py
```
يُشغَّل عند اعتماد وثيقة KB:
  1. Load document content
  2. Semantic chunking (200–500 tokens per chunk)
  3. For each chunk:
     a. normalize Arabic text
     b. OpenAI embed (text-embedding-3-small)
     c. Upsert to Qdrant collection (workspace_id as collection name)
     d. Update kb_chunks.embedding_id
     e. Update kb_chunks.tsv (PostgreSQL FTS trigger auto-updates)
  4. Update document status → "indexed"
```

---

## 10. واجهة المستخدم (Dashboard)

### صفحة الرئيسية — 8 KPI Cards
| البطاقة | المصدر | التحديث |
|---------|--------|---------|
| محادثات نشطة | `conversations WHERE status='active'` | 30 ثانية |
| معدل الأتمتة | auto_template + auto_rag / total (24h) | 30 ثانية |
| متوسط وقت الرد | gap بين message customer + system | 30 ثانية |
| معدل التصعيد | escalated / total (24h) | 30 ثانية |
| رسائل اليوم | messages WHERE sender_type='customer' today | 30 ثانية |
| تصعيدات معلّقة | `escalation_events WHERE status='pending'` | 30 ثانية |
| تقييم الرضا | — (placeholder للإصدار القادم) | — |
| معدل الهلوسة | RAG responses with C_verify < 0.70 (24h) | 30 ثانية |

**Live Feed:** WebSocket connection `/ws/agent?token=JWT` — يعرض الأحداث الفورية (escalations, resolutions).

### صفحة المحادثات
- قائمة مع فلتر بالحالة (نشط / ينتظر موظف / محلول)
- بحث باسم العميل أو معرف المحادثة
- تفاصيل المحادثة: فقاعات RTL ملونة حسب المرسل (customer / system / agent)
- Badge ثقة على كل رد نظام
- صندوق رد الموظف: Ctrl+Enter للإرسال، زر "إرسال وإغلاق"

### صفحة قاعدة المعرفة
- إنشاء وثيقة inline (بدون modal)
- دورة حياة: مسودة → مراجعة → معتمد (يبدأ indexing تلقائياً) → مؤرشف
- حذف ناعم (soft delete)

### صفحة التصعيدات
- 3 views: معلّق / مقبول / محلول
- Context package مرئي: ملخص المحادثة + نية العميل + مسودة رد AI
- Agent actions: قبول → رد يدوي → إغلاق مع ملاحظات

### صفحة الإعدادات
- عتبات الثقة قابلة للتعديل (`auto_threshold` + `soft_threshold`)
- إدارة المستخدمين: إنشاء + تغيير الدور + تعطيل

---

## 11. CI/CD Pipeline

```
┌── push to PR ─────────────────────────────────┐
│  Job 1: test-api (pytest + ruff + mypy)        │
│  Job 2: test-web (tsc + eslint)                │
└───────────────────────────────────────────────┘
         │ (on push to main/staging)
         ▼
┌── Job 3: build-push ──────────────────────────┐
│  Docker multi-stage build × 3 images           │
│  Cache: GitHub Actions cache (layer cache)     │
│  Push to GHCR:                                 │
│    radd-api:{branch}-{sha8} + :latest          │
│    radd-worker:{branch}-{sha8} + :latest       │
│    radd-web:{branch}-{sha8} + :latest          │
└───────────────────────────────────────────────┘
         │ (only on push to main)
         ▼
┌── Job 4: deploy ──────────────────────────────┐
│  SSH to production server                      │
│  docker-compose pull → up --no-deps            │
│  alembic upgrade head                          │
│  docker image prune                            │
│  Slack notification (success/failure)          │
└───────────────────────────────────────────────┘
```

**Environments:** `production` (manual approval gate مفعّل في GitHub)

---

## 12. الأمان

### مستوى الشبكة
- Nginx: TLS 1.2/1.3 فقط، HSTS، X-Frame-Options، X-Content-Type-Options
- كل HTTP → HTTPS redirect

### مستوى التطبيق
- **RLS:** PostgreSQL Row Level Security — كل query مقيّد بـ `workspace_id` على مستوى DB
- **HMAC Verification:** كل webhook من Meta يُتحقق منه بـ `X-Hub-Signature-256`
- **Message Dedup:** Redis SET لمنع معالجة نفس الرسالة مرتين
- **JWT:** قصير الأمد (15 دقيقة) + refresh rotation
- **PII Redaction:** regex يمسح بيانات حساسة قبل الإرسال
- **Prompt Injection:** 8 patterns للكشف عن محاولات اختراق النموذج
- **Non-root containers:** كل Docker image يشغّل بـ UID 1001

### مستوى البيانات
- كلمات مرور: `bcrypt` (passlib)
- أرقام هواتف العملاء: SHA-256 hash فقط (لا يُخزن الرقم الأصلي)
- Audit log: كل action مسجّل

---

## 13. أداء وقابلية التوسع

### نقاط التصميم الحالية
| المقياس | القيمة الحالية |
|---------|---------------|
| Workers | 2 Gunicorn workers × API |
| Message throughput | ~100 رسالة/دقيقة (bottleneck: OpenAI API) |
| DB connections | AsyncPG connection pool (SQLAlchemy) |
| Redis dedup window | 24 ساعة |
| Qdrant collection | 1 per workspace |
| Chunk size | 200–500 tokens |
| Embedding dimension | 1536 (text-embedding-3-small) |

### خطوات التوسع عند الحاجة
1. **زيادة Workers:** رفع `--workers` في Gunicorn أو نشر عدة containers
2. **Message Queue:** Redis Streams تدعم multiple consumer groups تلقائياً
3. **Read Replicas:** Neon يدعم read replicas بدون تغيير الكود
4. **Caching:** إضافة Redis cache على embeddings متكررة
5. **Rate Limiting:** إضافة middleware على `/api/v1/` per workspace

---

## 14. Benchmark والاختبارات

### Gate G1 — Arabic NLP Benchmark
```
ملف: apps/api/scripts/benchmark.py
100 سؤال عربي موزع: greeting(10), order_status(30), shipping(20),
                      return_policy(20), store_hours(10), other(10)
النتيجة المحققة: 95% accuracy  ✅ (الهدف: ≥ 80%)
```

### اختبارات الوحدة (pytest)
```
tests/test_arabic.py     — normalizer + dialect + intent (15 اختبار)
tests/test_guardrails.py — PII redaction + injection detection (9 اختبارات)
tests/test_pipeline.py   — orchestrator routing logic
```

### تشغيل الاختبارات
```bash
make test-api     # pytest
make benchmark    # 100-query Arabic NLP benchmark
```

---

## 15. المتطلبات البيئية

### التطوير المحلي
```
Python 3.12 | uv 0.5+ | Node 22 | pnpm 9
Docker + Docker Compose
```

### الإنتاج (Production)
```
Server: Ubuntu 22.04 LTS, 4 vCPU, 8 GB RAM (minimum)
           16 GB RAM إذا worker يحمّل xlm-roberta محلياً

External Services:
  • Neon (PostgreSQL serverless)
  • Upstash (Redis serverless)
  • OpenAI API (GPT-4.1-mini + text-embedding-3-small)
  • Meta WhatsApp Cloud API
  • Salla Partner API

Optional:
  • AWS S3 (لبدائل MinIO في الإنتاج)
  • Qdrant Cloud (بدلاً من self-hosted)
```

---

## 16. الخلاصة التقنية

| البُعد | التفاصيل |
|--------|---------|
| **نوع المشروع** | B2B SaaS، Multi-tenant، Event-driven |
| **اللغة الأساسية** | عربية — خليجي + مصري + فصحى |
| **Channel** | WhatsApp Business Cloud API |
| **AI Core** | RAG + Hybrid Retrieval + NLI Verification |
| **Multi-tenancy** | PostgreSQL RLS — عزل كامل على مستوى DB |
| **Real-time** | WebSocket (FastAPI + Starlette) |
| **Async** | Python asyncio end-to-end (FastAPI + SQLAlchemy + Redis) |
| **Deployment** | Docker multi-stage → GHCR → SSH deploy |
| **CI/CD** | GitHub Actions — 4 jobs (test + build + push + deploy) |
| **NLP Accuracy** | 95% على 100-query Arabic benchmark |
| **Safety** | PII Redaction + Prompt Injection Detection + RLS |
| **Code Lines** | ~6,500 سطر Python + ~4,000 سطر TypeScript |
| **Files** | 85+ ملف |
| **DB Tables** | 9 جداول + RLS على الكل |
| **API Endpoints** | 30+ endpoint |
| **Tests** | 25+ unit test |
