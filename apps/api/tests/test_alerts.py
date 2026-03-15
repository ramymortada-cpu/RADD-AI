"""اختبارات AlertManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from radd.alerts import AlertLevel, AlertManager


class TestAlertManager:

    def setup_method(self):
        self.manager = AlertManager(
            slack_webhook_url="https://hooks.slack.com/test",
            app_env="test",
        )

    # ── Cooldown ──────────────────────────────────────────

    def test_cooldown_prevents_duplicate_alerts(self):
        """نفس التنبيه لا يُرسل مرتين خلال فترة الـ cooldown."""
        assert self.manager._should_send("worker_crash", AlertLevel.CRITICAL) is True
        assert self.manager._should_send("worker_crash", AlertLevel.CRITICAL) is False

    def test_different_events_not_blocked_by_cooldown(self):
        """أحداث مختلفة لا يحجب أحدها الآخر."""
        assert self.manager._should_send("event_a", AlertLevel.CRITICAL) is True
        assert self.manager._should_send("event_b", AlertLevel.CRITICAL) is True

    # ── Slack ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_slack_not_sent_for_info_level(self):
        """مستوى INFO لا يرسل إلى Slack."""
        with patch.object(self.manager, "_send_slack") as mock_slack:
            await self.manager.info("test_event", "test message")
            mock_slack.assert_not_called()

    @pytest.mark.asyncio
    async def test_slack_sent_for_critical(self):
        """مستوى CRITICAL يرسل إلى Slack."""
        with patch.object(self.manager, "_send_slack", new_callable=AsyncMock) as mock_slack:
            await self.manager.critical("test_critical", "something broke")
            mock_slack.assert_called_once()

    @pytest.mark.asyncio
    async def test_slack_not_sent_when_no_webhook_url(self):
        """بدون Slack URL لا يرسل (بدون error)."""
        manager = AlertManager(slack_webhook_url="", app_env="test")
        await manager.critical("test_event", "test message")

    @pytest.mark.asyncio
    async def test_slack_failure_does_not_crash_app(self):
        """فشل Slack لا يكسر التطبيق."""
        mock_http = MagicMock()
        mock_http.post = AsyncMock(side_effect=ConnectionError("Slack unreachable"))
        with patch.object(self.manager, "_get_client", return_value=mock_http):
            await self.manager._send_slack(
                AlertLevel.CRITICAL, "test_event", "test message", {}
            )

    # ── All levels ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_crash_on_all_levels(self):
        """جميع المستويات تعمل بدون exception."""
        manager = AlertManager(slack_webhook_url="", app_env="test")
        await manager.info("e", "m")
        await manager.warning("e", "m")
        await manager.critical("e", "m")
        await manager.fatal("e", "m")
