# خطة دمج حزمة RADD Implementation Package v2

**التاريخ:** 11 مارس 2026  
**الغرض:** دمج محتويات `RADD_Implementation_Package_v2.zip` داخل مشروع RADD الحالي

---

## نظرة عامة

| المرحلة | المدة التقديرية | الوصف |
|---------|------------------|-------|
| 1. التحضير | 30 دقيقة | التبعيات، المجلدات، الـ branch |
| 2. نسخ الملفات | 30 دقيقة | نسخ الملفات الجديدة |
| 3. إصلاح التكامل | 1–2 ساعة | تعديل الـ imports والـ fallbacks |
| 4. تعديل الـ Orchestrator | 1 ساعة | ربط intent_v2 و verifier_v2 |
| 5. ربط الـ Routers | 45 دقيقة | Revenue، CSAT، Rate Limiter |
| 6. Worker و Docker | 30 دقيقة | تفعيل message_worker_v2 |
| 7. الاختبار | 1–2 ساعة | تشغيل الاختبارات والتحقق |

**الإجمالي:** ~6–8 ساعات عمل

---

## المرحلة 1: التحضير

### 1.1 إنشاء branch

```bash
cd /Users/ramymortada/Documents/New\ project
git checkout -b feature/v2-integration
```

### 1.2 إضافة التبعيات

في `apps/api/pyproject.toml`، أضف:

```toml
# في قائمة dependencies:
"instructor>=1.0.0",
```

ثم نفّذ:

```bash
cd apps/api && uv sync
```

### 1.3 إنشاء المجلدات الناقصة

```bash
mkdir -p apps/api/radd/middleware
mkdir -p apps/api/radd/monitoring
mkdir -p apps/api/scripts
touch apps/api/radd/middleware/__init__.py
touch apps/api/radd/monitoring/__init__.py
touch apps/api/scripts/__init__.py
```

### 1.4 استخراج الحزمة (إذا لم تكن مستخرجة)

```bash
unzip -o ~/Desktop/RADD_Implementation_Package_v2.zip -d /tmp/radd_v2
# المسار: /tmp/radd_v2/radd_implementation/
```

---

## المرحلة 2: نسخ الملفات

| الملف المصدر (من الحزمة) | الوجهة (في المشروع) |
|--------------------------|----------------------|
| `pipeline/intent_v2.py` | `apps/api/radd/pipeline/intent_v2.py` |
| `pipeline/verifier_v2.py` | `apps/api/radd/pipeline/verifier_v2.py` |
| `middleware/rate_limiter.py` | `apps/api/radd/middleware/rate_limiter.py` |
| `monitoring/alerts.py` | `apps/api/radd/monitoring/alerts.py` |
| `dashboard_components/revenue_attribution.py` | `apps/api/radd/admin/revenue_router.py` |
| `dashboard_components/csat_collection.py` | `apps/api/radd/conversations/csat.py` |
| `workers/message_worker_v2.py` | `apps/api/workers/message_worker_v2.py` |
| `scripts/migrate_streams.py` | `apps/api/scripts/migrate_streams.py` |
| `tests/test_v2_components.py` | `apps/api/tests/test_v2_components.py` |

**ملاحظة:** المشروع يحتوي بالفعل على `radd.revenue.attribution` و `analytics_router` يعرض `/admin/revenue/summary`.  
ملف `revenue_attribution.py` من الحزمة يقدم منطقاً مختلفاً (ربط محادثات → طلبات). يمكن:
- **الخيار أ:** استبدال/دمج المنطق في `radd/revenue/attribution.py` واستخدام الـ router الحالي
- **الخيار ب:** إضافة `revenue_router.py` كـ router منفصل مع endpoints إضافية

---

## المرحلة 3: إصلاح التكامل

### 3.1 `intent_v2.py` — إصلاح الـ Fallback

الـ fallback يستدعي `classify_intent` الذي يعيد `IntentResult` (dataclass)، وليس `dict`.

**البحث عن:** `_fallback_classify` أو استخدام `legacy_result.get(...)`

**التعديل المقترح:**

```python
# في intent_v2.py، داخل _fallback_classify:
from radd.pipeline.intent import classify_intent

legacy_result = classify_intent(text)
# استخدم:
return {
    "intent_name": legacy_result.intent,  # وليس .get("intent", ...)
    "confidence": legacy_result.confidence,
    "entities": {},
}
```

### 3.2 `message_worker_v2.py` — إصلاح استيراد Redis

**البحث عن:** `radd.db.redis` أو `get_redis`

**التعديل:**

```python
# من:
from radd.db.redis import get_redis

# إلى:
from radd.deps import get_redis
```

وتحقق أن `get_redis` في `radd.deps` يعيد Redis client متوافق (async إذا كان الـ worker async).

### 3.3 `test_v2_components.py` — إصلاح الـ imports

```python
# من:
from radd_implementation.pipeline.intent_v2 import ...

# إلى:
from radd.pipeline.intent_v2 import ...
```

---

## المرحلة 4: تعديل الـ Orchestrator

الملف: `apps/api/radd/pipeline/orchestrator.py`

### 4.1 تغيير الاستيرادات

```python
# أضف (مع الاحتفاظ بالقديم للـ run_pipeline السينكروني):
from radd.pipeline.intent_v2 import (
    classify_intent_llm,
    get_intent_instance,
    OrderStatusIntent,
    ShippingInquiryIntent,
    ReturnPolicyIntent,
    ProductInquiryIntent,
    ComplaintIntent,
    OrderCancelIntent,
    GreetingIntent,
    StoreHoursIntent,
    GeneralInquiryIntent,
    GuardrailTriggeredIntent,
)
from radd.pipeline.verifier_v2 import verify_response_async
```

### 4.2 في `run_pipeline_async` — استبدال التصنيف

```python
# من:
intent_result = classify_intent(normalized)
intent = intent_result.intent

# إلى (يحتاج redis من الـ context):
redis = ...  # من deps أو من الـ context
intent_result_dict = await classify_intent_llm(normalized, redis_client=redis)
intent_instance = get_intent_instance(intent_result_dict)
intent = intent_result_dict["intent_name"]

# خريطة النوايا للـ templates الحالية:
# shipping_inquiry → shipping
if intent == "shipping_inquiry":
    intent = "shipping"
```

### 4.3 في `run_pipeline_async` — استبدال التحقق

```python
# من:
from radd.pipeline.verifier import verify_response_fast
c_verify, is_grounded = verify_response_fast(response, passages)

# إلى:
c_verify, is_grounded, details = await verify_response_async(response, passages)
# استخدم details اختيارياً للتسجيل
```

### 4.4 تمرير Redis إلى `run_pipeline_async`

يجب أن يستقبل `run_pipeline_async` معامل `redis` أو يجلب Redis من الـ deps.  
الـ message worker يستدعي الـ pipeline — تأكد أن الـ worker يمرر `redis` عند استدعاء `run_pipeline_async`.

---

## المرحلة 5: ربط الـ Routers

### 5.1 Revenue Router

إذا اخترت إضافة router منفصل:

في `apps/api/radd/admin/router.py`:

```python
from radd.admin.revenue_router import router as revenue_router

router.include_router(revenue_router, prefix="")
```

إذا كان `revenue_attribution.py` من الحزمة يقدم نفس الوظيفة مع منطق مختلف، يمكن دمج المنطق في `radd/revenue/attribution.py` والاعتماد على `analytics_router` الحالي.

### 5.2 CSAT

في `apps/api/radd/conversations/router.py` (أو الملف المناسب):

- استيراد دوال جمع CSAT من `radd.conversations.csat`
- ربطها بحدث إغلاق المحادثة (مثلاً webhook أو callback)

### 5.3 Rate Limiter Middleware

المشروع يستخدم بالفعل **SlowAPI** (`radd.limiter`). الـ middleware من الحزمة يستخدم **Redis sliding window** ويمكن استخدامه كطبقة إضافية أو بديل.

في `apps/api/radd/main.py`:

```python
from radd.middleware.rate_limiter import RateLimitMiddleware

# الـ middleware يتوقع redis_client. يمكن تخزين Redis في app.state
# داخل lifespan ثم الوصول إليه من الـ middleware عبر request.app.state.redis
app.add_middleware(RateLimitMiddleware, redis_client=None)  # أو تمرير redis من deps
```

تحقق من كود `rate_limiter.py` — إذا كان `redis_client=None` يتخطى الـ rate limiting، يمكن إضافته تدريجياً.

### 5.4 Alerts (اختياري)

نظام التنبيهات يمكن تشغيله كـ background task أو كـ endpoint للـ health check.  
راجع `monitoring/alerts.py` لمعرفة كيفية تفعيله (مثلاً Slack webhook، إلخ).

---

## المرحلة 6: Worker و Docker

### 6.1 تفعيل Worker v2

**تم التنفيذ:**
- `make worker-v2` — تشغيل العامل v2 محلياً
- `make worker` — العامل الأصلي (الافتراضي)

في `docker-compose`، لتشغيل v2:

```yaml
worker:
  command: python -m workers.message_worker_v2
  deploy:
    replicas: 2
```

### 6.2 Webhook

المشروع يستخدم بالفعل streams لكل workspace (`messages:{workspace_id}`).  
إذا كان `message_worker_v2` يتوقع نفس النموذج، لا حاجة لتعديل الـ webhook.  
راجع `webhook_patch.py` في الحزمة للمقارنة.

### 6.3 سكريبت الترحيل

`scripts/migrate_streams.py` يُستخدم إذا كان لديك رسائل قديمة في stream واحد (`messages`) وتريد نقلها إلى streams لكل workspace.  
نفّذه يدوياً عند الحاجة:

```bash
cd apps/api && uv run python -m scripts.migrate_streams
```

---

## المرحلة 7: الاختبار

```bash
cd apps/api

# اختبارات v2
uv run pytest tests/test_v2_components.py -v

# اختبارات التكامل (إذا Docker متاح)
uv run pytest tests/integration/ -v

# اختبارات المشروع بالكامل
uv run pytest tests/ --ignore=tests/integration/ -v
```

---

## خطة التراجع (Rollback)

| المكون | طريقة التراجع | الوقت |
|--------|----------------|-------|
| Intent v2 | إرجاع import في orchestrator إلى `classify_intent` | < 5 دقائق |
| Verifier v2 | إرجاع import إلى `verify_response_fast` | < 5 دقائق |
| Worker v2 | تغيير command في docker-compose إلى `message_worker` | < 5 دقائق |
| Rate Limiter | إزالة الـ middleware من main.py | < 2 دقيقة |
| Revenue/CSAT | إزالة الـ routers أو تعطيل الـ endpoints | < 5 دقائق |

---

## تفعيل مكونات v2

| المكون | متغير البيئة | القيمة |
|--------|---------------|--------|
| Intent v2 (LLM) | `USE_INTENT_V2` | `true` |
| Verifier v2 (NLI) | `USE_VERIFIER_V2` | `true` |

(يُقرأ من radd.config.settings)

## قائمة تحقق نهائية

- [x] `instructor` مضاف في pyproject.toml
- [ ] مجلدات `middleware` و `monitoring` و `scripts` موجودة
- [ ] كل الملفات منسوخة إلى المسارات الصحيحة
- [ ] إصلاح fallback في intent_v2
- [ ] إصلاح Redis import في message_worker_v2
- [ ] إصلاح imports في test_v2_components
- [ ] orchestrator يستخدم intent_v2 و verifier_v2
- [ ] Redis يُمرَّر إلى run_pipeline_async
- [ ] Revenue router مربوط (أو منطق مدمج)
- [ ] CSAT مربوط بحدث إغلاق المحادثة
- [ ] Rate Limiter middleware مضاف
- [ ] Worker v2 مفعّل في Docker/Makefile
- [ ] كل الاختبارات تمر

---

## ملاحظات إضافية

1. **متغيرات البيئة:** قد تحتاج `OPENAI_API_KEY` لـ intent_v2. تحقق من `radd/config.py`.
2. **Redis decode_responses:** المشروع يستخدم `decode_responses=True`. تأكد أن worker_v2 يتعامل مع strings وليس bytes.
3. **الـ Verifier:** verifier_v2 يستخدم نموذج NLI. تحقق أن النموذج `joeddav/xlm-roberta-large-xnli` (أو المحدد في verifier_v2) يُحمَّل بشكل صحيح.
