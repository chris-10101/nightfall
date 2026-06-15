from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse

from core.csv_store import append_csv_atomic, read_csv, write_csv_atomic
from core.eligibility_rules import FREE_PERSONAL_DOMAINS


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
REPLY_EVENTS_PATH = DATA_DIR / "reply_events.csv"

SUPPRESSION_HEADERS = [
    "email",
    "domain",
    "company_name",
    "reason",
    "source",
    "source_message_id",
    "scope",
    "expires_at",
    "added_at",
]

REPLY_EVENT_HEADERS = [
    "received_at",
    "sender",
    "recipient",
    "subject",
    "classification",
    "message_id",
    "matched_lead_id",
    "action_taken",
]

UNSUBSCRIBE_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\bremove us\b",
    r"\btake me off\b",
    r"\btake us off\b",
    r"\bstop emailing\b",
    r"\bstop contacting\b",
]

NOT_INTERESTED_PATTERNS = [
    r"\bnot interested\b",
    r"\bno thanks\b",
    r"\bno thank you\b",
    r"\bnot relevant\b",
    r"\bnot for us\b",
]

POSITIVE_PATTERNS = [
    r"\bsend (it|over|through)\b",
    r"\bsounds good\b",
    r"\binterested\b",
    r"\bbook\b",
    r"\bcall\b",
    r"\bmeeting\b",
    r"\boverview\b",
]

QUESTION_PATTERNS = [
    r"\bhow does\b",
    r"\bhow much\b",
    r"\bpricing\b",
    r"\bterms\b",
    r"\bwhat.+cost\b",
    r"\?",
]

REFERRAL_PATTERNS = [
    r"\bspeak to\b",
    r"\bcontact\b.+\b(colleague|partner|director|manager)\b",
    r"\bforward(ed)? to\b",
]

OOO_PATTERNS = [
    r"\bout of office\b",
    r"\baway from (the )?office\b",
    r"\bannual leave\b",
    r"\bauto.?reply\b",
    r"\bautomatic reply\b",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    write_csv_atomic(path, rows, headers)


def append_csv(path: Path, row: dict[str, str], headers: list[str]) -> None:
    append_csv_atomic(path, row, headers)


def email_domain(email: str) -> str:
    email = normalize_email(email)
    return email.rsplit("@", 1)[1] if "@" in email else ""


def normalize_email(value: str) -> str:
    parsed = parseaddr(value or "")[1]
    return (parsed or value or "").strip().lower()


def url_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def business_domain_for(row: dict[str, str], email: str = "") -> str:
    company_domain = (row.get("company_domain") or "").strip().lower()
    if company_domain:
        return company_domain
    website_url = (row.get("website_url") or "").strip()
    if website_url:
        return url_domain(website_url)
    domain = email_domain(email)
    return "" if domain in FREE_PERSONAL_DOMAINS else domain


def row_matches(row: dict[str, str], email: str, domain: str, company_name: str) -> bool:
    row_email = (row.get("email") or "").strip().lower()
    row_company = (row.get("company_name") or "").strip().lower()
    row_domain = business_domain_for(row, row_email)
    return bool(
        (email and row_email == email)
        or (domain and row_domain == domain)
        or (company_name and row_company == company_name)
    )


def add_suppression(
    *,
    email: str = "",
    domain: str = "",
    company_name: str = "",
    reason: str = "unsubscribe",
    source: str = "",
    source_message_id: str = "",
    scope: str = "company",
    expires_at: str = "",
) -> bool:
    email = normalize_email(email)
    company_name = (company_name or "").strip()
    domain = (domain or "").strip().lower()
    if not domain and email_domain(email) not in FREE_PERSONAL_DOMAINS:
        domain = email_domain(email)
    if not any([email, domain, company_name]):
        raise ValueError("Suppression requires email, domain, or company_name.")

    rows = read_csv(SUPPRESSION_PATH)
    for row in rows:
        if (
            (row.get("email") or "").strip().lower() == email
            and (row.get("domain") or "").strip().lower() == domain
            and (row.get("company_name") or "").strip().lower() == company_name.lower()
        ):
            return False

    rows.append(
        {
            "email": email,
            "domain": domain,
            "company_name": company_name,
            "reason": reason,
            "source": source,
            "source_message_id": source_message_id,
            "scope": scope,
            "expires_at": expires_at,
            "added_at": now_iso(),
        }
    )
    write_csv(SUPPRESSION_PATH, rows, SUPPRESSION_HEADERS)
    apply_suppression_to_state(email=email, domain=domain, company_name=company_name, reason=reason)
    return True


def apply_suppression_to_state(email: str, domain: str, company_name: str, reason: str) -> None:
    timestamp = now_iso()
    queue_rows = read_csv(QUEUE_PATH)
    queue_changed = False
    for row in queue_rows:
        if not row_matches(row, email, domain, company_name):
            continue
        row["last_reply_at"] = row.get("last_reply_at") or timestamp
        row["reply_status"] = "unsubscribed" if reason == "unsubscribe" else "not_interested"
        row["campaign_status"] = "stopped"
        row["next_action"] = "suppressed"
        row["eligibility_status"] = "blocked"
        existing_reasons = row.get("eligibility_reasons", "")
        block_reason = "suppressed_or_unsubscribed"
        row["eligibility_reasons"] = (
            existing_reasons if block_reason in existing_reasons else f"{existing_reasons};{block_reason}".strip(";")
        )
        queue_changed = True
    if queue_changed and queue_rows:
        write_csv(QUEUE_PATH, queue_rows, list(queue_rows[0].keys()))

    prospect_rows = read_csv(PROSPECTS_PATH)
    prospects_changed = False
    for row in prospect_rows:
        if not row_matches(row, email, domain, company_name):
            continue
        row["status"] = "do_not_contact"
        note = f"Suppressed via {reason} at {timestamp}"
        row["notes"] = append_note(row.get("notes", ""), note)
        prospects_changed = True
    if prospects_changed and prospect_rows:
        write_csv(PROSPECTS_PATH, prospect_rows, list(prospect_rows[0].keys()))


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


def classify_reply(subject: str, body: str) -> str:
    text = f"{subject or ''}\n{body or ''}".lower()
    if matches_any(text, UNSUBSCRIBE_PATTERNS):
        return "unsubscribe"
    if matches_any(text, NOT_INTERESTED_PATTERNS):
        return "not_interested"
    if matches_any(text, OOO_PATTERNS):
        return "out_of_office"
    if matches_any(text, REFERRAL_PATTERNS):
        return "referral"
    if matches_any(text, QUESTION_PATTERNS):
        return "question"
    if matches_any(text, POSITIVE_PATTERNS):
        return "positive"
    return "unclear"


def matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def record_reply(
    *,
    sender: str,
    recipient: str = "",
    subject: str = "",
    body: str = "",
    message_id: str = "",
    received_at: str = "",
) -> str:
    sender = normalize_email(sender)
    received_at = received_at or now_iso()
    classification = classify_reply(subject, body)
    queue_rows = read_csv(QUEUE_PATH)
    matched_lead_id = ""
    action_taken = "logged"

    for row in queue_rows:
        if (row.get("email") or "").strip().lower() != sender:
            continue
        matched_lead_id = row.get("lead_id", "")
        row["last_reply_at"] = received_at
        row["reply_status"] = classification
        row["campaign_status"] = "stopped" if classification != "out_of_office" else "paused"
        row["next_action"] = next_action_for(classification)
        action_taken = row["next_action"]
        if classification in {"unsubscribe", "not_interested"}:
            row["eligibility_status"] = "blocked"
            existing_reasons = row.get("eligibility_reasons", "")
            block_reason = "suppressed_or_unsubscribed"
            row["eligibility_reasons"] = (
                existing_reasons if block_reason in existing_reasons else f"{existing_reasons};{block_reason}".strip(";")
            )
            add_suppression(
                email=sender,
                domain=business_domain_for(row, sender),
                company_name=row.get("company_name", ""),
                reason=classification,
                source="reply_monitor",
                source_message_id=message_id,
            )
        break

    if queue_rows:
        write_csv(QUEUE_PATH, queue_rows, list(queue_rows[0].keys()))

    append_csv(
        REPLY_EVENTS_PATH,
        {
            "received_at": received_at,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "classification": classification,
            "message_id": message_id,
            "matched_lead_id": matched_lead_id,
            "action_taken": action_taken,
        },
        REPLY_EVENT_HEADERS,
    )
    return classification


def next_action_for(classification: str) -> str:
    return {
        "unsubscribe": "suppressed",
        "not_interested": "suppressed",
        "positive": "draft_reply",
        "question": "draft_reply",
        "referral": "review_referral",
        "out_of_office": "review_ooo",
        "unclear": "review_reply",
    }.get(classification, "review_reply")
