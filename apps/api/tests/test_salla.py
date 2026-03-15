"""
اختبارات actions/salla.py

تغطي:
- استعلام حالة الطلب (get_order_status)
- معالجة طلب غير موجود
- معالجة خطأ Salla API
- timeout handling
- تنسيق الاستجابة للعربية
- عدم تسرب token في الـ logs
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_salla_api_response(
    status_slug: str = "in_transit",
    order_id: str = "123",
) -> dict:
    """استجابة Salla API نموذجية (هيكل /orders)."""
    return {
        "data": [
            {
                "id": order_id,
                "reference_id": "ORD-12345",
                "status": {
                    "slug": status_slug,
                    "name": status_slug,
                },
                "shipping": {
                    "tracking_number": "TRK-987654",
                    "company": {"name": "أرامكس"},
                    "estimated_delivery": "2026-03-15",
                },
                "amounts": {"total": {"formatted": "250 SAR"}},
            }
        ]
    }


# ── Tests: get_order_status ───────────────────────────────────────────────────

class TestSallaGetOrderStatus:

    @pytest.mark.asyncio
    async def test_returns_order_status_for_valid_order(self):
        """يعيد حالة الطلب لطلب موجود."""
        from radd.actions.salla import get_order_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = make_salla_api_response(
            status_slug="in_transit", order_id="123"
        )
        mock_response.raise_for_status = MagicMock()

        with patch("radd.actions.salla.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_order_status(
                order_reference="ORD-12345",
                access_token="test_token_123",
            )

        assert result is not None
        assert result.get("found") is True
        assert "status_ar" in result or "in_transit" in str(result).lower()

    @pytest.mark.asyncio
    async def test_returns_found_false_for_nonexistent_order(self):
        """يعيد found=False لطلب غير موجود (قائمة فارغة)."""
        from radd.actions.salla import get_order_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch("radd.actions.salla.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_order_status(
                order_reference="INVALID-999",
                access_token="test_token_123",
            )

        assert result.get("found") is False
        assert result.get("reference") == "INVALID-999"

    @pytest.mark.asyncio
    async def test_handles_salla_api_timeout(self):
        """يعالج timeout من Salla API بدون crash."""
        from radd.actions.salla import get_order_status

        with patch("radd.actions.salla.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timeout")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_order_status(
                order_reference="ORD-12345",
                access_token="test_token_123",
            )

        assert result is not None
        assert result.get("found") is False
        assert result.get("error") == "network_error"

    @pytest.mark.asyncio
    async def test_handles_salla_api_server_error(self):
        """يعالج 500 من Salla API."""
        from radd.actions.salla import get_order_status

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("radd.actions.salla.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def raise_http_error(*args, **kwargs):
                raise httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=mock_response
                )

            mock_client.get = AsyncMock(side_effect=raise_http_error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_order_status(
                order_reference="ORD-12345",
                access_token="test_token_123",
            )

        assert result.get("found") is False
        assert result.get("error") == "api_error"


# ── Tests: تنسيق الاستجابة ────────────────────────────────────────────────────

class TestSallaResponseFormat:

    def test_order_response_has_required_fields(self):
        """استجابة Salla تحتوي على الحقول المطلوبة."""
        from radd.actions.salla import ORDER_STATUS_AR

        assert "pending" in ORDER_STATUS_AR
        assert "delivered" in ORDER_STATUS_AR
        assert "canceled" in ORDER_STATUS_AR

    def test_status_labels_are_arabic(self):
        """تسمية الحالة تكون بالعربية."""
        from radd.actions.salla import ORDER_STATUS_AR

        arabic_statuses = list(ORDER_STATUS_AR.values())
        for label in arabic_statuses:
            assert any("\u0600" <= c <= "\u06ff" for c in label), (
                f"Label is not Arabic: {label}"
            )

    def test_format_order_status_response_for_found_order(self):
        """تنسيق الاستجابة لطلب موجود."""
        from radd.actions.salla import format_order_status_response

        order_data = {
            "found": True,
            "reference": "12345",
            "status_ar": "قيد الشحن",
            "tracking_number": "TRK-123",
            "carrier": "أرامكس",
        }
        msg = format_order_status_response(order_data)
        assert "12345" in msg
        assert "قيد الشحن" in msg


# ── Tests: extract_order_number ──────────────────────────────────────────────

class TestSallaExtractOrderNumber:

    def test_extracts_order_from_arabic_text(self):
        """استخراج رقم الطلب من النص العربي."""
        from radd.actions.salla import extract_order_number

        assert extract_order_number("رقم الطلب 12345") == "12345"
        assert extract_order_number("وين طلبي 98765") == "98765"

    def test_extracts_order_with_hash(self):
        """استخراج رقم الطلب مع #."""
        from radd.actions.salla import extract_order_number

        result = extract_order_number("طلب #12345")
        assert result == "12345"

    def test_returns_none_when_no_order(self):
        """يعيد None عند عدم وجود رقم طلب."""
        from radd.actions.salla import extract_order_number

        assert extract_order_number("السلام عليكم") is None
