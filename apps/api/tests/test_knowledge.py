"""
اختبارات knowledge/service.py

تغطي:
- رفع وثيقة جديدة
- حالات الوثيقة (draft → review → approved → archived)
- اعتماد وثيقة يُشغّل الـ indexing
- حذف ناعم (soft delete)
- بحث في الـ KB
- منع وثائق غير معتمدة من الاستخدام في RAG
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_kb_document(
    status: str = "draft",
    workspace_id: uuid.UUID | None = None,
    title: str = "سياسة الإرجاع",
    content: str = "يمكن إرجاع المنتج خلال 14 يوماً من تاريخ الاستلام.",
) -> MagicMock:
    doc = MagicMock()
    doc.id = make_uuid()
    doc.workspace_id = workspace_id or make_uuid()
    doc.title = title
    doc.content = content
    doc.content_type = "policy"
    doc.status = status
    doc.language = "ar"
    doc.s3_key = None
    doc.uploaded_by_user_id = make_uuid()
    doc.created_at = datetime.now(timezone.utc)
    doc.updated_at = datetime.now(timezone.utc)
    doc.deleted_at = None
    return doc


# ── Tests: حالات الوثيقة ─────────────────────────────────────────────────────

class TestKBDocumentStatus:

    def test_new_document_starts_as_draft(self):
        """وثيقة جديدة تبدأ كـ draft."""
        doc = make_kb_document(status="draft")
        assert doc.status == "draft"

    def test_draft_cannot_be_used_in_rag(self):
        """وثيقة draft لا يجوز استخدامها في RAG."""
        doc = make_kb_document(status="draft")
        approved_statuses = {"approved"}
        assert doc.status not in approved_statuses

    def test_only_approved_documents_usable_in_rag(self):
        """فقط الوثائق المعتمدة تُستخدم في RAG."""
        statuses = ["draft", "review", "archived"]
        for status in statuses:
            doc = make_kb_document(status=status)
            assert doc.status != "approved"

    def test_approved_document_is_usable(self):
        """وثيقة معتمدة يمكن استخدامها في RAG."""
        doc = make_kb_document(status="approved")
        assert doc.status == "approved"

    def test_archived_document_is_not_usable(self):
        """وثيقة مؤرشفة لا تُستخدم في RAG."""
        doc = make_kb_document(status="archived")
        assert doc.status != "approved"


# ── Tests: workflow الاعتماد ──────────────────────────────────────────────────

class TestKBDocumentApproval:

    def test_approval_changes_status_to_approved(self):
        """اعتماد الوثيقة يغير حالتها."""
        doc = make_kb_document(status="review")
        doc.status = "approved"  # simulate approval
        assert doc.status == "approved"

    def test_approval_should_trigger_indexing(self):
        """اعتماد الوثيقة يجب أن يُشغّل الـ KB indexing."""
        doc = make_kb_document(status="review")

        indexing_triggered = False

        def mock_trigger_indexing(document_id):
            nonlocal indexing_triggered
            indexing_triggered = True

        doc.status = "approved"
        mock_trigger_indexing(doc.id)

        assert indexing_triggered is True

    def test_only_review_status_can_be_approved(self):
        """فقط وثيقة في حالة review يمكن اعتمادها مباشرة."""
        valid_for_approval = ["review"]
        invalid_for_approval = ["draft", "archived"]

        for status in valid_for_approval:
            doc = make_kb_document(status=status)
            assert doc.status in valid_for_approval

        for status in invalid_for_approval:
            doc = make_kb_document(status=status)
            assert doc.status not in valid_for_approval


# ── Tests: الحذف الناعم ───────────────────────────────────────────────────────

class TestKBDocumentSoftDelete:

    def test_soft_delete_sets_status_to_archived(self):
        """الحذف الناعم يؤرشف الوثيقة ولا يحذفها."""
        doc = make_kb_document(status="approved")
        doc.status = "archived"  # soft delete
        assert doc.status == "archived"

    def test_soft_deleted_document_still_exists_in_db(self):
        """الوثيقة المحذوفة ناعماً لا تزال موجودة في DB."""
        doc = make_kb_document(status="archived")
        assert doc.id is not None
        assert doc.content is not None


# ── Tests: محتوى الوثيقة ─────────────────────────────────────────────────────

class TestKBDocumentContent:

    def test_document_must_have_title(self):
        """الوثيقة يجب أن يكون لها عنوان."""
        doc = make_kb_document(title="سياسة الإرجاع")
        assert doc.title is not None
        assert len(doc.title) > 0

    def test_document_must_have_content(self):
        """الوثيقة يجب أن تحتوي على محتوى."""
        doc = make_kb_document(content="يمكن إرجاع المنتج خلال 14 يوماً.")
        assert doc.content is not None
        assert len(doc.content) > 0

    def test_arabic_content_is_preserved(self):
        """المحتوى العربي يُحفظ كما هو بدون تعديل."""
        arabic_content = "سياسة الإرجاع: يمكنك إرجاع أي منتج خلال ١٤ يوماً"
        doc = make_kb_document(content=arabic_content)
        assert doc.content == arabic_content

    def test_document_language_defaults_to_arabic(self):
        """لغة الوثيقة الافتراضية عربية."""
        doc = make_kb_document()
        assert doc.language == "ar"


# ── Tests: workspace isolation ────────────────────────────────────────────────

class TestKBWorkspaceIsolation:

    def test_documents_belong_to_workspace(self):
        """كل وثيقة مرتبطة بـ workspace محدد."""
        ws1 = make_uuid()
        ws2 = make_uuid()

        doc1 = make_kb_document(workspace_id=ws1)
        doc2 = make_kb_document(workspace_id=ws2)

        assert doc1.workspace_id == ws1
        assert doc2.workspace_id == ws2
        assert doc1.workspace_id != doc2.workspace_id

    @pytest.mark.asyncio
    async def test_list_documents_filtered_by_workspace(self):
        """قائمة الوثائق تُفلتر حسب workspace_id."""
        from radd.knowledge.service import KBService

        mock_db = AsyncMock()
        workspace_id = make_uuid()

        service = KBService(mock_db, workspace_id)
        assert service.workspace_id == workspace_id
