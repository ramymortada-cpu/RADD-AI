# Skill: Debug the NLP Pipeline

## When to Use
When the AI gives wrong answers, always escalates, or has unexpected behavior.

## Quick Diagnostic Script

Run this to test any Arabic message through the full pipeline:

```python
# scripts/debug_pipeline.py
import asyncio
import sys

async def debug(message: str):
    from radd.pipeline.normalizer import normalize, is_arabic
    from radd.pipeline.dialect import detect_dialect
    from radd.pipeline.intent import classify_intent
    from radd.pipeline.guardrails import apply_guardrails

    print(f"\n{'='*60}")
    print(f"Input:      {message}")
    
    # Step 1: Arabic detection
    arabic = is_arabic(message)
    print(f"Is Arabic:  {arabic}")
    if not arabic:
        print("❌ Not Arabic — will return default response")
        return
    
    # Step 2: Normalization
    normalized = normalize(message)
    print(f"Normalized: {normalized}")
    
    # Step 3: Dialect
    dialect = detect_dialect(normalized)
    print(f"Dialect:    {dialect.dialect} (confidence: {dialect.confidence:.2f})")
    print(f"Markers:    {dialect.markers}")
    
    # Step 4: Intent
    intent = classify_intent(normalized)
    print(f"Intent:     {intent.intent} (confidence: {intent.confidence:.2f})")
    print(f"Keywords:   {intent.matched_keywords}")
    print(f"All scores: {intent.all_scores}")
    
    # Step 5: Routing decision
    from radd.config import settings
    if intent.confidence >= settings.confidence_auto_threshold:
        print(f"Route:      ✅ TEMPLATE PATH (confidence {intent.confidence:.2f} ≥ {settings.confidence_auto_threshold})")
    else:
        print(f"Route:      → RAG PATH (confidence {intent.confidence:.2f} < {settings.confidence_auto_threshold})")
    print('='*60)

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "أين طلبي؟"
    asyncio.run(debug(msg))
```

Usage:
```bash
cd apps/api
uv run python scripts/debug_pipeline.py "أين طلبي رقم 1234؟"
uv run python scripts/debug_pipeline.py "ما هي ساعات العمل؟"
uv run python scripts/debug_pipeline.py "ابغى ارجع المنتج"
```

---

## Debugging Specific Issues

### Issue: Intent always returns "other"
**Diagnosis:**
```bash
uv run python scripts/debug_pipeline.py "YOUR_MESSAGE"
# Look at "All scores" — which intent has highest score?
```
**Fix:** Add more keywords to `radd/pipeline/intent.py` for that intent.

---

### Issue: Confidence always below 0.85 (always goes to RAG)
**Diagnosis:**
```bash
# Check if KB has indexed documents
psql $DATABASE_URL -c "
SELECT COUNT(*) as total_chunks, 
       COUNT(embedding_id) as indexed_chunks
FROM kb_chunks WHERE workspace_id = 'YOUR_WS_ID';"
```
**Likely causes:**
1. No KB documents approved → add and approve documents
2. Qdrant empty → restart `kb_indexer` worker
3. Retrieval returning empty → check Qdrant: `curl http://localhost:6333/collections`

---

### Issue: AI response not in correct dialect
**Diagnosis:**
```bash
uv run python scripts/debug_pipeline.py "وش الأحوال"
# Check "Dialect" line — should show "gulf"
```
**Fix:** Add more Gulf dialect markers to `radd/pipeline/dialect.py`:
```python
GULF_MARKERS = [
    "وش", "كيفك", "زين", ...  # add more here
]
```

---

### Issue: RAG response is hallucinated (not grounded)
**Check verifier output:**
```python
# Quick test
from radd.pipeline.verifier import verify_response_fast

response = "الشحن يستغرق 3-5 أيام عمل"
passages = ["نوصل خلال 5-7 أيام عمل في الرياض"]

score, grounded = verify_response_fast(response, passages)
print(f"C_verify: {score:.3f}, Grounded: {grounded}")
# If score < 0.60 → pipeline will escalate (correct behavior)
# If score > 0.85 but response is wrong → check passages quality
```

---

### Issue: Worker not processing messages
```bash
# Check Redis stream has messages
redis-cli XLEN messages:YOUR_WORKSPACE_ID

# Check consumer group
redis-cli XINFO GROUPS messages:YOUR_WORKSPACE_ID

# Check pending messages
redis-cli XPENDING messages:YOUR_WORKSPACE_ID radd-workers - + 10

# Manually ack stuck message
redis-cli XACK messages:YOUR_WORKSPACE_ID radd-workers MESSAGE_ID
```

---

### Issue: WhatsApp webhook HMAC fails
```python
# Verify HMAC manually
import hmac, hashlib

app_secret = "YOUR_META_APP_SECRET"
payload = b'{"object":"whatsapp_business_account",...}'
expected = "sha256=" + hmac.new(
    app_secret.encode(), payload, hashlib.sha256
).hexdigest()
print(expected)
# Compare with X-Hub-Signature-256 header value
```

---

## Confidence Score Benchmarks

| Scenario | Expected C_min | Expected Route |
|----------|----------------|----------------|
| Clear greeting | 0.90+ | auto_template |
| Order status with number | 0.95+ | action (Salla) |
| Question in KB | 0.75-0.90 | auto_rag |
| Vague question, partial KB match | 0.60-0.75 | escalated_soft |
| Unknown topic, no KB | 0.20-0.50 | escalated_hard |

---

## Log Monitoring

```bash
# API logs (structured JSON)
cd apps/api && uv run uvicorn radd.main:app --reload 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        log = json.loads(line)
        event = log.get('event', line.strip())
        print(f\"[{log.get('level','?').upper()}] {event}\")
    except:
        print(line.strip())
"

# Worker logs
cd apps/api && uv run python -m workers.message_worker 2>&1 | grep -E "pipeline\.|worker\."
```
