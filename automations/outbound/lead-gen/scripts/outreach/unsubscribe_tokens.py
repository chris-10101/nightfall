from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import hashlib
import hmac
import json
import os
from typing import Any
from urllib.parse import urlencode


DEFAULT_SECRET_ENV = "VESRA_UNSUBSCRIBE_SECRET"


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(payload: dict[str, Any], secret: str) -> str:
    clean_payload = {key: str(value or "") for key, value in payload.items()}
    clean_payload["v"] = "1"
    payload_bytes = json.dumps(clean_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_part = b64url_encode(payload_bytes)
    signature = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{b64url_encode(signature)}"


def verify_token(token: str, secret: str) -> dict[str, str]:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed unsubscribe token.") from exc
    expected = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    actual = b64url_decode(signature_part)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid unsubscribe token signature.")
    payload = json.loads(b64url_decode(payload_part).decode("utf-8"))
    return {str(key): str(value or "") for key, value in payload.items()}


def unsubscribe_url(config: dict, row: dict[str, str]) -> str:
    base_url = (config.get("unsubscribe_base_url") or "").strip()
    if not base_url:
        return ""
    secret_env = config.get("unsubscribe_secret_env") or DEFAULT_SECRET_ENV
    secret = os.environ.get(secret_env, "")
    if not secret:
        return ""
    token = create_token(
        {
            "email": row.get("email", ""),
            "company_name": row.get("company_name", ""),
            "company_domain": row.get("company_domain", ""),
            "lead_id": row.get("lead_id", ""),
            "campaign_name": row.get("campaign_name", ""),
        },
        secret,
    )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'token': token})}"
