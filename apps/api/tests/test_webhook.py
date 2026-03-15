"""
Tests for the WhatsApp webhook handler.

Coverage:
  1. Verification challenge (valid + invalid token)
  2. POST with valid HMAC-SHA256 signature
  3. POST with invalid / missing HMAC signature
  4. Deduplication — second identical message_id returns 200 but skips enqueue
  5. Non-text message type (image, sticker, …) — ignored gracefully
  6. Malformed JSON body
"""
import hashlib
import hmac
import json
import sys
import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── ensure the api package is importable without installation ─────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
APP_SECRET = "test_app_secret_12345"
VERIFY_TOKEN = "radd_test_verify"
PHONE_NUMBER_ID = "12345678"


def _make_mock_redis():
    """Redis mock for webhook tests — no real Redis connection."""
    r = AsyncMock()
    # set(key, val, nx=True, ex=...) — returns True when key is new (dedup)
    r.set = AsyncMock(return_value=True)
    r.xadd = AsyncMock(return_value=b"1-1")
    r.get = AsyncMock(return_value=None)
    r.exists = AsyncMock(return_value=0)
    r.delete = AsyncMock(return_value=1)
    return r


def _make_app(limiter_instance=None) -> FastAPI:
    """Build a minimal FastAPI app with the webhook router, mocked deps."""
    from radd.config import settings
    settings.meta_app_secret = APP_SECRET
    settings.meta_verify_token = VERIFY_TOKEN
    settings.wa_phone_number_id = PHONE_NUMBER_ID

    app = FastAPI()
    if limiter_instance is not None:
        app.state.limiter = limiter_instance

    from radd.webhooks.router import router
    app.include_router(router)
    return app


@pytest.fixture(scope="module")
def client():
    """Test client with Redis and DB mocked — no real connections."""
    mock_redis = _make_mock_redis()
    test_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

    with (
        patch("radd.limiter.limiter", test_limiter),
        patch("radd.webhooks.router.get_redis", return_value=mock_redis),
        patch("radd.webhooks.router.get_db_session") as mock_db_session,
    ):
        # Mock get_db_session as async context manager — _resolve_workspace uses it
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)

        app = _make_app(limiter_instance=test_limiter)
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _wa_payload(msg_id: str = "wamid.test001", msg_type: str = "text", text: str = "مرحبا") -> dict:
    msg: dict = {
        "id": msg_id,
        "from": "966501234567",
        "timestamp": "1710000000",
        "type": msg_type,
    }
    if msg_type == "text":
        msg["text"] = {"body": text}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "966501234567",
                                "phone_number_id": PHONE_NUMBER_ID,
                            },
                            "messages": [msg],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Verification challenge
# ─────────────────────────────────────────────────────────────────────────────
class TestVerificationChallenge:
    def test_valid_token_returns_challenge(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE_XYZ",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "CHALLENGE_XYZ"

    def test_invalid_token_returns_403(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "CHALLENGE_XYZ",
            },
        )
        assert resp.status_code == 403

    def test_missing_mode_returns_403(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE_XYZ",
            },
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 2 & 3. HMAC verification
# ─────────────────────────────────────────────────────────────────────────────
class TestHMACVerification:
    @patch("radd.webhooks.router._process_webhook_payload", new_callable=AsyncMock)
    def test_valid_hmac_returns_200(self, mock_process, client):
        body = json.dumps(_wa_payload()).encode()
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_invalid_hmac_returns_401(self, client):
        body = json.dumps(_wa_payload()).encode()
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=deadbeef",
            },
        )
        assert resp.status_code == 401

    def test_missing_hmac_returns_401(self, client):
        body = json.dumps(_wa_payload()).encode()
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 4. Deduplication
# ─────────────────────────────────────────────────────────────────────────────
class TestDeduplication:
    @patch("radd.webhooks.router.get_redis")
    @patch("radd.webhooks.router._process_webhook_payload", new_callable=AsyncMock)
    def test_duplicate_message_is_skipped(self, mock_process, mock_get_redis, client):
        """Sending the same wamid twice: both return 200, but second should not enqueue."""
        fake_redis = AsyncMock()
        # First call: setnx returns True (new), second: False (duplicate)
        fake_redis.set = AsyncMock(side_effect=[True, False])
        mock_get_redis.return_value = fake_redis

        payload = _wa_payload(msg_id="wamid.DUPLICATE001")
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        }

        resp1 = client.post("/webhooks/whatsapp", content=body, headers=headers)
        resp2 = client.post("/webhooks/whatsapp", content=body, headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 5. Non-text message types (image, sticker, video…)
# ─────────────────────────────────────────────────────────────────────────────
class TestNonTextMessages:
    @pytest.mark.parametrize("msg_type", ["image", "sticker", "video", "audio", "document"])
    @patch("radd.webhooks.router._process_webhook_payload", new_callable=AsyncMock)
    def test_non_text_message_returns_200(self, mock_process, msg_type, client):
        body = json.dumps(_wa_payload(msg_type=msg_type)).encode()
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 6. Malformed JSON
# ─────────────────────────────────────────────────────────────────────────────
class TestMalformedPayload:
    def test_invalid_json_returns_400(self, client):
        body = b"not-valid-json{{"
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert resp.status_code == 400
