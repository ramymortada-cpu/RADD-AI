"""
Token encryption at rest for channel configs.
Uses Fernet (AES-128-CBC) with key derived from SECRET_KEY.
"""
from __future__ import annotations
import base64
import hashlib
import os

from radd.config import settings

# Keys that must be encrypted in channel config
_TOKEN_KEYS = frozenset({
    "wa_api_token", "page_access_token", "access_token",
    "api_token", "salla_token", "zid_token",
})


def _get_fernet_key() -> bytes:
    """Derive a 32-byte key for Fernet from SECRET_KEY."""
    key = (settings.secret_key or "radd-default-secret").encode()
    return base64.urlsafe_b64encode(hashlib.sha256(key).digest())


def _get_cipher():
    from cryptography.fernet import Fernet
    return Fernet(_get_fernet_key())


def encrypt_token(plain: str) -> str:
    """Encrypt a token for storage. Returns base64 string."""
    if not plain:
        return ""
    try:
        return _get_cipher().encrypt(plain.encode()).decode()
    except Exception:
        return plain  # Fallback: store as-is if encryption fails


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token."""
    if not encrypted:
        return ""
    # Check if it looks like Fernet (base64, 4 parts)
    if ":" in encrypted or len(encrypted) < 50:
        return encrypted  # Likely plaintext (legacy)
    try:
        return _get_cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted  # Fallback: return as-is


def encrypt_sensitive_config(config: dict) -> dict:
    """Encrypt all token-like keys in a config dict."""
    if not config:
        return config
    out = dict(config)
    for k, v in out.items():
        if k.lower() in _TOKEN_KEYS and isinstance(v, str) and v and not v.startswith("gAAAAA"):
            out[k] = encrypt_token(v)
    return out


def decrypt_sensitive_config(config: dict) -> dict:
    """Decrypt all token-like keys when reading from DB."""
    if not config:
        return config
    out = dict(config)
    for k, v in out.items():
        if k.lower() in _TOKEN_KEYS and isinstance(v, str) and v:
            out[k] = decrypt_token(v)
    return out


def get_channel_config_decrypted(channel) -> dict:
    """Get channel config with tokens decrypted. Use when reading for API calls."""
    cfg = getattr(channel, "config", None) or {}
    return decrypt_sensitive_config(cfg)
