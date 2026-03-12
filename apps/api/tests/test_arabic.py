"""
Tests: Arabic normalizer, dialect detector, intent classifier.
Manual checkpoint: Sprint 1 Day 6–8.
"""
import pytest

from radd.pipeline.normalizer import is_arabic, normalize
from radd.pipeline.dialect import detect_dialect
from radd.pipeline.intent import classify_intent


class TestNormalizer:
    def test_removes_tashkeel(self):
        assert normalize("مَرْحَباً") == "مرحبا"

    def test_normalizes_alef_hamza(self):
        assert normalize("أهلاً") == "اهلا"

    def test_normalizes_alef_madda(self):
        assert normalize("آخر") == "اخر"

    def test_normalizes_ya(self):
        assert normalize("مبنى") == "مبني"

    def test_removes_tatweel(self):
        # Tatweel is U+0640 (ـ kashida), not repeated letters
        assert normalize("جمـيـل") == "جميل"

    def test_normalizes_whitespace(self):
        assert normalize("كيف   حالك") == "كيف حالك"

    def test_strips_leading_trailing(self):
        assert normalize("  مرحبا  ") == "مرحبا"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_preserves_non_arabic(self):
        result = normalize("Hello مرحبا")
        assert "Hello" in result
        assert "مرحبا" in result


class TestArabicDetection:
    def test_detects_arabic(self):
        assert is_arabic("مرحبا كيف حالك") is True

    def test_rejects_english(self):
        assert is_arabic("Hello how are you") is False

    def test_mixed_mostly_arabic(self):
        assert is_arabic("مرحبا hello") is True


class TestDialectDetector:
    def test_detects_gulf(self):
        result = detect_dialect("وين طلبي ليش ما وصل")
        assert result.dialect == "gulf"
        assert result.confidence > 0.7

    def test_detects_egyptian(self):
        result = detect_dialect("إيه ده ليه مجاش")
        assert result.dialect == "egyptian"
        assert result.confidence > 0.7

    def test_defaults_to_msa(self):
        result = detect_dialect("أريد معرفة حالة طلبي")
        assert result.dialect == "msa"


class TestIntentClassifier:
    def test_greeting(self):
        r = classify_intent("مرحبا كيف حالكم")
        assert r.intent == "greeting"
        assert r.confidence >= 0.7

    def test_order_status(self):
        r = classify_intent("وين طلبي ما وصل")
        assert r.intent == "order_status"

    def test_shipping(self):
        r = classify_intent("كم مدة الشحن والتوصيل")
        assert r.intent == "shipping"

    def test_return_policy(self):
        r = classify_intent("ابغى ارجع المنتج")
        assert r.intent == "return_policy"

    def test_store_hours(self):
        r = classify_intent("متى تفتحون ساعات الدوام")
        assert r.intent == "store_hours"

    def test_unmatched_returns_general(self):
        r = classify_intent("تواصل مع المدير بخصوص شكوى")
        assert r.intent == "general"
        assert r.confidence <= 0.5

    # ── 3 new intents (Cursor Prompt 3) ──────────────────────────────────────

    def test_product_inquiry_price(self):
        r = classify_intent("كم سعر العطر الجديد؟")
        assert r.intent == "product_inquiry"
        assert r.confidence >= 0.7

    def test_product_inquiry_available(self):
        r = classify_intent("عندكم مقاس L متوفر؟")
        assert r.intent == "product_inquiry"
        assert r.confidence >= 0.7

    def test_product_inquiry_details(self):
        r = classify_intent("ايش مواصفات الساعة الذهبية؟")
        assert r.intent == "product_inquiry"
        assert r.confidence >= 0.6

    def test_product_comparison_which_better(self):
        r = classify_intent("ايهم أفضل العطر الأول ولا الثاني؟")
        assert r.intent == "product_comparison"
        assert r.confidence >= 0.7

    def test_product_comparison_difference(self):
        r = classify_intent("إيش الفرق بين المنتجين؟")
        assert r.intent == "product_comparison"
        assert r.confidence >= 0.7

    def test_purchase_hesitation_expensive(self):
        r = classify_intent("غالي شوي، فيه خصم؟")
        assert r.intent == "purchase_hesitation"
        assert r.confidence >= 0.7

    def test_purchase_hesitation_thinking(self):
        r = classify_intent("بفكر في الموضوع")
        assert r.intent == "purchase_hesitation"
        assert r.confidence >= 0.6

    def test_purchase_hesitation_installment(self):
        r = classify_intent("ممكن بالتقسيط تابي؟")
        assert r.intent == "purchase_hesitation"
        assert r.confidence >= 0.6

    def test_pre_purchase_flag(self):
        """All 3 new intents should be flagged as pre-purchase."""
        from radd.pipeline.intent import PRE_PURCHASE_INTENTS
        assert "product_inquiry" in PRE_PURCHASE_INTENTS
        assert "product_comparison" in PRE_PURCHASE_INTENTS
        assert "purchase_hesitation" in PRE_PURCHASE_INTENTS
