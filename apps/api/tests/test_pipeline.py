"""
Tests: chunker, orchestrator (sync template path), pipeline routing.
"""
import pytest

from radd.knowledge.chunker import chunk_document
from radd.pipeline.orchestrator import run_pipeline


class TestChunker:
    def test_basic_chunking(self):
        content = "سياسة الإرجاع\n\nيمكن إرجاع المنتجات خلال ١٤ يوماً من تاريخ الاستلام.\n\nشروط الإرجاع:\n- المنتج بحالته الأصلية\n- مع الفاتورة الأصلية\n- خلال مدة الضمان"
        chunks = chunk_document(content)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content
            assert chunk.content_normalized
            assert chunk.token_count > 0

    def test_chunk_indices_sequential(self):
        content = "\n\n".join([f"فقرة رقم {i} " + "محتوى " * 50 for i in range(5)])
        chunks = chunk_document(content)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_large_paragraph_split(self):
        long_para = "هذه جملة طويلة جداً. " * 100
        chunks = chunk_document(long_para)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.token_count <= 600  # Allow some buffer

    def test_empty_content(self):
        chunks = chunk_document("")
        assert chunks == []


class TestOrchestrator:
    def test_greeting_arabic(self):
        result = run_pipeline("مرحبا كيف حالكم")
        assert result.resolution_type == "auto_template"
        assert result.intent == "greeting"
        assert result.response_text

    def test_order_status_arabic(self):
        result = run_pipeline("وين طلبي رقم 12345")
        assert result.intent == "order_status"
        assert result.resolution_type == "auto_template"

    def test_shipping_arabic(self):
        result = run_pipeline("كم مدة الشحن والتوصيل")
        assert result.intent == "shipping"
        assert result.resolution_type == "auto_template"

    def test_return_policy_arabic(self):
        result = run_pipeline("ابغى ارجع المنتج كيف")
        assert result.intent == "return_policy"
        assert result.resolution_type == "auto_template"

    def test_store_hours_arabic(self):
        result = run_pipeline("متى تفتحون وساعات الدوام")
        assert result.intent == "store_hours"
        assert result.resolution_type == "auto_template"

    def test_unknown_escalates(self):
        result = run_pipeline("لدي شكوى حول موظف")
        assert result.resolution_type == "escalated_hard"
        assert "فريقنا" in result.response_text or "دعم" in result.response_text.lower()

    def test_non_arabic_handled(self):
        result = run_pipeline("Hello I need help")
        assert result.intent == "other"
        assert result.resolution_type == "auto_template"

    def test_confidence_breakdown_present(self):
        result = run_pipeline("مرحبا")
        assert "intent" in result.confidence_breakdown
        assert "retrieval" in result.confidence_breakdown
        assert "verify" in result.confidence_breakdown

    def test_gulf_dialect_detected(self):
        result = run_pipeline("وين طلبي ليش ما وصل")
        assert result.dialect == "gulf"

    def test_msa_default(self):
        result = run_pipeline("أريد الاستفسار عن حالة طلبي")
        assert result.dialect == "msa"
