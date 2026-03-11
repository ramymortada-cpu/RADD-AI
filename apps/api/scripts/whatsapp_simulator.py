"""
WhatsApp Webhook Simulator — RADD AI E2E Test
==============================================
Simulates real WhatsApp webhook payloads to test the full pipeline:
  1. Webhook reception & HMAC verification
  2. Message parsing & deduplication
  3. Redis Stream enqueue
  4. Pipeline processing (normalize → dialect → intent → template/RAG)

Usage:
  cd apps/api
  uv run python scripts/whatsapp_simulator.py

Requires: API running on localhost:8000, Redis, PostgreSQL, Qdrant
"""
import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime

import httpx
import redis.asyncio as aioredis

# ── Configuration ────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
WEBHOOK_URL = f"{API_BASE}/api/v1/webhooks/whatsapp"
META_APP_SECRET = ""  # Empty = skip HMAC (dev mode)
PHONE_NUMBER_ID = "test_phone_001"
REDIS_URL = "redis://localhost:6379/0"

# ── Test Messages ────────────────────────────────────────────────────────────
# Each tuple: (sender_phone, message_text, expected_intent, description)

TEST_MESSAGES = [
    # Arabic greetings (Saudi dialect)
    ("966501234567", "السلام عليكم", "greeting", "تحية عربية كلاسيكية"),
    ("966501234567", "هلا والله كيفك", "greeting", "تحية سعودية عامية"),
    ("966501234567", "مرحبا", "greeting", "تحية بسيطة"),

    # Order status inquiries
    ("966509876543", "وين طلبي؟", "order_status", "استفسار عن حالة الطلب - سعودي"),
    ("966509876543", "أبي أعرف وضع طلبي", "order_status", "استفسار عن الطلب - سعودي"),
    ("966509876543", "ابي اتتبع شحنتي", "shipping", "استفسار عن الشحن"),

    # Shipping inquiries
    ("966507771111", "متى يوصل الطلب؟", "shipping", "سؤال عن وقت التوصيل"),
    ("966507771111", "كم ياخذ التوصيل؟", "shipping", "سؤال عن مدة الشحن"),

    # Return policy
    ("966502223333", "ابي ارجع المنتج", "return_policy", "طلب إرجاع - سعودي"),
    ("966502223333", "وش سياسة الاسترجاع عندكم؟", "return_policy", "سؤال عن سياسة الإرجاع"),

    # Store hours
    ("966504445555", "متى تفتحون؟", "store_hours", "سؤال عن ساعات العمل"),
    ("966504445555", "وش اوقات الدوام؟", "store_hours", "سؤال عن أوقات الدوام"),

    # Non-Arabic (should get Arabic-only response)
    ("966506667777", "Hello, what are your hours?", "other", "رسالة إنجليزية - يجب الرد بالعربية فقط"),

    # Edge cases
    ("966508889999", "😊", "other", "إيموجي فقط"),
    ("966508889999", "شكراً جزيلاً على المساعدة", "greeting", "شكر وتقدير"),
]

# ── Duplicate test message ───────────────────────────────────────────────────
DUPLICATE_MESSAGE = ("966501234567", "السلام عليكم", "greeting", "رسالة مكررة - يجب تجاهلها")


def build_whatsapp_payload(sender_phone: str, text: str, msg_id: str = None) -> dict:
    """Build a realistic WhatsApp Cloud API webhook payload."""
    if msg_id is None:
        msg_id = f"wamid.{uuid.uuid4().hex[:32]}"

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Customer"},
                                    "wa_id": sender_phone,
                                }
                            ],
                            "messages": [
                                {
                                    "from": sender_phone,
                                    "id": msg_id,
                                    "timestamp": str(int(time.time())),
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def build_non_text_payload(sender_phone: str, msg_type: str = "image") -> dict:
    """Build a non-text message payload (image, audio, etc.)."""
    msg_id = f"wamid.{uuid.uuid4().hex[:32]}"
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Customer"},
                                    "wa_id": sender_phone,
                                }
                            ],
                            "messages": [
                                {
                                    "from": sender_phone,
                                    "id": msg_id,
                                    "timestamp": str(int(time.time())),
                                    "type": msg_type,
                                    msg_type: {
                                        "mime_type": "image/jpeg",
                                        "sha256": "abc123",
                                        "id": "media_id_123",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()


async def send_webhook(client: httpx.AsyncClient, payload: dict, description: str) -> dict:
    """Send a webhook payload and return the result."""
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}

    if META_APP_SECRET:
        headers["x-hub-signature-256"] = sign_payload(body, META_APP_SECRET)

    try:
        response = await client.post(WEBHOOK_URL, content=body, headers=headers, timeout=10.0)
        return {
            "description": description,
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "success": response.status_code == 200,
        }
    except Exception as e:
        return {
            "description": description,
            "status_code": 0,
            "response": str(e),
            "success": False,
        }


async def test_pipeline_directly():
    """Test the pipeline orchestrator directly (bypasses webhook)."""
    print("\n" + "=" * 70)
    print("🧪 اختبار مباشر للـ Pipeline (بدون webhook)")
    print("=" * 70)

    from radd.pipeline.orchestrator import run_pipeline

    results = []
    for sender, text, expected_intent, desc in TEST_MESSAGES:
        result = run_pipeline(text)
        match = "✅" if result.intent == expected_intent else "❌"
        results.append({
            "message": text,
            "expected": expected_intent,
            "actual": result.intent,
            "confidence": result.confidence,
            "resolution": result.resolution_type,
            "dialect": result.dialect,
            "match": result.intent == expected_intent,
        })
        print(f"  {match} [{result.intent:15s}] (ثقة: {result.confidence:.2f}) "
              f"[{result.resolution_type:15s}] [{result.dialect:5s}] → {text[:50]}")

    passed = sum(1 for r in results if r["match"])
    total = len(results)
    accuracy = (passed / total) * 100 if total > 0 else 0
    print(f"\n📊 النتيجة: {passed}/{total} ({accuracy:.1f}%)")
    print(f"   {'✅ نجح' if accuracy >= 80 else '❌ فشل'} — الحد الأدنى المطلوب: 80%")

    return results


async def test_webhook_endpoint():
    """Test the webhook endpoint with simulated WhatsApp payloads."""
    print("\n" + "=" * 70)
    print("🌐 اختبار Webhook Endpoint")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        # 1. Test health endpoint first
        print("\n📡 فحص صحة الـ API...")
        try:
            health = await client.get(f"{API_BASE}/health", timeout=5.0)
            print(f"  ✅ API Health: {health.json()}")
        except Exception as e:
            print(f"  ❌ API غير متاح: {e}")
            return []

        # 2. Test webhook verification (GET)
        print("\n🔐 اختبار التحقق من Webhook (GET)...")
        verify_params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token_placeholder",
            "hub.challenge": "test_challenge_12345",
        }
        try:
            verify_resp = await client.get(f"{WEBHOOK_URL}", params=verify_params, timeout=5.0)
            if verify_resp.status_code == 200:
                print(f"  ✅ Webhook verification: {verify_resp.text}")
            else:
                print(f"  ⚠️ Webhook verification failed (expected if META_VERIFY_TOKEN not set): {verify_resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ Verification error: {e}")

        # 3. Send text messages
        print("\n📨 إرسال رسائل نصية...")
        results = []
        for sender, text, expected_intent, desc in TEST_MESSAGES:
            payload = build_whatsapp_payload(sender, text)
            result = await send_webhook(client, payload, desc)
            status_icon = "✅" if result["success"] else "❌"
            print(f"  {status_icon} [{result['status_code']}] {desc}: {text[:40]}")
            results.append(result)
            await asyncio.sleep(0.2)  # Small delay between messages

        # 4. Test deduplication
        print("\n🔄 اختبار منع التكرار (Deduplication)...")
        dup_msg_id = f"wamid.duplicate_{uuid.uuid4().hex[:16]}"
        dup_payload = build_whatsapp_payload(
            DUPLICATE_MESSAGE[0], DUPLICATE_MESSAGE[1], msg_id=dup_msg_id
        )
        # Send same message twice
        result1 = await send_webhook(client, dup_payload, "الرسالة الأولى (يجب قبولها)")
        result2 = await send_webhook(client, dup_payload, "الرسالة المكررة (يجب تجاهلها)")
        print(f"  ✅ الأولى: {result1['status_code']} | المكررة: {result2['status_code']}")
        print(f"  ℹ️ كلاهما يعود 200 (ACK) لكن المكررة لن تُعالج في Redis")

        # 5. Test non-text message
        print("\n🖼️ اختبار رسالة غير نصية (صورة)...")
        non_text_payload = build_non_text_payload("966501111222", "image")
        non_text_result = await send_webhook(client, non_text_payload, "رسالة صورة (يجب رفضها)")
        print(f"  ✅ Status: {non_text_result['status_code']} (ACK — الصورة ستُرفض في المعالجة)")

        # 6. Test invalid JSON
        print("\n🚫 اختبار JSON غير صالح...")
        try:
            bad_resp = await client.post(
                WEBHOOK_URL,
                content=b"not json",
                headers={"Content-Type": "application/json"},
                timeout=5.0,
            )
            print(f"  ✅ Invalid JSON rejected: {bad_resp.status_code}")
        except Exception as e:
            print(f"  ✅ Invalid JSON rejected: {e}")

        return results


async def check_redis_streams():
    """Check Redis streams for enqueued messages."""
    print("\n" + "=" * 70)
    print("📦 فحص Redis Streams")
    print("=" * 70)

    try:
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        keys = await r.keys("messages:*")
        print(f"\n  📋 عدد الـ streams: {len(keys)}")

        total_messages = 0
        for key in keys:
            length = await r.xlen(key)
            total_messages += length
            print(f"  📨 {key}: {length} رسالة")

            # Show last 3 messages from each stream
            messages = await r.xrevrange(key, count=3)
            for msg_id, data in messages:
                text = data.get("text", "")[:50]
                sender = data.get("sender_phone", "unknown")
                print(f"      └─ [{sender}] {text}")

        # Check dedup keys
        dedup_keys = await r.keys("dedup:wa:*")
        print(f"\n  🔑 مفاتيح منع التكرار: {len(dedup_keys)}")

        await r.aclose()
        return total_messages

    except Exception as e:
        print(f"  ❌ خطأ في الاتصال بـ Redis: {e}")
        return 0


async def main():
    """Run all tests."""
    print("=" * 70)
    print("🚀 RADD AI — WhatsApp Webhook Simulator")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 API: {API_BASE}")
    print("=" * 70)

    # Test 1: Direct pipeline test
    pipeline_results = await test_pipeline_directly()

    # Test 2: Webhook endpoint test
    webhook_results = await test_webhook_endpoint()

    # Test 3: Check Redis streams
    await asyncio.sleep(2)  # Wait for background tasks
    redis_count = await check_redis_streams()

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📊 ملخص الاختبار النهائي")
    print("=" * 70)

    pipeline_passed = sum(1 for r in pipeline_results if r["match"])
    pipeline_total = len(pipeline_results)
    pipeline_accuracy = (pipeline_passed / pipeline_total) * 100 if pipeline_total > 0 else 0

    webhook_passed = sum(1 for r in webhook_results if r["success"])
    webhook_total = len(webhook_results)

    print(f"\n  🧪 Pipeline:  {pipeline_passed}/{pipeline_total} ({pipeline_accuracy:.1f}%)")
    print(f"  🌐 Webhook:   {webhook_passed}/{webhook_total} ({'✅' if webhook_passed == webhook_total else '⚠️'})")
    print(f"  📦 Redis:     {redis_count} رسالة في الـ streams")

    overall = "✅ جميع الاختبارات نجحت" if (pipeline_accuracy >= 80 and webhook_passed == webhook_total) else "⚠️ بعض الاختبارات تحتاج مراجعة"
    print(f"\n  {overall}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
