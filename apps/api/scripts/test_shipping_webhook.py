#!/usr/bin/env python3
"""Quick test for shipping webhook endpoints."""

import asyncio

import httpx


async def test():
    base = "http://localhost:8000"

    print("═══ Testing Shipping Webhooks ═══\n")

    # Test 1: Generic — delivery_failed (should queue)
    print("Test 1: Generic — delivery_failed")
    payload = {
        "order_id": "TEST-100",
        "status": "delivery_failed",
        "carrier": "aramex",
        "tracking_number": "ARX123456",
        "customer_phone": "+201234567890",
        "customer_name": "أحمد",
        "store_name": "متجر تست",
        "workspace_id": "00000000-0000-0000-0000-000000000000",
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{base}/api/v1/webhooks/shipping/generic", json=payload)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  Error: {e} (expected if server not running)")

    # Test 2: Generic — delivered (should NOT queue)
    print("\nTest 2: Generic — delivered")
    payload["status"] = "delivered"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{base}/api/v1/webhooks/shipping/generic", json=payload)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  Error: {e} (expected if server not running)")

    # Test 3: Generic — no phone (should skip)
    print("\nTest 3: Generic — no phone")
    payload["status"] = "delivery_failed"
    payload["customer_phone"] = None
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{base}/api/v1/webhooks/shipping/generic", json=payload)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  Error: {e} (expected if server not running)")

    print("\n✅ Test script completed")
    print("💡 Run API first: make api")


if __name__ == "__main__":
    asyncio.run(test())
