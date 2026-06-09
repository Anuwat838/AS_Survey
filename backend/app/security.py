from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"), salt, 120_000)
    return "pbkdf2_sha256$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_pin(pin: str, stored: str) -> bool:
    try:
        alg, salt_b64, digest_b64 = stored.split("$", 2)
        if alg != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)
