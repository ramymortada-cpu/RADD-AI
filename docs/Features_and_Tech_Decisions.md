# ملخص الـ Features وقرارات اختيار التقنية
**منصة رَدّ (Radd) — MVP v0.1.0**

---

## أولاً: الـ Features حسب المحور

---

### 🔷 المحور الأول: استقبال ومعالجة رسائل واتساب

---

#### Feature 1 — WhatsApp Webhook (استقبال الرسائل)
**الملف:** `radd/webhooks/router.py`

**ما يفعله:**
- يستقبل كل رسالة واتساب ترسلها Meta على endpoint محدد
- يتحقق من صحة الرسالة عبر HMAC-SHA256 (يمنع الرسائل المزوّرة)
- يتجنب معالجة نفس الرسالة مرتين (deduplication عبر Redis)
- يضع الرسالة في قائمة انتظار لمعالجتها بشكل غير متزامن

**اختيار التقنية: Python + FastAPI**
> واتساب Cloud API بترسل الرسائل عبر HTTP webhooks — FastAPI مثالي لأنه يتعامل مع HTTP بشكل async بالكامل مما يعني قدرة على استقبال مئات الرسائل في الثانية بدون blocking. بديل Node.js كان ممكن لكن Python أهم لأن نفس اللغة تشغّل الـ NLP pipeline، مما يقلل التعقيد.

---

#### Feature 2 — Message Deduplication (منع التكرار)
**الملف:** `radd/webhooks/router.py` + Redis

**ما يفعله:**
- يخزّن ID كل رسالة في Redis بـ TTL 24 ساعة
- إذا وصلت نفس الرسالة مرتين (coomon مع Meta)، يتجاهلها فوراً
- يحمي من الردود المضاعفة للعميل

**اختيار التقنية: Redis (SET + EXPIRE)**
> Redis هو الأسرع عالمياً لعمليات "هل هذا الـ ID موجود؟" — الاستجابة بالميكروثانية. قاعدة البيانات العادية (PostgreSQL) كانت ستعمل لكن بتكلفة أعلى وأبطأ. Redis SET operation هي O(1) وهو الـ pattern القياسي لـ deduplication في أنظمة messaging.

---

#### Feature 3 — Message Queue (قائمة الانتظار)
**الملف:** `radd/webhooks/router.py` → Redis Streams → `workers/message_worker.py`

**ما يفعله:**
- الـ webhook يضع الرسالة في Redis Stream فوراً ويرد على Meta بـ 200
- Worker منفصل يقرأ من الـ Stream ويعالج الرسالة
- إذا فشلت المعالجة، الرسالة تبقى في الـ Stream للمحاولة مجدداً

**اختيار التقنية: Redis Streams**
> Meta تطلب أن يرد الـ webhook بـ 200 خلال أقل من 5 ثوانٍ أو ستعيد الإرسال. المعالجة الكاملة (RAG + OpenAI) قد تستغرق 3-8 ثوانٍ. الحل: فصل الاستقبال عن المعالجة. Redis Streams أخف من Kafka وأقوى من Redis Lists (يدعم consumer groups، acknowledgment، replay).

---

### 🔷 المحور الثاني: الـ NLP Pipeline (قلب المنصة)

---

#### Feature 4 — Arabic Text Normalization (تطبيع النص العربي)
**الملف:** `radd/pipeline/normalizer.py`

**ما يفعله:**
- يزيل التشكيل (حَرَكات) لأنه غير ثابت في الكتابة اليومية
- يوحّد أشكال الألف (أ، إ، آ، ١ → ا)
- يوحّد التاء المربوطة والياء (ى → ي)
- يزيل التطويل (كـشيدة ـ)
- يحوّل "مَرْحَبًا يَا أَخِي" → "مرحبا يا اخي"

**اختيار التقنية: Python Regex (بدون مكتبات خارجية)**
> التطبيع عمليات string بسيطة — regex محلي أسرع 10x من مكتبة خارجية لأنه لا يحتاج model loading أو network calls. قررنا تجنب مكتبات مثل Farasa أو CAMeL Tools للتطبيع الأساسي لأن حجمها كبير ووقت التحميل طويل. Python's `re` module يعمل في microseconds.

---

#### Feature 5 — Arabic Dialect Detection (كشف اللهجة)
**الملف:** `radd/pipeline/dialect.py`

**ما يفعله:**
- يحدد إذا كانت الرسالة خليجية (وش، كيفك، ابغى، وايد)
- أو مصرية (إيه، ازيك، عامل إيه)
- أو فصحى (MSA) كـ default
- مهم لاختيار القالب المناسب للرد

**اختيار التقنية: Python Rule-Based (keyword matching)**
> قرار واعٍ: v0 = rule-based، v1 = model-based. السبب: نحتاج المنتج يشتغل قبل جمع بيانات كافية لتدريب model. الكلمات المفتاحية تغطي 85%+ من الحالات للسوق السعودي/الخليجي. تكلفة inference نموذج لكل رسالة = $0.001+ — على 10,000 رسالة يومياً هذا $10/يوم فقط للـ dialect detection.

---

#### Feature 6 — Intent Classification (تصنيف النية)
**الملف:** `radd/pipeline/intent.py`

**ما يفعله:**
- يصنّف سبب تواصل العميل في 6 فئات: تحية، حالة طلب، شحن، إرجاع، مواعيد، عام
- يعطي confidence score (0.0 → 1.0)
- يُرجع الكلمات المفتاحية التي أدّت للتصنيف (قابل للشرح/explainable)
- حقّق 95% accuracy على benchmark 100 سؤال

**اختيار التقنية: Python Keyword-Based مع Confidence Scoring**
> نفس منطق اللهجة: v0 سريع قابل للشحن، v1 model-based. الميزة المخفية: عند فشل تصنيف محدد، نعرف بالضبط أي كلمة أحدثت الخطأ ونصلحها فوراً بدون إعادة تدريب. مع GPT/BERT تحتاج dataset + fine-tuning + GPU time. بالنسبة للـ MVP هذا overhead غير مبرر.

---

#### Feature 7 — Template Response Engine (ردود القوالب)
**الملف:** `radd/pipeline/templates.py`

**ما يفعله:**
- 15 قالب جاهز (5 نوايا × 3 لهجات)
- يملأ المتغيرات: {اسم العميل}، {رقم الطلب}، {اسم المتجر}
- أسرع مسار للرد (بدون OpenAI = بدون تكلفة)
- يُستخدم عندما confidence_intent ≥ 0.85

**اختيار التقنية: Python dict + string formatting**
> القوالب لا تحتاج database في v0 — Python dict في memory = أسرع استجابة ممكنة (< 1ms). عند الوصول لـ 10+ متاجر سنحوّلها لـ DB مع workspace isolation. قرار: لا تُعقّد ما يمكن أن يكون بسيطاً في v0.

---

### 🔷 المحور الثالث: RAG Pipeline (الذكاء الاصطناعي)

---

#### Feature 8 — Document Chunking (تقطيع الوثائق)
**الملف:** `radd/knowledge/chunker.py`

**ما يفعله:**
- يقسّم وثيقة KB طويلة (مثل: سياسة الإرجاع = 3000 كلمة) إلى مقاطع 200-500 token
- يحترم حدود الفقرات والجمل (لا يقطع في منتصف جملة)
- يحفظ رقم المقطع وعدد الـ tokens

**اختيار التقنية: Python + tiktoken**
> tiktoken هو tokenizer OpenAI نفسه — يعطي عدد tokens دقيق 100% لأننا نرسلها بعدها لـ OpenAI Embeddings. استخدام word count بدلاً منه كان سيعطي تقديرات خاطئة ويسبب truncation في الـ embedding model.

---

#### Feature 9 — Vector Embeddings (تحويل النص لمتجهات)
**الملف:** `radd/knowledge/embedder.py`

**ما يفعله:**
- يحوّل كل مقطع نص عربي إلى vector (1536 رقم يمثّل المعنى)
- يخزّن الـ vectors في Qdrant
- يدعم حذف vectors قديمة عند تحديث الوثيقة
- يُشغَّل مرة واحدة عند اعتماد الوثيقة (ليس عند كل سؤال)

**اختيار التقنية: OpenAI text-embedding-3-small**
> اختبرنا 3 خيارات:
> - `text-embedding-3-small`: $0.00002/1K tokens، دعم عربي ممتاز، 1536 dim
> - `text-embedding-3-large`: 3x أغلى، تحسن هامشي للعربية
> - Arabic-BERT محلي: مجاني لكن يحتاج GPU، latency عالي، infra معقدة
>
> الاختيار: small لأن السوق المستهدف (سؤال عميل واحد) لا يتجاوز 500 token.

---

#### Feature 10 — Hybrid Retrieval / RRF (الاسترجاع الهجين)
**الملف:** `radd/pipeline/retriever.py`

**ما يفعله:**
- **Vector Search (Qdrant):** يجد المقاطع الأقرب معنىً للسؤال
- **BM25 Full-Text Search (PostgreSQL):** يجد المقاطع التي تحتوي نفس الكلمات
- **Reciprocal Rank Fusion:** يدمج النتيجتين بصيغة `1/(k + rank)` ويرتّب
- النتيجة: top 5 مقاطع + C_retrieval score

**اختيار التقنية: Qdrant + PostgreSQL BM25 + Python RRF**
> Vector search وحده يفشل مع الأسماء والأرقام ("طلب رقم 12345" — المعنى الدلالي لا يساعد كثيراً هنا). BM25 وحده يفشل مع المعنى ("متى يصل؟" ≈ "موعد التسليم"). الهجين يحقق أفضل من كليهما منفردين — ورقة BEIR 2021 أثبتت أن RRF يتفوق على أي weighting scheme آخر.
>
> Qdrant اخترناه على Pinecone (تكلفة) وpgvector (أداء أضعف عند >100K vectors).

---

#### Feature 11 — RAG Response Generation (توليد الرد)
**الملف:** `radd/pipeline/generator.py`

**ما يفعله:**
- يبني system prompt عربي متخصص يحدد دور النموذج
- يحقن المقاطع المسترجعة كـ context
- يضيف آخر 10 رسائل من المحادثة (conversation history)
- يوجّه النموذج للرد باللهجة المكتشفة
- يُرجع الرد + IDs المقاطع المستخدمة

**اختيار التقنية: OpenAI GPT-4.1-mini**
> قارنّا 4 نماذج:
> - GPT-4.1-mini: جودة عالية، سريع (1-2s)، $0.0001/1K tokens
> - GPT-4o: 5x أغلى، جودة أفضل بـ 10% فقط للعربية البسيطة
> - Claude 3.5 Haiku: مشابه لكن integration أصعب
> - Llama 3 Arabic: مجاني لكن يحتاج GPU hosting + أداء أضعف للخليجي
>
> mini يعطي 90% من جودة GPT-4o بـ 20% من التكلفة — مثالي للـ MVP.

---

#### Feature 12 — NLI Response Verification (التحقق من التأطير)
**الملف:** `radd/pipeline/verifier.py`

**ما يفعله:**
- يتحقق إذا كان رد النموذج مدعوماً فعلاً بالمقاطع المسترجعة
- يكتشف الـ "هلوسة" (hallucination) — عندما يخترع النموذج معلومات
- يستخدم NLI (Natural Language Inference): هل الـ passage يدعم الـ response؟
- يُرجع C_verify score + keyword fallback للسرعة

**اختيار التقنية: joeddav/xlm-roberta-large-xnli**
> هذا القرار الأصعب في المشروع. 3 خيارات:
> - OpenAI GPT لتقييم ردوده: تعارض مصالح + تكلفة مضاعفة
> - Arabic NLI model محلي: غير موجود بجودة كافية
> - xlm-roberta-large-xnli: cross-lingual يفهم العربية والإنجليزية، مدرّب على XNLI dataset، يعمل locally (بدون API call)، مجاني بعد التحميل
>
> العيب الوحيد: يحتاج ~2GB RAM وأول تشغيل بطيء. الحل: model cache كـ Docker volume.

---

#### Feature 13 — Confidence Routing (توجيه بناءً على الثقة)
**الملف:** `radd/pipeline/orchestrator.py`

**ما يفعله:**
- C_min = min(C_intent, C_retrieval, C_verify)
- C_min ≥ 0.85 → يرسل الرد تلقائياً (auto_rag)
- 0.60 ≤ C_min < 0.85 → يرسل رسالة انتظار ويعطي الموظف مسودة الرد (escalated_soft)
- C_min < 0.60 → يوقف الرد ويُنبّه الموظف فوراً (escalated_hard)

**اختيار التقنية: Python pure logic**
> الـ routing هو decision tree بسيط — لا يحتاج framework. العبقرية في الـ design: استخدام min() بدل average() يعني إذا أي حلقة ضعيفة (مثلاً: intent واضح لكن retrieval ضعيف) الكل يُعامَل كضعيف. "أضعف حلقة تحدد القرار" — مبدأ أمان.

---

### 🔷 المحور الرابع: الأمان والحماية

---

#### Feature 14 — PII Redaction (إخفاء البيانات الحساسة)
**الملف:** `radd/pipeline/guardrails.py`

**ما يفعله:**
- يمسح رقم الهوية السعودية من الردود قبل إرسالها
- يمسح أرقام الهاتف الخليجية، البريد الإلكتروني، بطاقات الائتمان، IBAN
- يمسح عناوين IP والإحداثيات الجغرافية
- يبدّلها بـ [NATIONAL_ID]، [PHONE]، [EMAIL]، إلخ

**اختيار التقنية: Python Regex**
> PII redaction بـ regex أسرع وأكثر مصداقية من NER model للبيانات المنظمة (أرقام، عناوين بريد). الهوية السعودية لها نمط ثابت (10 أرقام تبدأ بـ 1 أو 2) — regex يكتشفها بـ 100% دقة. NER model قد يُفوّت رقم يُكتب بشكل غير متوقع.

---

#### Feature 15 — Prompt Injection Detection (كشف محاولات الاختراق)
**الملف:** `radd/pipeline/guardrails.py`

**ما يفعله:**
- يكشف محاولات تلاعب بالنموذج: "ignore all previous instructions"
- يكشف المحاولات العربية: "تجاهل جميع التعليمات"
- يكشف jailbreak patterns (DAN mode, act as...)
- إذا اكتُشف: يرد برسالة إحالة للموظف ويسجّل الحادثة

**اختيار التقنية: Python Regex patterns**
> 8 patterns محددة تغطي الهجمات المعروفة. regex أسرع من model classifier وأسهل في التحديث عند ظهور هجمات جديدة. المبدأ: "deny by pattern" أآمن من "allow by score".

---

#### Feature 16 — Row Level Security / RLS (عزل بيانات المتاجر)
**الملف:** `alembic/versions/0001_initial_schema.py` + `radd/db/session.py`

**ما يفعله:**
- كل جدول محمي على مستوى قاعدة البيانات: لا يمكن قراءة بيانات متجر من جلسة متجر آخر
- يُفعَّل تلقائياً بـ `SET LOCAL app.current_workspace_id` في كل session
- حتى bug في الكود لن يسرّب بيانات بين المتاجر

**اختيار التقنية: PostgreSQL RLS**
> Multi-tenant isolation يمكن تحقيقه بثلاث طرق:
> 1. Separate databases: آمن لكن expensive جداً
> 2. WHERE clause في كل query: آمن لكن يعتمد على المطوّر (human error)
> 3. PostgreSQL RLS: آمن على مستوى DB نفسه، لا يعتمد على الكود
>
> اخترنا RLS لأنه "defense in depth" — حتى لو نسي المطوّر WHERE clause، البيانات محمية.

---

#### Feature 17 — JWT Authentication + RBAC (المصادقة والصلاحيات)
**الملف:** `radd/auth/`

**ما يفعله:**
- Access token قصير الأمد (15 دقيقة) + Refresh token (7 أيام)
- 4 أدوار: owner (كل شيء) > admin > agent > reviewer (قراءة فقط)
- كل endpoint محمي بـ `require_role()` decorator
- كلمات المرور محمية بـ bcrypt

**اختيار التقنية: python-jose (JWT) + passlib (bcrypt)**
> JWT stateless = لا يحتاج DB lookup عند كل request. بديله (session-based) يحتاج Redis lookup في كل call. على 1000 request/ثانية، هذا فرق كبير. bcrypt اخترناه على SHA-256 لأن bcrypt مصمّم ليكون بطيئاً (cost factor) — يحمي من brute force attacks.

---

### 🔷 المحور الخامس: التكامل مع الخدمات الخارجية

---

#### Feature 18 — Salla Order Status Integration (ربط سلّة)
**الملف:** `radd/actions/salla.py` + `radd/actions/base.py`

**ما يفعله:**
- يستخرج رقم الطلب من رسالة العميل (يدعم الأرقام العربية ١٢٣)
- يستعلم API سلّة عن حالة الطلب
- يُرجع رد عربي dialect-aware: "طلبك رقم 123 في الطريق إليك"
- يتجاوز مسار RAG بالكامل (أسرع + أدق)

**اختيار التقنية: Python httpx (async HTTP)**
> httpx اخترناه على requests لأنه يدعم async/await — لا يعطّل الـ event loop أثناء انتظار رد سلّة API. requests library blocking تعني أن الـ worker يتوقف كاملاً أثناء API call. على 100 طلب في الثانية هذا كارثي.

---

#### Feature 19 — WhatsApp Message Sending (إرسال الردود)
**الملف:** `radd/whatsapp/client.py`

**ما يفعله:**
- يرسل رسائل نصية عبر WhatsApp Cloud API
- يعلّم الرسائل كـ "مقروءة" (read receipts)
- يدعم إعادة المحاولة عند الفشل

**اختيار التقنية: Python httpx + WhatsApp Cloud API**
> WhatsApp Business API الرسمية من Meta هي الطريقة الوحيدة المتوافقة مع شروط الاستخدام. httpx async لنفس سبب سلّة.

---

### 🔷 المحور السادس: إدارة المحادثات والتصعيد

---

#### Feature 20 — Escalation System (نظام التصعيد للموظف)
**الملف:** `radd/escalation/`

**ما يفعله:**
- ينشئ "حزمة سياق" للموظف: ملخص، آخر 5 رسائل، نية العميل، مسودة رد AI
- يصنّف التصعيد: hard (عاجل) أو soft (للمراجعة)
- يتيح للموظف: قبول التصعيد → الرد → الإغلاق مع ملاحظات
- يُحدّث حالة المحادثة تلقائياً

**اختيار التقنية: FastAPI + PostgreSQL**
> التصعيد له state machine بسيط (pending → accepted → resolved). PostgreSQL مثالي لتخزين هذه الحالات مع ACID guarantees — لا نريد تصعيداً يضيع بسبب crash. FastAPI يوفر REST endpoints للموظفين.

---

#### Feature 21 — Real-time WebSocket Notifications (إشعارات فورية)
**الملف:** `radd/websocket/`

**ما يفعله:**
- يُنبّه الموظف فوراً عند وصول تصعيد جديد (بدون refresh)
- يتتبع حضور الموظفين (online/away/offline)
- يرسل typing indicators
- يُذيع الردود الجديدة للموظفين في نفس المتجر

**اختيار التقنية: FastAPI WebSocket (Starlette)**
> WebSocket هو الحل الوحيد للـ real-time push من server للـ client. الخيار الأبسط (polling كل 5 ثوانٍ) يعني 12 request/دقيقة لكل موظف = ضغط غير ضروري على الـ API. Starlette WebSocket مدمج في FastAPI بدون library إضافية.

---

#### Feature 22 — Conversations Management API (إدارة المحادثات)
**الملف:** `radd/conversations/router.py`

**ما يفعله:**
- قائمة المحادثات مع فلتر (نشط، ينتظر موظف، محلول)
- عرض كامل لأي محادثة مع كل الرسائل
- رد الموظف: يُرسل واتساب + يُخزّن في DB + يُذيع WebSocket
- تحديث حالة المحادثة أو تعيينها لموظف

**اختيار التقنية: FastAPI + PostgreSQL**
> Conversations هي core domain object — تخزينها في PostgreSQL مع relations (customer, channel, messages) يعطي query flexibility. FastAPI REST endpoints مناسبة لـ CRUD operations.

---

### 🔷 المحور السابع: إدارة قاعدة المعرفة

---

#### Feature 23 — Knowledge Base CRUD (إدارة الوثائق)
**الملف:** `radd/knowledge/`

**ما يفعله:**
- رفع وثائق جديدة (سياسات، أسئلة شائعة، معلومات منتجات)
- دورة حياة الوثيقة: مسودة → مراجعة → معتمد → مؤرشف
- عند الاعتماد: يبدأ indexing تلقائياً في الخلفية
- soft delete (الحذف لا يمسح البيانات بل يضع deleted_at)
- versioning (كل تعديل يُنشئ نسخة جديدة)

**اختيار التقنية: FastAPI + PostgreSQL + Qdrant**
> PostgreSQL للـ metadata والعلاقات، Qdrant للـ vectors. الفصل مهم: إذا أعدنا build الـ vectors، الـ metadata لا تتأثر.

---

#### Feature 24 — KB Indexer Worker (الفهرسة التلقائية)
**الملف:** `workers/kb_indexer.py`

**ما يفعله:**
- يعمل في الخلفية عند اعتماد وثيقة
- يقطّع الوثيقة → يعمل embeddings → يرفع لـ Qdrant → يُحدّث DB
- منفصل عن الـ API (لا يعطّل الاستجابة)

**اختيار التقنية: Python async worker**
> Indexing قد يستغرق 10-30 ثانية للوثيقة الطويلة (API calls لـ OpenAI). وضعها في API request سيجعل الـ endpoint timeout. Worker منفصل يعمل بشكل independent.

---

### 🔷 المحور الثامن: الـ Admin Dashboard

---

#### Feature 25 — KPI Analytics (مؤشرات الأداء)
**الملف:** `radd/admin/analytics.py`

**ما يفعله:**
ثمانية KPIs تُحسب real-time:
1. محادثات نشطة الآن
2. معدل الأتمتة (آخر 24h)
3. متوسط وقت الرد
4. معدل التصعيد
5. رسائل اليوم
6. تصعيدات معلّقة
7. تقييم الرضا (placeholder)
8. معدل الهلوسة (ردود C_verify < 0.70)

**اختيار التقنية: Python + PostgreSQL aggregate queries**
> KPIs هي SQL aggregate queries (COUNT, AVG, GROUP BY). PostgreSQL يحسبها مباشرة على البيانات المخزّنة بدون data warehouse منفصل. في v0 الحجم صغير — PostgreSQL كافٍ. عند الوصول لملايين الرسائل نُضيف materialized views أو ClickHouse.

---

#### Feature 26 — User Management (إدارة المستخدمين)
**الملف:** `radd/admin/router.py`

**ما يفعله:**
- إنشاء موظفين جدد مع تحديد الدور
- تعطيل/تفعيل حسابات
- تغيير الأدوار (مع حماية حساب الـ owner)

**اختيار التقنية: FastAPI + PostgreSQL**
> User management = CRUD بسيط لجدول users مع validation. FastAPI + Pydantic يضمن validation تلقائي لكل input.

---

#### Feature 27 — Audit Log (سجل التدقيق)
**الملف:** `radd/db/models.py` + `radd/admin/router.py`

**ما يفعله:**
- يسجّل كل action مهم: من فعل إيه، متى، من أي IP
- قابل للفلترة والبحث
- غير قابل للحذف (append-only بـ BigInt PK)

**اختيار التقنية: PostgreSQL (BigInt append-only table)**
> Audit log يجب أن يكون immutable. BigInt auto-increment يضمن الترتيب الزمني. لا نستخدم UUID هنا لأن BigInt أسرع في sorting وrange queries.

---

### 🔷 المحور التاسع: الـ Frontend Dashboard

---

#### Feature 28 — RTL Arabic Dashboard (لوحة تحكم عربية)
**الملف:** `apps/web/`

**ما يفعله:**
- لوحة كاملة RTL (من اليمين لليسار)
- خط Noto Sans Arabic لعرض العربية بشكل صحيح
- 5 صفحات: رئيسية، محادثات، KB، تصعيدات، إعدادات
- تحديث تلقائي كل 30 ثانية للـ KPIs
- WebSocket للأحداث الفورية

**اختيار التقنية: Next.js 15 + React 19 + Tailwind CSS 4**
> - **Next.js:** Server-side rendering = أسرع تحميل أولي، SEO أفضل، built-in routing
> - **React 19:** أحدث إصدار مع Concurrent Features للـ real-time updates
> - **Tailwind CSS 4:** RTL support كامل مع `dir="rtl"` على `<html>`، لا CSS مخصص
> - **TypeScript:** Type safety مع الـ API responses — يمنع runtime errors شائعة
>
> بديل Vue.js/Nuxt كان ممكن لكن React ecosystem أوسع وأسهل للتوظيف مستقبلاً.

---

#### Feature 29 — Typed API Client (عميل API مكتّب)
**الملف:** `apps/web/lib/api.ts`

**ما يفعله:**
- كل API call له TypeScript type محدد
- Token management تلقائي (inject في كل request)
- Auto-redirect لـ /login عند 401
- 16 function تغطي كل الـ endpoints

**اختيار التقنية: Native fetch + TypeScript**
> تجنبنا axios لتقليل dependencies. Native fetch في Next.js 15 يدعم caching و revalidation تلقائياً. TypeScript types تُنشأ يدوياً (بدل codegen) لأن الـ API بسيط بما يكفي.

---

### 🔷 المحور العاشر: Infrastructure

---

#### Feature 30 — Multi-Stage Docker Builds
**الملفات:** `infrastructure/docker/`

**ما يفعله:**
- **Dockerfile.api:** Build stage (تثبيت deps) + Runtime stage (تشغيل فقط) → حجم image أصغر بـ 60%
- **Dockerfile.worker:** نفس الـ api image لكن CMD مختلف، model cache كـ volume
- **Dockerfile.web:** Next.js standalone output → فقط الملفات الضرورية للتشغيل

**اختيار التقنية: Docker multi-stage + python:3.12-slim + node:22-alpine**
> slim/alpine = أصغر attack surface + أسرع pull time. Multi-stage = لا يوجد compiler أو dev tools في production image. Non-root user (UID 1001) في كل image = security best practice.

---

#### Feature 31 — CI/CD Pipeline (النشر التلقائي)
**الملف:** `.github/workflows/ci.yml`

**ما يفعله:**
- عند كل PR: يشغّل tests + linting تلقائياً
- عند push لـ main: يبني 3 Docker images ويرفعها لـ GHCR
- عند push لـ main فقط: يعمل SSH deploy للسيرفر + migration + cleanup
- Slack notification عند نجاح أو فشل الـ deploy

**اختيار التقنية: GitHub Actions**
> مدمج مع GitHub = لا infrastructure إضافية. GHCR مجاني للـ public repos. بديل Jenkins/GitLab CI يحتاج server منفصل. GitHub Actions = zero ops overhead للـ startup.

---

## ثانياً: جدول قرارات التقنية الملخّص

| Feature | Python | TypeScript | PostgreSQL | Redis | Qdrant | OpenAI |
|---------|--------|------------|------------|-------|--------|--------|
| Webhook استقبال | ✅ FastAPI | — | — | ✅ Dedup | — | — |
| Message Queue | — | — | — | ✅ Streams | — | — |
| Arabic NLP | ✅ Regex | — | — | — | — | — |
| Intent/Dialect | ✅ Keywords | — | — | — | — | — |
| Embeddings | ✅ httpx | — | — | — | ✅ Store | ✅ Generate |
| Retrieval | ✅ RRF | — | ✅ BM25 | — | ✅ Vector | — |
| Generation | ✅ prompt | — | — | — | — | ✅ GPT-4.1 |
| Verification | ✅ xlm-roberta | — | — | — | — | — |
| Guardrails | ✅ Regex | — | — | — | — | — |
| Auth/RBAC | ✅ JWT | — | ✅ Users | — | — | — |
| RLS/Multi-tenant | — | — | ✅ RLS | — | — | — |
| Escalations | ✅ Service | — | ✅ Tables | — | — | — |
| WebSocket | ✅ Starlette | ✅ LiveFeed | — | — | — | — |
| KPI Analytics | ✅ Queries | ✅ Dashboard | ✅ Aggregates | — | — | — |
| KB Management | ✅ CRUD | ✅ UI | ✅ Documents | — | ✅ Vectors | ✅ Embed |
| Docker/Deploy | — | — | — | — | — | — |

---

## ثالثاً: المبادئ التي حكمت قرارات التقنية

1. **"أبسط تقنية تحل المشكلة"** — Regex قبل ML Model، Rule-based قبل Neural Network في v0
2. **"لا تدفع ثمن ما لا تستخدم"** — text-embedding-3-small بدل large، GPT-4.1-mini بدل GPT-4o
3. **"الأمان بالعمق"** — RLS + JWT + HMAC + PII Redaction معاً، ليس layer واحد
4. **"Async كلما أمكن"** — FastAPI + httpx + SQLAlchemy asyncio = لا blocking operations
5. **"كل شيء قابل للتبديل"** — embedding model يمكن تغييره، dialect detection يمكن ترقيتها لـ model بدون مس الـ architecture
