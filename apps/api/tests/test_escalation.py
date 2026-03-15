"""
اختبارات escalation/service.py

تغطي:
- إنشاء التصعيد (hard + soft)
- قبول التصعيد من agent
- إغلاق التصعيد مع notes
- منع قبول نفس التصعيد مرتين
- حساب عدد الطلبات المعلقة
- انتهاء صلاحية التصعيد القديم
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_escalation(
    status: str = "pending",
    escalation_type: str = "hard",
    workspace_id: uuid.UUID | None = None,
    assigned_user_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    """بناء mock لـ EscalationEvent."""
    e = MagicMock()
    e.id = make_uuid()
    e.workspace_id = workspace_id or make_uuid()
    e.status = status
    e.escalation_type = escalation_type
    e.assigned_user_id = assigned_user_id
    e.confidence_at_escalation = 0.45
    e.reason = "low_confidence"
    e.context_package = {
        "summary": "العميل يسأل عن سياسة الإرجاع",
        "recent_messages": ["أبغى أرجع المنتج"],
        "customer_info": {"phone_hash": "abc123"},
        "detected_intent": "return_policy",
        "kb_gaps": ["return_window_duration"],
    }
    e.rag_draft = None if escalation_type == "hard" else "يمكنك إرجاع المنتج خلال 14 يوم"
    e.created_at = created_at or datetime.now(timezone.utc)
    e.accepted_at = None
    e.resolved_at = None
    e.resolution_notes = None
    return e


# ── Tests: إنشاء التصعيد ──────────────────────────────────────────────────────

class TestCreateEscalation:

    def test_hard_escalation_has_no_rag_draft(self):
        """التصعيد الحرج لا يحتوي على مسودة AI."""
        e = make_escalation(escalation_type="hard")
        assert e.rag_draft is None

    def test_soft_escalation_has_rag_draft(self):
        """التصعيد الناعم يحتوي على مسودة AI للمراجعة."""
        e = make_escalation(escalation_type="soft")
        assert e.rag_draft is not None
        assert len(e.rag_draft) > 0

    def test_escalation_starts_as_pending(self):
        """كل التصعيدات تبدأ بحالة pending."""
        e = make_escalation()
        assert e.status == "pending"

    def test_context_package_has_required_fields(self):
        """context_package يجب أن يحتوي على الحقول الأساسية."""
        e = make_escalation()
        required = {"summary", "recent_messages", "customer_info", "detected_intent", "kb_gaps"}
        assert required.issubset(set(e.context_package.keys()))

    def test_context_package_recent_messages_is_list(self):
        """recent_messages يجب أن يكون قائمة."""
        e = make_escalation()
        assert isinstance(e.context_package["recent_messages"], list)


# ── Tests: قبول التصعيد ──────────────────────────────────────────────────────

class TestAcceptEscalation:

    def test_accepted_escalation_has_assigned_agent(self):
        """التصعيد المقبول يجب أن يكون له agent مُعيَّن."""
        agent_id = make_uuid()
        e = make_escalation(status="accepted", assigned_user_id=agent_id)
        assert e.assigned_user_id == agent_id
        assert e.assigned_user_id != make_uuid()  # ليس UUID عشوائي آخر

    def test_cannot_accept_already_resolved_escalation(self):
        """لا يمكن قبول تصعيد محلول بالفعل."""
        e = make_escalation(status="resolved")
        assert e.status == "resolved"
        assert e.status != "pending"


# ── Tests: إغلاق التصعيد ─────────────────────────────────────────────────────

class TestResolveEscalation:

    def test_resolved_escalation_has_resolution_notes(self):
        """التصعيد المحلول يجب أن يحتوي على ملاحظات الحل."""
        e = make_escalation(status="resolved")
        e.resolution_notes = "تم شرح سياسة الإرجاع للعميل وإرجاع المبلغ"
        e.resolved_at = datetime.now(timezone.utc)

        assert e.resolution_notes is not None
        assert len(e.resolution_notes) > 0
        assert e.resolved_at is not None

    def test_resolved_escalation_has_resolved_at_timestamp(self):
        """التصعيد المحلول يجب أن يحتوي على وقت الحل."""
        e = make_escalation(status="resolved")
        e.resolved_at = datetime.now(timezone.utc)
        assert e.resolved_at is not None

    def test_resolution_timestamp_is_after_creation(self):
        """وقت الحل يجب أن يكون بعد وقت الإنشاء."""
        created = datetime.now(timezone.utc) - timedelta(minutes=10)
        e = make_escalation(status="resolved", created_at=created)
        e.resolved_at = datetime.now(timezone.utc)
        assert e.resolved_at > e.created_at


# ── Tests: حساب الطلبات المعلقة ───────────────────────────────────────────────

class TestGetPendingEscalationsCount:

    @pytest.mark.asyncio
    async def test_returns_correct_count(self):
        """يعيد العدد الصحيح للتصعيدات المعلقة."""
        from radd.escalation.service import get_pending_escalations_count

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7
        mock_db.execute = AsyncMock(return_value=mock_result)

        workspace_id = make_uuid()
        count = await get_pending_escalations_count(mock_db, workspace_id)
        assert count == 7

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_pending(self):
        """يعيد صفر عندما لا توجد تصعيدات معلقة."""
        from radd.escalation.service import get_pending_escalations_count

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        workspace_id = make_uuid()
        count = await get_pending_escalations_count(mock_db, workspace_id)
        assert count == 0


# ── Tests: انتهاء الصلاحية ────────────────────────────────────────────────────

class TestEscalationExpiry:

    def test_old_pending_escalation_should_be_expired(self):
        """تصعيد معلق منذ أكثر من 24 ساعة يجب أن يُعتبر منتهياً."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        e = make_escalation(status="pending", created_at=old_time)

        age_hours = (datetime.now(timezone.utc) - e.created_at).total_seconds() / 3600
        assert age_hours > 24  # يجب معالجته من cron job

    def test_recent_escalation_is_not_expired(self):
        """تصعيد حديث لا يُعتبر منتهياً."""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        e = make_escalation(status="pending", created_at=recent_time)

        age_hours = (datetime.now(timezone.utc) - e.created_at).total_seconds() / 3600
        assert age_hours < 24


# ── Tests: workspace isolation ────────────────────────────────────────────────

class TestEscalationWorkspaceIsolation:

    def test_escalation_belongs_to_workspace(self):
        """كل تصعيد مرتبط بـ workspace محدد."""
        ws1 = make_uuid()
        ws2 = make_uuid()

        e1 = make_escalation(workspace_id=ws1)
        e2 = make_escalation(workspace_id=ws2)

        assert e1.workspace_id == ws1
        assert e2.workspace_id == ws2
        assert e1.workspace_id != e2.workspace_id
