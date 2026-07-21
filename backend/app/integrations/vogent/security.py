from __future__ import annotations

import hashlib
import hmac


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_shared_secret(supplied: str, configured: str) -> bool:
    return hmac.compare_digest(supplied, configured)
