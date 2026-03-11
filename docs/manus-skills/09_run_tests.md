# Skill: Run Tests and Add New Tests

## When to Use
Before committing any change, to verify nothing is broken.

## Run All Tests

```bash
cd apps/api

# Run all tests
uv run pytest tests/ -v

# Run with coverage report
uv run pytest tests/ --cov=radd --cov-report=term-missing

# Run NLP benchmark (must stay ≥ 80%)
uv run python scripts/benchmark.py
```

## Run Specific Tests

```bash
# Test Arabic NLP components
uv run pytest tests/test_arabic.py -v

# Test PII guardrails
uv run pytest tests/test_guardrails.py -v

# Test pipeline routing
uv run pytest tests/test_pipeline.py -v

# Run single test by name
uv run pytest tests/test_arabic.py::TestNormalizer::test_removes_tashkeel -v
```

---

## Adding a New Test

### Test Arabic NLP (test_arabic.py style)

```python
# tests/test_arabic.py — ADD to appropriate class:

class TestIntentClassifier:
    def test_classifies_payment_intent(self):
        """New intent: payment methods"""
        result = classify_intent("كيف أدفع الطلب؟")
        assert result.intent == "payment_methods"
        assert result.confidence >= 0.70
    
    def test_payment_intent_gulf_dialect(self):
        result = classify_intent("تقبلون مدى؟")
        assert result.intent == "payment_methods"
```

### Test API endpoint

```python
# tests/test_api_conversations.py — NEW FILE:
import pytest
from httpx import AsyncClient
from radd.main import app

@pytest.mark.asyncio
async def test_list_conversations_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/conversations")
    assert response.status_code == 401

@pytest.mark.asyncio  
async def test_list_conversations_with_token(auth_headers):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/conversations",
            headers=auth_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
```

### Test PII Redaction (test_guardrails.py style)

```python
# tests/test_guardrails.py — ADD:

class TestPIIRedaction:
    def test_redacts_iban(self):
        text = "رقم الآيبان SA1234567890123456789012"
        redacted, types, count = redact_pii(text)
        assert "[IBAN]" in redacted
        assert "iban" in types
    
    def test_multiple_pii_in_one_message(self):
        text = "رقمي 0551234567 وإيميلي test@example.com"
        redacted, types, count = redact_pii(text)
        assert count == 2
        assert "[PHONE]" in redacted
        assert "[EMAIL]" in redacted
```

---

## Test Fixtures (conftest.py)

```python
# tests/conftest.py — already exists, add fixtures here:
import pytest
import uuid

@pytest.fixture
def workspace_id():
    return uuid.UUID("00000000-0000-0000-0000-000000000001")

@pytest.fixture
def sample_arabic_messages():
    return [
        "أين طلبي؟",
        "أبغى أرجع المنتج",
        "وش ساعات العمل؟",
    ]
```

---

## Benchmark Test Format

```python
# scripts/benchmark.py — ADD test cases for new intents:

BENCHMARK_QUERIES = [
    # ... existing queries ...
    
    # payment_methods — add 5+ cases
    {"query": "كيف أدفع الطلب؟", "expected": "payment_methods"},
    {"query": "تقبلون فيزا؟", "expected": "payment_methods"},
    {"query": "هل في دفع عند الاستلام؟", "expected": "payment_methods"},
    {"query": "أقدر أدفع بمدى؟", "expected": "payment_methods"},
    {"query": "طرق الدفع المتاحة", "expected": "payment_methods"},
]
```

---

## CI Test Requirements

The CI pipeline (`.github/workflows/ci.yml`) runs:
1. `uv run ruff check radd/ workers/ scripts/` — linting
2. `uv run mypy radd/ --ignore-missing-imports` — type checking
3. `uv run pytest tests/ -v --tb=short` — all tests

**All must pass before merge to main.**
