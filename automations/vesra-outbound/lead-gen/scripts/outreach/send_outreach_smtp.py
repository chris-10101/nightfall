from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import smtplib
from datetime import datetime, time, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from core.csv_store import read_csv, write_csv_atomic
from core.eligibility_rules import dedupe_keys, evaluate_prospect, is_uk_working_hours
from core.paths import config_dir, data_dir
from outreach.unsubscribe_tokens import unsubscribe_url


CONFIG_DIR = config_dir()
DATA_DIR = data_dir()
CONFIG_PATH = CONFIG_DIR / "outbound_config.json"
CONFIG_EXAMPLE_PATH = CONFIG_DIR / "outbound_config.example.json"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"
UK_TZ = ZoneInfo("Europe/London")


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    with path.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    write_csv_atomic(path, rows, headers)


def build_message(config: dict, row: dict[str, str]) -> EmailMessage:
    message = EmailMessage()
    sender_name = config["sender_name"]
    from_email = config["from_email"]
    message["From"] = f"{sender_name} <{from_email}>"
    message["To"] = row["email"]
    message["Subject"] = row["subject"]
    if config.get("reply_to"):
        message["Reply-To"] = config["reply_to"]
    unsubscribe_mailto = config.get("unsubscribe_mailto") or config.get("reply_to") or from_email
    url_unsubscribe = unsubscribe_url(config, row)
    unsubscribe_targets = []
    if url_unsubscribe:
        unsubscribe_targets.append(f"<{url_unsubscribe}>")
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if unsubscribe_mailto:
        subject = quote(config.get("unsubscribe_subject", "Unsubscribe"))
        unsubscribe_targets.append(f"<mailto:{unsubscribe_mailto}?subject={subject}>")
    if unsubscribe_targets:
        message["List-Unsubscribe"] = ", ".join(unsubscribe_targets)
    body = with_unsubscribe_text(config, row)
    message.set_content(body)
    return message


def with_unsubscribe_text(config: dict, row: dict[str, str]) -> str:
    body = row["draft_body"]
    unsubscribe_text = config.get(
        "unsubscribe_text",
        "If this is not relevant, reply unsubscribe and I will not contact you again.",
    )
    url_unsubscribe = unsubscribe_url(config, row)
    if url_unsubscribe:
        unsubscribe_line = f"Unsubscribe: {url_unsubscribe}"
    else:
        unsubscribe_mailto = config.get("unsubscribe_mailto") or config.get("reply_to") or config.get("from_email")
        if unsubscribe_mailto:
            unsubscribe_line = f"Unsubscribe: mailto:{unsubscribe_mailto}?subject=Unsubscribe"
        else:
            unsubscribe_line = ""
    if unsubscribe_line and unsubscribe_line in body:
        return body
    if "Unsubscribe:" in body and unsubscribe_line:
        return f"{body.rstrip()}\n{unsubscribe_line}"
    footer = f"{unsubscribe_text}\n{unsubscribe_line}".rstrip()
    return f"{body.rstrip()}\n\n{footer}"


def suppression_values() -> set[str]:
    rows = read_csv(SUPPRESSION_PATH) if SUPPRESSION_PATH.exists() else []
    values = set()
    for row in rows:
        for key in ("email", "domain", "company_name"):
            value = row.get(key, "").strip().lower()
            if value:
                values.add(value)
    return values


def parse_time(value: str, default: time) -> time:
    if not value:
        return default
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def sent_today(row: dict[str, str], now: datetime) -> bool:
    value = row.get("last_outbound_at", "").strip()
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(UK_TZ).date() == now.astimezone(UK_TZ).date()


def queue_rows_by_lead_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["lead_id"]: row for row in rows if row.get("lead_id")}


def validate_send_window(config: dict, now: datetime) -> None:
    if not config.get("send_weekdays_only", True) and not config.get("send_window_start"):
        return
    start = parse_time(config.get("send_window_start", "09:30"), time(9, 30))
    end = parse_time(config.get("send_window_end", "16:00"), time(16, 0))
    if not is_uk_working_hours(
        now=now,
        start=start,
        end=end,
        weekdays_only=config.get("send_weekdays_only", True),
    ):
        raise SystemExit(
            f"Outside allowed UK send window ({start.strftime('%H:%M')}-{end.strftime('%H:%M')} Europe/London)."
        )


def validate_batch_rows(config: dict, batch_rows: list[dict[str, str]], queue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    now = datetime.now(UK_TZ)
    suppressed = suppression_values()
    queue_by_lead_id = queue_rows_by_lead_id(queue_rows)
    daily_limit = int(config.get("daily_send_limit", 20))
    per_domain_limit = int(config.get("per_domain_daily_limit", 1))
    sent_today_count = sum(1 for row in queue_rows if sent_today(row, now))
    if sent_today_count + len(batch_rows) > daily_limit:
        raise SystemExit(
            f"Daily send limit would be exceeded: {sent_today_count} already sent today, "
            f"{len(batch_rows)} in batch, limit {daily_limit}."
        )

    domain_counts: dict[str, int] = {}
    for row in queue_rows:
        if not sent_today(row, now):
            continue
        domain = row.get("company_domain", "").strip().lower() or dedupe_keys(row)["domain"]
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    validated_rows: list[dict[str, str]] = []
    seen_batch_emails: set[str] = set()
    seen_batch_domains: set[str] = set()
    for batch_row in batch_rows:
        queue_row = queue_by_lead_id.get(batch_row.get("lead_id", ""))
        if not queue_row:
            raise SystemExit(f"Batch row is not present in campaign_queue.csv: {batch_row.get('lead_id')}")
        row = dict(queue_row)
        row.update({key: value for key, value in batch_row.items() if value})
        keys = dedupe_keys(row)
        domain = row.get("company_domain", "").strip().lower() or keys["domain"]
        if keys["email"] in seen_batch_emails:
            raise SystemExit(f"Duplicate email in batch: {keys['email']}")
        if domain and domain in seen_batch_domains:
            raise SystemExit(f"Duplicate company domain in batch: {domain}")
        if domain and domain_counts.get(domain, 0) >= per_domain_limit:
            raise SystemExit(f"Per-domain daily limit reached for {domain}.")
        result = evaluate_prospect(
            row,
            suppressed_values=suppressed,
            max_sequence_steps=int(row.get("max_follow_ups") or 3),
        )
        if not result["eligible"]:
            reasons = ", ".join(
                reason["code"] for reason in result["reasons"] if reason.get("severity") == "block"
            )
            raise SystemExit(f"Unsafe batch row blocked for {row.get('company_name')}: {reasons}")
        seen_batch_emails.add(keys["email"])
        if domain:
            seen_batch_domains.add(domain)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        validated_rows.append(row)
    return validated_rows


def mark_sent(batch_rows: list[dict[str, str]], dry_run: bool) -> None:
    if dry_run:
        return
    queue_rows = read_csv(QUEUE_PATH)
    sent_ids = {row["lead_id"] for row in batch_rows}
    now = datetime.now(timezone.utc).isoformat()
    for row in queue_rows:
        if row["lead_id"] in sent_ids:
            row["campaign_status"] = "sent"
            row["last_outbound_at"] = now
            row["send_count"] = str(int(row.get("send_count") or 0) + 1)
            row["next_action"] = "monitor_reply"
    write_csv(QUEUE_PATH, queue_rows, list(queue_rows[0].keys()) if queue_rows else [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Send or dry-run an outreach batch via SMTP.")
    parser.add_argument("batch_csv", help="CSV produced by prepare_outreach_batch.py")
    parser.add_argument("--send", action="store_true", help="Actually send emails. Omit for dry-run.")
    args = parser.parse_args()

    config = load_config()
    batch_rows = read_csv(Path(args.batch_csv))
    queue_rows = read_csv(QUEUE_PATH)
    dry_run = not args.send
    if args.send:
        validate_send_window(config, datetime.now(UK_TZ))
    batch_rows = validate_batch_rows(config, batch_rows, queue_rows)

    messages = [build_message(config, row) for row in batch_rows]

    if dry_run:
        for message in messages:
            print(f"DRY RUN: {message['From']} -> {message['To']} | {message['Subject']}")
        print(f"Prepared {len(messages)} messages. No email sent.")
        return

    if config.get("review_required_before_send", True):
        raise SystemExit("Config has review_required_before_send=true. Set it false only after reviewing the batch.")

    smtp_config = config["smtp"]
    username = os.environ.get(smtp_config["username_env"])
    password = os.environ.get(smtp_config["password_env"])
    if not username or not password:
        raise SystemExit(
            f"Missing SMTP credentials. Set {smtp_config['username_env']} and {smtp_config['password_env']}."
        )

    with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        for message in messages:
            smtp.send_message(message)
            print(f"SENT: {message['To']} | {message['Subject']}")

    mark_sent(batch_rows, dry_run=False)


if __name__ == "__main__":
    main()
