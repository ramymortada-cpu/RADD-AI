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

    def test_other(self):
        r = classify_intent("تواصل مع المدير بخصوص شكوى")
        assert r.intent == "other"
        assert r.confidence <= 0.5
