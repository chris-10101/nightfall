"""Reusable outbound eligibility rules for Vesra lead generation.

The functions in this module are deliberately pure: they accept row dictionaries
and optional in-memory context, then return structured decisions. They do not
read or write CSV files, config files, or network resources.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from core.icp_profiles import active_segments, is_active_segment, profile_exclusion_hits, profile_required_signal


Reason = dict[str, str]
EligibilityResult = dict[str, Any]

UK_TZ = ZoneInfo("Europe/London")

BLOCK = "block"
WARN = "warn"
PASS = "pass"

BLOCKED_STATUS_VALUES = {
    "do_not_contact",
    "do not contact",
    "dnc",
    "not_fit",
    "not fit",
    "suppressed",
    "unsubscribed",
    "opted_out",
    "opted out",
}

STOP_REPLY_VALUES = {
    "replied",
    "positive",
    "interested",
    "not_interested",
    "not interested",
    "do_not_contact",
    "do not contact",
    "out_of_office",
    "out of office",
}

BOUNCE_VALUES = {
    "bounce",
    "bounced",
    "hard_bounce",
    "hard bounce",
    "soft_bounce",
    "soft bounce",
}

SUPPRESSION_FIELDS = (
    "suppressed",
    "is_suppressed",
    "unsubscribed",
    "is_unsubscribed",
    "opted_out",
    "do_not_contact",
)

STATUS_FIELDS = (
    "status",
    "company_status",
    "contact_status",
    "campaign_status",
    "suppression_status",
    "unsubscribe_status",
)

EVIDENCE_FIELDS = (
    "email_source_url",
    "website_url",
    "source_url",
    "company_linkedin_url",
    "decision_maker_linkedin_url",
    "linkedin_source_url",
    "headcount_source_url",
)

TEXT_FIELDS_FOR_RECRUITMENT_CHECK = (
    "segment",
    "subtype",
    "company_name",
    "notes",
    "short_reason",
    "personalisation",
    "source",
    "source_url",
    "website_url",
)

FREE_PERSONAL_DOMAINS = {
    "aol.com",
    "btinternet.com",
    "gmail.com",
    "googlemail.com",
    "hotmail.co.uk",
    "hotmail.com",
    "icloud.com",
    "live.co.uk",
    "live.com",
    "me.com",
    "msn.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.co.uk",
    "yahoo.com",
}

PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.co.uk",
    "example.org",
    "invalid.test",
    "test.com",
    "test.co.uk",
}

PLACEHOLDER_LOCAL_PARTS = {
    "admin",
    "donotreply",
    "do-not-reply",
    "email",
    "fake",
    "hello-world",
    "invalid",
    "mail",
    "n.a",
    "na",
    "no-reply",
    "no.email",
    "noemail",
    "none",
    "noreply",
    "notprovided",
    "null",
    "placeholder",
    "sample",
    "test",
    "unknown",
    "user",
}

GUESSED_SOURCE_MARKERS = {
    "guess",
    "guessed",
    "inferred",
    "pattern",
    "permutation",
    "predicted",
}

TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}


def evaluate_prospect(
    row: dict[str, Any],
    *,
    suppressed_values: set[str] | None = None,
    seen_email_keys: set[str] | None = None,
    seen_company_domain_keys: set[str] | None = None,
    seen_company_keys: set[str] | None = None,
    now: datetime | None = None,
    min_follow_up_days: int = 3,
    max_sequence_steps: int = 3,
    require_send_window: bool = False,
) -> EligibilityResult:
    """Evaluate whether a prospect row is eligible for outbound email.

    Optional sets let a caller add in-memory suppression and duplicate checks.
    They are read only; this function does not mutate them.
    """

    reasons: list[Reason] = []
    reasons.extend(check_required_email(row))
    reasons.extend(check_active_segment(row))
    reasons.extend(check_profile_required_signal(row))
    reasons.extend(check_profile_exclusions(row))
    reasons.extend(check_not_recruitment(row))
    reasons.extend(check_blocked_status(row))
    reasons.extend(check_public_evidence(row))
    reasons.extend(check_email_quality(row))
    reasons.extend(check_free_personal_email(row))
    reasons.extend(check_suppression_flags(row))
    reasons.extend(check_external_suppression(row, suppressed_values or set()))
    reasons.extend(check_duplicate_keys(row, seen_email_keys, seen_company_domain_keys, seen_company_keys))
    reasons.extend(check_stop_on_reply_or_bounce(row))
    reasons.extend(check_follow_up_spacing(row, now=now, min_days=min_follow_up_days))
    reasons.extend(check_sequence_cap(row, max_steps=max_sequence_steps))
    if require_send_window:
        reasons.extend(check_uk_working_hours(now=now))

    blocked = any(reason["severity"] == BLOCK for reason in reasons)
    return {
        "eligible": not blocked,
        "reasons": reasons,
        "dedupe_keys": dedupe_keys(row),
    }


def check_required_email(row: dict[str, Any]) -> list[Reason]:
    email = clean(row.get("email"))
    if not email:
        return [reason("missing_email", BLOCK, "Row has no email address.")]
    if not is_valid_email(email):
        return [reason("invalid_email", BLOCK, "Email address is not syntactically valid.")]
    return [reason("has_email", PASS, "Row has a usable email address.")]


def check_active_segment(row: dict[str, Any]) -> list[Reason]:
    segment = clean(row.get("segment"))
    if not is_active_segment(segment):
        allowed = ", ".join(sorted(active_segments()))
        return [reason("inactive_segment", BLOCK, f"Segment is not active for outbound. Active segments: {allowed}.")]
    return [reason("active_segment", PASS, f"Prospect is in active segment: {segment}.")]


def check_profile_required_signal(row: dict[str, Any]) -> list[Reason]:
    if profile_required_signal(row):
        return [reason("icp_required_signal", PASS, "Row has a required signal for its active ICP profile.")]
    return [reason("missing_icp_required_signal", BLOCK, "Row lacks required ICP evidence for its segment.")]


def check_profile_exclusions(row: dict[str, Any]) -> list[Reason]:
    hits = profile_exclusion_hits(row)
    if hits:
        return [reason("icp_exclusion", BLOCK, "Profile exclusion signal found: " + ", ".join(hits))]
    return [reason("icp_exclusions_ok", PASS, "No profile-specific exclusion signal found.")]


def check_not_recruitment(row: dict[str, Any]) -> list[Reason]:
    if looks_like_recruitment(row):
        return [reason("recruitment_not_partner_icp", BLOCK, "Recruitment businesses are excluded.")]
    return [reason("not_recruitment", PASS, "No recruitment exclusion signal found.")]


def check_blocked_status(row: dict[str, Any]) -> list[Reason]:
    hits = []
    for field in STATUS_FIELDS:
        value = normalize_token(row.get(field))
        if value in BLOCKED_STATUS_VALUES:
            hits.append(f"{field}={value}")
    if hits:
        return [reason("blocked_status", BLOCK, "Blocked status present: " + ", ".join(hits))]
    return [reason("status_ok", PASS, "No not_fit or do_not_contact status found.")]


def check_public_evidence(row: dict[str, Any]) -> list[Reason]:
    if has_public_evidence(row):
        return [reason("public_evidence", PASS, "Row has public source evidence.")]
    return [
        reason(
            "missing_public_evidence",
            BLOCK,
            "A public email source URL, website URL, LinkedIn URL, or source URL is required.",
        )
    ]


def check_email_quality(row: dict[str, Any]) -> list[Reason]:
    email = clean(row.get("email")).lower()
    if not email or not is_valid_email(email):
        return []
    local_part, domain = email.rsplit("@", 1)
    if domain in PLACEHOLDER_DOMAINS or local_part in PLACEHOLDER_LOCAL_PARTS:
        return [reason("placeholder_email", BLOCK, "Placeholder or no-reply style email address.")]
    if local_part.startswith(("test", "example", "sample")):
        return [reason("placeholder_email", BLOCK, "Placeholder email local part.")]
    if has_guessed_email_signal(row):
        return [reason("guessed_email", BLOCK, "Email appears guessed or pattern-inferred.")]
    return [reason("email_quality_ok", PASS, "Email is not flagged as guessed or placeholder.")]


def check_free_personal_email(row: dict[str, Any]) -> list[Reason]:
    domain = email_domain(row)
    if domain not in FREE_PERSONAL_DOMAINS:
        return [reason("business_email_domain", PASS, "Email is not on a known free personal domain.")]
    if is_source_backed_business_contact(row):
        return [
            reason(
                "source_backed_personal_domain",
                WARN,
                "Free personal domain is allowed only because it is source-backed as a business contact.",
            )
        ]
    return [
        reason(
            "free_personal_email",
            BLOCK,
            "Free personal email domains require source-backed evidence that this is a business contact.",
        )
    ]


def check_suppression_flags(row: dict[str, Any]) -> list[Reason]:
    hits = []
    for field in SUPPRESSION_FIELDS:
        value = normalize_token(row.get(field))
        if value in TRUTHY_VALUES or value in BLOCKED_STATUS_VALUES:
            hits.append(field)
    for field in STATUS_FIELDS:
        value = normalize_token(row.get(field))
        if value in {"suppressed", "unsubscribed", "opted_out", "opted out"}:
            hits.append(f"{field}={value}")
    if hits:
        return [reason("suppressed_or_unsubscribed", BLOCK, "Suppression flag present: " + ", ".join(hits))]
    return [reason("suppression_flags_ok", PASS, "No suppression or unsubscribe field blocks the row.")]


def check_external_suppression(row: dict[str, Any], suppressed_values: set[str]) -> list[Reason]:
    if not suppressed_values:
        return []
    keys = suppression_keys(row)
    matched = sorted(key for key in keys if key in suppressed_values)
    if matched:
        return [reason("external_suppression_match", BLOCK, "Matched suppression key: " + ", ".join(matched))]
    return [reason("external_suppression_ok", PASS, "No supplied suppression key matched.")]


def check_duplicate_keys(
    row: dict[str, Any],
    seen_email_keys: set[str] | None = None,
    seen_company_domain_keys: set[str] | None = None,
    seen_company_keys: set[str] | None = None,
) -> list[Reason]:
    reasons: list[Reason] = []
    keys = dedupe_keys(row)

    if seen_email_keys is not None and keys["email"] and keys["email"] in seen_email_keys:
        reasons.append(reason("duplicate_email", BLOCK, "Email has already been selected."))
    if (
        seen_company_domain_keys is not None
        and keys["company_domain"]
        and keys["company_domain"] in seen_company_domain_keys
    ):
        reasons.append(reason("duplicate_company_domain", BLOCK, "Company/domain pair has already been selected."))
    if seen_company_keys is not None and keys["company"] and keys["company"] in seen_company_keys:
        reasons.append(reason("duplicate_company", WARN, "Company name has already appeared in this selection."))

    return reasons


def check_uk_working_hours(
    *,
    now: datetime | None = None,
    start: time = time(9, 0),
    end: time = time(17, 0),
    weekdays_only: bool = True,
) -> list[Reason]:
    if is_uk_working_hours(now=now, start=start, end=end, weekdays_only=weekdays_only):
        return [reason("uk_working_hours", PASS, "Current time is inside the UK working-hours send window.")]
    return [reason("outside_uk_working_hours", BLOCK, "Send only during UK working hours.")]


def check_follow_up_spacing(
    row: dict[str, Any],
    *,
    now: datetime | None = None,
    min_days: int = 3,
) -> list[Reason]:
    ok, detail = follow_up_spacing_ok(row, now=now, min_days=min_days)
    if ok:
        return [reason("follow_up_spacing_ok", PASS, detail)]
    return [reason("follow_up_too_soon", BLOCK, detail)]


def check_sequence_cap(row: dict[str, Any], *, max_steps: int = 3) -> list[Reason]:
    ok, count = within_sequence_cap(row, max_steps=max_steps)
    if ok:
        return [reason("sequence_cap_ok", PASS, f"Sequence count {count} is below cap {max_steps}.")]
    return [reason("sequence_cap_reached", BLOCK, f"Sequence count {count} has reached cap {max_steps}.")]


def check_stop_on_reply_or_bounce(row: dict[str, Any]) -> list[Reason]:
    stops = stop_on_reply_or_bounce_reasons(row)
    if stops:
        return [reason("stop_on_reply_or_bounce", BLOCK, "Stop condition present: " + ", ".join(stops))]
    return [reason("no_reply_or_bounce_stop", PASS, "No reply or bounce stop condition found.")]


def dedupe_keys(row: dict[str, Any]) -> dict[str, str]:
    return {
        "email": email_key(row),
        "domain": email_domain(row),
        "company": company_key(row),
        "company_domain": company_domain_key(row),
    }


def email_key(row: dict[str, Any]) -> str:
    return clean(row.get("email")).lower()


def email_domain(row: dict[str, Any]) -> str:
    email = email_key(row)
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1]


def company_key(row: dict[str, Any]) -> str:
    company = normalize_token(row.get("company_name"))
    company = re.sub(r"\b(ltd|limited|llp|plc|uk|the)\b", "", company)
    return re.sub(r"\s+", " ", company).strip()


def website_domain(row: dict[str, Any]) -> str:
    for field in ("website_url", "source_url", "email_source_url"):
        domain = domain_from_url(clean(row.get(field)))
        if domain:
            return domain
    return ""


def company_domain_key(row: dict[str, Any]) -> str:
    company = company_key(row)
    domain = website_domain(row) or email_domain(row)
    if not company and not domain:
        return ""
    return f"{company}|{domain}"


def suppression_keys(row: dict[str, Any]) -> set[str]:
    return {key for key in (email_key(row), email_domain(row), company_key(row), company_domain_key(row)) if key}


def is_uk_working_hours(
    *,
    now: datetime | None = None,
    start: time = time(9, 0),
    end: time = time(17, 0),
    weekdays_only: bool = True,
) -> bool:
    current = as_uk_datetime(now)
    if weekdays_only and current.weekday() >= 5:
        return False
    current_time = current.time().replace(tzinfo=None)
    return start <= current_time < end


def follow_up_spacing_ok(
    row: dict[str, Any],
    *,
    now: datetime | None = None,
    min_days: int = 3,
) -> tuple[bool, str]:
    current = as_uk_datetime(now)
    follow_up_at = parse_datetime(row.get("follow_up_at"))
    if follow_up_at is not None:
        due_at = as_uk_datetime(follow_up_at)
        if current < due_at:
            return False, f"Follow-up is scheduled for {due_at.isoformat()}."
        return True, "Follow-up date is due."

    last_outbound_at = first_datetime(row, ("last_outbound_at", "contacted_at", "sent_at"))
    if last_outbound_at is None:
        return True, "No previous outbound timestamp found."

    next_allowed = as_uk_datetime(last_outbound_at) + timedelta(days=min_days)
    if current < next_allowed:
        return False, f"Next follow-up is allowed from {next_allowed.isoformat()}."
    return True, "Minimum follow-up spacing has elapsed."


def within_sequence_cap(row: dict[str, Any], *, max_steps: int = 3) -> tuple[bool, int]:
    count = sequence_count(row)
    return count < max_steps, count


def sequence_count(row: dict[str, Any]) -> int:
    for field in ("sequence_step", "sequence_count", "outbound_count", "send_count", "follow_up_count"):
        value = clean(row.get(field))
        if value.isdigit():
            return int(value)
    if clean(row.get("last_outbound_at")) or clean(row.get("contacted_at")):
        return 1
    return 0


def stop_on_reply_or_bounce_reasons(row: dict[str, Any]) -> list[str]:
    stops: list[str] = []
    if clean(row.get("last_reply_at")):
        stops.append("last_reply_at")
    for field in ("reply_status", "campaign_status", "next_action"):
        value = normalize_token(row.get(field))
        if value in STOP_REPLY_VALUES:
            stops.append(f"{field}={value}")
    if clean(row.get("bounced_at")):
        stops.append("bounced_at")
    for field in ("bounce_status", "delivery_status", "smtp_status"):
        value = normalize_token(row.get(field))
        if value in BOUNCE_VALUES:
            stops.append(f"{field}={value}")
    return stops


def has_public_evidence(row: dict[str, Any]) -> bool:
    return any(is_public_url(clean(row.get(field))) for field in EVIDENCE_FIELDS)


def is_source_backed_business_contact(row: dict[str, Any]) -> bool:
    email_source_url = clean(row.get("email_source_url"))
    if not is_public_url(email_source_url):
        return False
    if has_guessed_email_signal(row):
        return False
    return bool(clean(row.get("company_name")) or clean(row.get("decision_maker_name")))


def has_guessed_email_signal(row: dict[str, Any]) -> bool:
    values = [
        clean(row.get("email_type")),
        clean(row.get("email_confidence")),
        clean(row.get("email_source")),
        clean(row.get("email_source_url")),
        clean(row.get("notes")),
    ]
    haystack = " ".join(values).lower()
    return any(marker in haystack for marker in GUESSED_SOURCE_MARKERS)


def looks_like_recruitment(row: dict[str, Any]) -> bool:
    haystack = " ".join(clean(row.get(field)) for field in TEXT_FIELDS_FOR_RECRUITMENT_CHECK).lower()
    if not haystack:
        return False
    recruitment_patterns = (
        r"\brecruit(?:ment|er|ing|ers)?\b",
        r"\bstaffing\b",
        r"\btalent acquisition\b",
        r"\bexecutive search\b",
    )
    return any(re.search(pattern, haystack) for pattern in recruitment_patterns)


def first_datetime(row: dict[str, Any], fields: tuple[str, ...]) -> datetime | None:
    for field in fields:
        parsed = parse_datetime(row.get(field))
        if parsed is not None:
            return parsed
    return None


def parse_datetime(value: Any) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UK_TZ)
    return parsed


def as_uk_datetime(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(UK_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=UK_TZ)
    return value.astimezone(UK_TZ)


def is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def domain_from_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else "https://" + value)
    domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_token(value: Any) -> str:
    return re.sub(r"\s+", " ", clean(value).lower().replace("-", "_")).strip()


def reason(code: str, severity: str, message: str) -> Reason:
    return {"code": code, "severity": severity, "message": message}
