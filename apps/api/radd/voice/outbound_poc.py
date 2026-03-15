#!/usr/bin/env python3
"""
COD Shield — Voice PoC (Proof of Concept)

Tests:
1. Making an outbound call via Twilio
2. Text-to-Speech in Egyptian Arabic
3. Receiving DTMF input (button presses) from customer

Usage:
    # Dry run (no actual call — just prints TwiML):
    cd apps/api && uv run python -m radd.voice.outbound_poc --dry-run

    # Make a real test call (requires Twilio credentials):
    cd apps/api && uv run python -m radd.voice.outbound_poc --call +201234567890

    # With custom order details:
    cd apps/api && uv run python -m radd.voice.outbound_poc --call +201234567890 \\
        --customer-name "أحمد" --order-id "ORD-12345" --store-name "متجر النور"
"""

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


# ─── TwiML Generator ───

def generate_confirmation_twiml(
    customer_name: str = "العميل",
    order_id: str = "12345",
    store_name: str = "المتجر",
    callback_url: str = "",
) -> str:
    """
    Generate TwiML XML for COD order confirmation call.

    Flow:
    1. Greeting + order details (Egyptian Arabic TTS)
    2. Ask for confirmation: "اضغط 1 للتأكيد، اضغط 2 للإلغاء"
    3. Gather DTMF input (timeout 10 seconds, max 1 digit)
    4. If no input → repeat once then hang up

    Uses Amazon Polly voice "Zeina" for Egyptian Arabic.
    """

    greeting_text = (
        f"أهلاً يا {customer_name}، "
        f"معاك {store_name}. "
        f"عندك طلب رقم {order_id} جاهز للشحن. "
    )

    confirmation_prompt = (
        "لو عايز نشحنلك الطلب، اضغط واحد. "
        "لو عايز تلغي الطلب، اضغط اتنين. "
    )

    no_input_message = (
        "معلش، مسمعتش ردك. "
        "اضغط واحد للتأكيد أو اتنين للإلغاء. "
    )

    goodbye_timeout = "مفيش رد. هنتواصل معاك تاني. شكراً!"

    # Action URL for gathering input
    action_url = callback_url or "/api/v1/webhooks/twilio/gather"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" timeout="10" action="{action_url}" method="POST">
        <Say voice="Polly.Zeina" language="ar-EG">
            {greeting_text}
            {confirmation_prompt}
        </Say>
    </Gather>
    <!-- If no input received, repeat once -->
    <Gather numDigits="1" timeout="8" action="{action_url}" method="POST">
        <Say voice="Polly.Zeina" language="ar-EG">
            {no_input_message}
        </Say>
    </Gather>
    <!-- If still no input, say goodbye -->
    <Say voice="Polly.Zeina" language="ar-EG">
        {goodbye_timeout}
    </Say>
    <Hangup/>
</Response>"""

    return twiml


def generate_gather_response_twiml(digit: str) -> str:
    """Generate TwiML response based on customer's DTMF input."""

    if digit == "1":
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Zeina" language="ar-EG">
        تمام، طلبك هيتشحن في أقرب وقت. شكراً ليك!
    </Say>
    <Hangup/>
</Response>"""

    elif digit == "2":
        # This is where "Save the Sale" will be added later
        # For PoC: just confirm cancellation
        # Phase 2: Ask why and try to save the sale via WhatsApp
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Zeina" language="ar-EG">
        تمام، تم تسجيل طلب الإلغاء. لو غيرت رأيك تواصل معانا. شكراً!
    </Say>
    <Hangup/>
</Response>"""

    else:
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Zeina" language="ar-EG">
        معلش، مفهمتش ردك. اضغط واحد للتأكيد أو اتنين للإلغاء.
    </Say>
    <Gather numDigits="1" timeout="8" action="/api/v1/webhooks/twilio/gather" method="POST">
        <Say voice="Polly.Zeina" language="ar-EG">
            واحد للتأكيد. اتنين للإلغاء.
        </Say>
    </Gather>
    <Hangup/>
</Response>"""


# ─── Call Initiator ───

def make_outbound_call(
    to_number: str,
    customer_name: str = "العميل",
    order_id: str = "12345",
    store_name: str = "المتجر",
) -> dict:
    """
    Initiate an outbound call via Twilio.

    Returns dict with call_sid and status, or error details.
    """
    try:
        from twilio.rest import Client

        from radd.config import settings

        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            return {
                "success": False,
                "error": "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env",
            }

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        twiml = generate_confirmation_twiml(
            customer_name=customer_name,
            order_id=order_id,
            store_name=store_name,
        )

        status_callback_url = f"{settings.api_base_url}/api/v1/webhooks/twilio/call-status"
        call_kwargs = {
            "to": to_number,
            "from_": settings.twilio_phone_number,
            "twiml": twiml,
        }
        if status_callback_url:
            call_kwargs["status_callback"] = status_callback_url
            call_kwargs["status_callback_event"] = ["completed", "busy", "no-answer", "failed"]

        call = client.calls.create(**call_kwargs)

        logger.info(f"Call initiated: SID={call.sid}, to={to_number}, status={call.status}")

        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "to": to_number,
            "order_id": order_id,
        }

    except ImportError:
        return {"success": False, "error": "twilio package not installed"}
    except Exception as e:
        logger.error(f"Failed to make call to {to_number}: {e}")
        return {"success": False, "error": str(e)}


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="COD Shield Voice PoC")
    parser.add_argument("--dry-run", action="store_true", help="Print TwiML without making a call")
    parser.add_argument("--call", type=str, help="Phone number to call (e.g., +201234567890)")
    parser.add_argument("--customer-name", default="أحمد", help="Customer name in Arabic")
    parser.add_argument("--order-id", default="ORD-12345", help="Order ID")
    parser.add_argument("--store-name", default="متجر النور", help="Store name in Arabic")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════╗")
    print("║  RADD AI — COD Shield Voice PoC      ║")
    print("╚══════════════════════════════════════╝\n")

    if args.dry_run or not args.call:
        print("📋 Mode: Dry Run (TwiML generation only)\n")

        twiml = generate_confirmation_twiml(
            customer_name=args.customer_name,
            order_id=args.order_id,
            store_name=args.store_name,
        )
        print("─── Generated TwiML ───")
        print(twiml)
        print("─── End TwiML ───\n")

        print("📋 Gather Response — Digit 1 (Confirm):")
        print(generate_gather_response_twiml("1"))
        print("\n📋 Gather Response — Digit 2 (Cancel):")
        print(generate_gather_response_twiml("2"))

        print("\n✅ TwiML generation works correctly.")
        print("💡 To make a real call: --call +201234567890")

    else:
        print(f"📞 Mode: Live Call to {args.call}\n")

        result = make_outbound_call(
            to_number=args.call,
            customer_name=args.customer_name,
            order_id=args.order_id,
            store_name=args.store_name,
        )

        if result["success"]:
            print(f"✅ Call initiated successfully!")
            print(f"   SID: {result['call_sid']}")
            print(f"   Status: {result['status']}")
            print(f"   To: {result['to']}")
        else:
            print(f"❌ Call failed: {result['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
