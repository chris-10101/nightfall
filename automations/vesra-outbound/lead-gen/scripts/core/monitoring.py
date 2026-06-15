import os
import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return EMAIL_RE.sub("[redacted-email]", value)
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_value(item) for item in value)
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"email", "sender", "recipient", "to", "from", "body", "stripped-text", "body-plain"}:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = scrub_value(item)
        return cleaned
    return value


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    return scrub_value(event)


def init_sentry(job_name: str) -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        release=os.environ.get("NIGHTFALL_RELEASE"),
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=before_send,
    )
    sentry_sdk.set_tag("automation", "vesra-outbound")
    sentry_sdk.set_tag("job", job_name)


def capture_exception(exc: BaseException) -> None:
    if not os.environ.get("SENTRY_DSN", "").strip():
        return
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.capture_exception(exc)
