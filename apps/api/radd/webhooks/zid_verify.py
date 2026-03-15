"""
Zid webhook HMAC-SHA256 verification.

Zid sends the signature in the header: X-Zid-Signature
Format: sha256=<hex_digest>

Docs: https://docs.zid.sa/docs/webhooks
"""

import hashlib
import hmac

import structlog

logger = structlog.get_logger(__name__)


def verify_zid_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """
    Verify Zid webhook HMAC-SHA256 signature.

    Args:
        payload:          Raw request body bytes.
        signature_header: Value of X-Zid-Signature header.
        secret:           ZID_WEBHOOK_SECRET from config.

    Returns:
        True if signature is valid, False otherwise.
    """
    # إذا السر فاضي → نرفض دائماً (لا نسمح بتجاوز الأمان)
    if not secret:
        logger.error(
            "zid_webhook_secret_not_configured",
            warning="ZID_WEBHOOK_SECRET is empty — rejecting all Zid webhooks",
        )
        return False

    if not signature_header:
        logger.warning("zid_missing_signature_header")
        return False

    # Zid format: "sha256=<hex>"
    if signature_header.startswith("sha256="):
        provided_sig = signature_header[7:]
    else:
        # fallback: بعض الإصدارات ترسل hex مباشرة
        provided_sig = signature_header

    # احسب التوقيع المتوقع
    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # مقارنة constant-time لمنع timing attacks
    is_valid = hmac.compare_digest(expected_sig, provided_sig)

    if not is_valid:
        logger.warning(
            "zid_invalid_signature",
            provided=provided_sig[:16] + "...",  # أول 16 حرف للـ debug
        )

    return is_valid
