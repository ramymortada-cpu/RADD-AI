# وثيقة التسليم — منصة رَدّ (Radd)
**تاريخ التسليم:** مارس 2026  
**المُسلِّم:** فريق التطوير  
**الإصدار:** 0.1.0 (MVP)

---

## 1. ما تم تسليمه

هذه الوثيقة تغطي كل ما يحتاجه المطوّر القادم (أو الفريق) لفهم، تشغيل، وتطوير منصة رَدّ من الصفر.

### ملخص سريع
| البند | التفاصيل |
|-------|---------|
| نوع المشروع | B2B SaaS — خدمة عملاء بالذكاء الاصطناعي عبر واتساب |
| المرحلة | MVP جاهز للاختبار مع أول عميل |
| لغة البرمجة | Python 3.12 (Backend) + TypeScript/Next.js (Frontend) |
| حالة الكود | مكتمل — لم يُختبر end-to-end بعد على بيئة حقيقية |
| اختبارات تمت | Unit tests (25+) + NLP Benchmark 95% |
| ما لم يُبنَ بعد | CSAT collection، Terraform IaC، monitoring (Grafana) |

---

## 2. هيكل المشروع

```
radd/                               ← Root
├── apps/
│   ├── api/                        ← FastAPI backend (Python)
│   └── web/                        ← Next.js 15 dashboard (TypeScript)
├── infrastructure/
│   ├── docker/                     ← Dockerfiles (api, worker, web)
│   ├── nginx/                      ← Reverse proxy config
│   ├── docker-compose.yml          ← Local dev
│   └── docker-compose.prod.yml     ← Production
├── docs/
│   ├── Technical_Profile.md        ← الملف التعريفي التقني
│   ├── HANDOVER.md                 ← هذه الوثيقة
│   ├── Founder_Execution_Plan_v1.md
│   ├── Radd_Founder_Control_Document_v2.md
│   └── Radd_Technical_Execution_Pack.md ← المصدر الأصلي للمواصفات
├── .github/workflows/ci.yml        ← CI/CD pipeline
├── .env.example                    ← Template للـ environment variables
├── Makefile                        ← أوامر التطوير
└── README.md                       ← دليل البدء السريع
```

---

## 3. البدء السريع (أول 30 دقيقة)

### المتطلبات
```bash
# تحقق أن هذه الأدوات مثبتة:
python --version     # يجب 3.12+
docker --version     # يجب 24+
node --version       # يجب 22+
pnpm --version       # يجب 9+

# لتثبيت uv (Python package manager):
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### الخطوات
```bash
# 1. Clone المشروع
git clone https://github.com/YOUR_ORG/radd.git
cd radd

# 2. إعداد environment variables
cp .env.example .env
# افتح .env وأضف على الأقل:
#   OPENAI_API_KEY=sk-...
#   (الباقي اختياري لاختبار الـ unit tests)

# 3. تثبيت Dependencies
make install
# يشغّل: uv sync (Python) + pnpm install (Node)

# 4. تشغيل الخدمات المحلية
make up
# يبدأ: PostgreSQL:5432, Redis:6379, Qdrant:6333, MinIO:9000

# 5. تهيئة قاعدة البيانات
make migrate   # تطبيق الـ migrations
make seed      # إنشاء بيانات تجريبية

# 6. تشغيل المشروع
make api       # terminal 1 → http://localhost:8000
make worker    # terminal 2 → message worker
make web       # terminal 3 → http://localhost:3000
```

### بيانات الدخول التجريبية (بعد seed)
```
Workspace Slug: demo
Email:          owner@demo.com
Password:       Demo1234!
```

### التحقق من أن كل شيء يعمل
```bash
# Health check
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs

# Dashboard
open http://localhost:3000
```

---

## 4. الخدمات الخارجية المطلوبة

### للتطوير (مطلوب فعلياً)
| الخدمة | لماذا | كيفية الحصول |
|--------|-------|--------------|
| **OpenAI API Key** | embeddings + GPT-4.1-mini | platform.openai.com → API Keys |

### للإنتاج (مطلوب كله)
| الخدمة | الغرض | الرابط | ملاحظة |
|--------|-------|--------|--------|
| **Neon** | PostgreSQL serverless | neon.tech | Free tier متاح |
| **Upstash** | Redis serverless | upstash.com | Free tier متاح |
| **OpenAI** | AI pipeline | platform.openai.com | ~$0.002/رسالة |
| **Meta WhatsApp** | Cloud API | business.facebook.com | 1000 رسالة/شهر مجانية |
| **Salla** | Partner API | salla.dev | مجاني للشركاء |

### إعداد WhatsApp Business (مهم)
```
1. إنشاء Meta Business Account
2. إنشاء Meta App → WhatsApp product
3. Get: Phone Number ID, Business Account ID, API Token
4. Webhook URL: https://yourdomain.com/api/v1/webhooks/whatsapp
5. Verify Token: نفس قيمة META_VERIFY_TOKEN في .env
6. Subscribe to: messages
```

---

## 5. متغيرات البيئة المهمة

```bash
# أهم 10 متغيرات (الكاملة في .env.example)

# [مطلوب] Authentication
SECRET_KEY=            # random 64-char string → openssl rand -hex 32
JWT_SECRET_KEY=        # random 64-char string مختلف

# [مطلوب] Database
DATABASE_URL=          # postgresql+asyncpg://user:pass@host/db

# [مطلوب] Redis
REDIS_URL=             # redis://host:6379/0

# [مطلوب] AI
OPENAI_API_KEY=        # sk-...

# [للواتساب] 
META_APP_SECRET=       # من Meta Developer Console
META_VERIFY_TOKEN=     # أنت تختاره
WA_PHONE_NUMBER_ID=    # من WhatsApp settings
WA_API_TOKEN=          # System User Token

# [للـ Salla]
SALLA_CLIENT_ID=
SALLA_CLIENT_SECRET=

# [ثقة AI] — عدّلها حسب الأداء
CONFIDENCE_AUTO_THRESHOLD=0.85
CONFIDENCE_SOFT_ESCALATION_THRESHOLD=0.60
```

**⚠️ تحذير:** لا ترفع `.env` على GitHub أبداً — هو في `.gitignore`.

---

## 6. قاعدة البيانات

### Migrations
```bash
# تطبيق كل الـ migrations
make migrate

# التراجع خطوة للخلف
make migrate-down

# إنشاء migration جديد
make migrate-create
# (يطلب منك اسم الـ migration)
```

### الـ Migrations الموجودة
| الملف | المحتوى |
|-------|---------|
| `0001_initial_schema.py` | 7 جداول أساسية + RLS policies |
| `0002_kb_tables.py` | kb_documents + kb_chunks + response_templates + FTS index |
| `0003_escalation_tickets.py` | escalation_events + tickets + RLS |

### مهم: Row Level Security
كل جدول محمي بـ RLS. يجب دائماً تمرير `workspace_id` للـ session:
```python
# يتم تلقائياً في get_db_session()
await db.execute(
    text("SET LOCAL app.current_workspace_id = :wid"),
    {"wid": str(workspace_id)}
)
```
إذا نسيت هذا → ستحصل على **0 نتائج** بدون error واضح.

---

## 7. الكود الأساسي — خريطة سريعة

### أهم 10 ملفات يجب تعرفها

| الملف | الغرض | الأهمية |
|-------|-------|---------|
| `radd/pipeline/orchestrator.py` | قلب النظام — routing logic كامل | ⭐⭐⭐⭐⭐ |
| `workers/message_worker.py` | يعالج كل رسالة واتساب واردة | ⭐⭐⭐⭐⭐ |
| `radd/db/models.py` | كل الـ database models | ⭐⭐⭐⭐⭐ |
| `radd/config.py` | كل الـ settings من .env | ⭐⭐⭐⭐ |
| `radd/pipeline/retriever.py` | Hybrid RAG retrieval | ⭐⭐⭐⭐ |
| `radd/pipeline/guardrails.py` | PII + safety | ⭐⭐⭐⭐ |
| `radd/auth/middleware.py` | JWT + RBAC | ⭐⭐⭐ |
| `radd/escalation/service.py` | escalation workflow | ⭐⭐⭐ |
| `radd/websocket/manager.py` | real-time notifications | ⭐⭐⭐ |
| `apps/web/lib/api.ts` | كل API calls من Frontend | ⭐⭐⭐ |

### تدفق رسالة واردة (للمطوّر الجديد)
```
1. Meta → POST /api/v1/webhooks/whatsapp
   └─ radd/webhooks/router.py (verify HMAC → dedup → enqueue Redis)

2. Redis Stream messages:{workspace_id}
   └─ workers/message_worker.py (XREADGROUP consumer)

3. run_pipeline_async()
   └─ radd/pipeline/orchestrator.py
      ├─ normalize → detect_dialect → classify_intent
      ├─ [order_status] → radd/actions/salla.py
      ├─ [high confidence] → radd/pipeline/templates.py
      └─ [else] → retriever → generator → verifier → guardrails

4. Send response
   └─ radd/whatsapp/client.py → WhatsApp Cloud API

5. If escalated
   └─ radd/escalation/service.py → create EscalationEvent
   └─ radd/websocket/manager.py → broadcast to agents
```

---

## 8. الاختبارات

```bash
# كل الاختبارات
make test

# Backend فقط
make test-api

# Benchmark NLP (يجب ≥ 80% — المحقق 95%)
make benchmark

# Frontend فقط (type-check)
make test-web
```

### ملفات الاختبار
```
tests/test_arabic.py     ← normalizer + dialect + intent (15 test)
tests/test_guardrails.py ← PII redaction + injection (9 tests)
tests/test_pipeline.py   ← orchestrator routing
```

---

## 9. الـ CI/CD Pipeline

### GitHub Secrets المطلوبة
```
GHCR_TOKEN       → GitHub PAT (packages:write)
SSH_DEPLOY_KEY   → Private SSH key للسيرفر
DEPLOY_HOST      → IP أو hostname السيرفر
DEPLOY_USER      → SSH user (عادةً ubuntu)
SLACK_WEBHOOK_URL → (اختياري) للإشعارات
```

### Flow
```
PR فتح → test-api + test-web
push main → test → build 3 Docker images → push GHCR → deploy (SSH)
push staging → test → build → push (بدون deploy)
```

### خطوات Deploy يدوي (بدون CI)
```bash
# على السيرفر
cd /opt/radd
git pull origin main
docker compose -f infrastructure/docker-compose.prod.yml pull
docker compose -f infrastructure/docker-compose.prod.yml up -d
docker compose -f infrastructure/docker-compose.prod.yml exec api alembic upgrade head
```

---

## 10. ما لم يُبنَ بعد (الخطوات القادمة)

### أولوية عالية (قبل أول عميل)
- [ ] **End-to-end test** بواتساب حقيقي (Sandbox Meta)
- [ ] **Rate limiting** على `/api/v1/` لكل workspace
- [ ] **Error monitoring** — Sentry أو BugSnag
- [ ] **Logging centralized** — structured logs → Datadog / CloudWatch
- [ ] **Alerting** — إذا worker توقف أو escalation queue امتلأ

### أولوية متوسطة (الشهر الأول بعد الإطلاق)
- [ ] **CSAT collection** — رسالة تقييم تلقائية بعد الإغلاق
- [ ] **Conversation analytics** — رسم بياني trends في Dashboard
- [ ] **Template editor** — GUI لتعديل قوالب الردود
- [ ] **Multi-language** — دعم الإنجليزية كلغة ثانية
- [ ] **Terraform IaC** — infrastructure as code للـ AWS

### أولوية منخفضة (مستقبلي)
- [ ] **Fine-tuned intent model** — بدل keyword matching (v1)
- [ ] **Dialect detection v1** — model-based بدل rule-based
- [ ] **iOS/Android app** — لموظفي الخدمة
- [ ] **Salla OAuth flow** — ربط متاجر بشكل آلي

---

## 11. المشاكل المعروفة (Known Issues)

| المشكلة | التأثير | الحل المؤقت |
|---------|---------|------------|
| xlm-roberta يحمّل عند أول تشغيل (~2GB) | Worker بطيء أول مرة | Pre-warm بـ dummy request |
| uv.lock غير موجود | `uv sync --frozen` يفشل | شغّل `uv lock` أولاً |
| pnpm-lock.yaml غير موجود | Docker build يفشل | شغّل `pnpm install` أولاً لتوليد الـ lockfile |
| CORS في dev | الـ API يرفض من :3000 | CORS_ORIGINS=http://localhost:3000 في .env |
| KBChunk tsv column | يحتاج trigger PostgreSQL من migration 0002 | `make migrate` يحلها |

---

## 12. أوامر Makefile المرجعية

```bash
make help          # عرض كل الأوامر
make up            # تشغيل Docker services
make down          # إيقاف Docker services
make migrate       # DB migrations
make migrate-down  # rollback خطوة
make migrate-create# إنشاء migration جديد
make seed          # بيانات تجريبية
make api           # FastAPI :8000
make worker        # Message worker
make web           # Next.js :3000
make install       # uv sync + pnpm install
make test          # كل الاختبارات
make test-api      # pytest فقط
make test-web      # vitest فقط
make benchmark     # NLP benchmark
make lint          # ruff + eslint
make typecheck     # mypy + tsc
make build         # Docker images
```

---

## 13. معلومات الاتصال والمراجع

### المستندات المرجعية
| الملف | الغرض |
|-------|-------|
| `docs/Technical_Profile.md` | الملف التعريفي التقني الكامل |
| `docs/Radd_Technical_Execution_Pack.md` | المواصفات الأصلية (source of truth) |
| `docs/Radd_Founder_Control_Document_v2.md` | رؤية المنتج والقرارات الاستراتيجية |
| `README.md` | Quick Start + Architecture |
| `.env.example` | كل المتغيرات البيئية مشروحة |

### Swagger API Docs
```
http://localhost:8000/docs      ← Swagger UI (dev)
http://localhost:8000/redoc     ← ReDoc
```

### MinIO Console (local)
```
http://localhost:9001
User: راجع MINIO_ROOT_USER في .env
```

### Qdrant Dashboard (local)
```
http://localhost:6333/dashboard
```

---

## 14. Checklist التسليم

### ✅ اكتمل
- [x] Backend API (FastAPI) — كامل
- [x] NLP Pipeline (7 مراحل)
- [x] WhatsApp integration
- [x] Knowledge Base + RAG
- [x] Escalation system + WebSocket
- [x] Salla API integration
- [x] PII Guardrails
- [x] Admin API (KPIs + settings + users)
- [x] Frontend Dashboard (RTL, 5 صفحات)
- [x] Database schema (9 جداول + RLS)
- [x] Alembic migrations (3 ملفات)
- [x] Docker images (3)
- [x] Nginx reverse proxy
- [x] CI/CD pipeline (GitHub Actions)
- [x] Unit tests (25+)
- [x] NLP Benchmark 95% ✅
- [x] README + Technical Profile + Handover

### ⏳ يحتاج إجراء قبل الإطلاق
- [ ] ملء `.env` ببيانات حقيقية
- [ ] إنشاء `uv.lock` و `pnpm-lock.yaml`
- [ ] SSL certificates
- [ ] تحديث `yourdomain.com` في `nginx.conf`
- [ ] إعداد WhatsApp Webhook على Meta Console
- [ ] اختبار end-to-end كامل
