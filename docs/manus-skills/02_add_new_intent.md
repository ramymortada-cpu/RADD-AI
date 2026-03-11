# Skill: Add New Arabic Intent to NLP Pipeline

## When to Use
When you need the AI to recognize a new type of customer question (e.g., "payment methods", "product availability", "loyalty points").

## Files to Modify
1. `apps/api/radd/pipeline/intent.py` — add keyword lists
2. `apps/api/radd/pipeline/templates.py` — add response templates (3 dialects)
3. `apps/api/scripts/benchmark.py` — add test cases

## Step-by-Step

### Step 1: Add keywords in intent.py

Open `apps/api/radd/pipeline/intent.py` and add to the `INTENT_KEYWORDS` dict:

```python
"payment_methods": [
    # MSA
    "طرق الدفع", "وسائل الدفع", "طريقة الدفع", "الدفع",
    # Gulf
    "كيف أدفع", "طرق الدفع عندكم", "تقبلون",
    # Egyptian  
    "بيع بالتقسيط", "بيدفع ازاي", "طرق الدفع ايه",
    # Universal
    "كاش", "بطاقة", "مدى", "فيزا", "أبل باي",
],
```

### Step 2: Add templates in templates.py

Open `apps/api/radd/pipeline/templates.py` and add to `TEMPLATES` dict:

```python
"payment_methods": {
    "gulf": "نقبل طرق الدفع التالية: مدى، فيزا، ماستركارد، أبل باي، والدفع عند الاستلام. {store_name} يدعم جميع طرق الدفع الآمنة.",
    "egyptian": "بنقبل: فيزا، ماستركارد، فودافون كاش، والدفع عند الاستلام في {store_name}.",
    "msa": "نقبل وسائل الدفع الآتية: البطاقات الائتمانية، مدى، المحافظ الرقمية، والدفع نقداً عند الاستلام.",
},
```

### Step 3: Add to is_template_intent function

In `templates.py`, find `is_template_intent()` and add the new intent:
```python
TEMPLATE_INTENTS = {
    "greeting", "return_policy", "store_hours", "payment_methods"  # add here
}
```

### Step 4: Add benchmark test cases

Open `apps/api/scripts/benchmark.py` and add to the test queries list:
```python
# payment_methods — add 5-10 test cases
{"query": "كيف أدفع الطلب؟", "expected": "payment_methods"},
{"query": "تقبلون مدى؟", "expected": "payment_methods"},
{"query": "هل فيه دفع عند الاستلام؟", "expected": "payment_methods"},
```

### Step 5: Run benchmark to verify
```bash
cd apps/api
uv run python scripts/benchmark.py
```
Must still show ≥ 80% accuracy (preferably ≥ 90%).

### Step 6: Run tests
```bash
uv run pytest tests/test_arabic.py -v
```

## Validation Checklist
- [ ] New intent appears in `INTENT_KEYWORDS` dict
- [ ] 3 dialect templates added (gulf, egyptian, msa)
- [ ] Intent added to `TEMPLATE_INTENTS` set
- [ ] Benchmark still ≥ 80%
- [ ] All existing tests pass
