from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

from outreach.unsubscribe_tokens import unsubscribe_url


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"
TEST_DIR = BASE_DIR / "tests"
OUTBOUND_CONFIG_PATH = CONFIG_DIR / "outbound_config.json"
OUTBOUND_CONFIG_EXAMPLE_PATH = CONFIG_DIR / "outbound_config.example.json"
TEST_CONFIG_PATH = CONFIG_DIR / "test_campaign_config.json"
TEST_CONFIG_EXAMPLE_PATH = CONFIG_DIR / "test_campaign_config.example.json"
STATE_PATH = TEST_DIR / "test_campaign_state.csv"


STATE_HEADERS = [
    "step",
    "delay_minutes",
    "subject",
    "status",
    "scheduled_at",
    "sent_at",
    "recipient",
    "last_error",
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as json_file:
        return json.load(json_file)


def load_outbound_config() -> dict:
    path = OUTBOUND_CONFIG_PATH if OUTBOUND_CONFIG_PATH.exists() else OUTBOUND_CONFIG_EXAMPLE_PATH
    return read_json(path)


def load_test_config() -> dict:
    path = TEST_CONFIG_PATH if TEST_CONFIG_PATH.exists() else TEST_CONFIG_EXAMPLE_PATH
    return read_json(path)


def read_state() -> list[dict[str, str]]:
    if not STATE_PATH.exists():
        return []
    with STATE_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_state(rows: list[dict[str, str]]) -> None:
    with STATE_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=STATE_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def init_state(recipient: str, reset: bool) -> list[dict[str, str]]:
    if STATE_PATH.exists() and not reset:
        return read_state()

    test_config = load_test_config()
    start = now_utc()
    rows = []
    for item in test_config["sequence"]:
        scheduled_at = start + timedelta(minutes=int(item["delay_minutes"]))
        rows.append(
            {
                "step": str(item["step"]),
                "delay_minutes": str(item["delay_minutes"]),
                "subject": item["subject"],
                "status": "pending",
                "scheduled_at": scheduled_at.isoformat(),
                "sent_at": "",
                "recipient": recipient,
                "last_error": "",
            }
        )
    write_state(rows)
    return rows


def sequence_by_step() -> dict[str, dict[str, str]]:
    config = load_test_config()
    return {str(item["step"]): item for item in config["sequence"]}


def build_message(outbound_config: dict, recipient: str, subject: str, body: str, step: str = "") -> EmailMessage:
    message = EmailMessage()
    sender_name = outbound_config["sender_name"]
    from_email = outbound_config["from_email"]
    message["From"] = f"{sender_name} <{from_email}>"
    message["To"] = recipient
    message["Subject"] = subject
    if outbound_config.get("reply_to"):
        message["Reply-To"] = outbound_config["reply_to"]
    unsubscribe_mailto = outbound_config.get("unsubscribe_mailto") or outbound_config.get("reply_to") or from_email
    row = {
        "email": recipient,
        "company_name": "Internal test inbox",
        "company_domain": recipient.rsplit("@", 1)[1] if "@" in recipient else "",
        "lead_id": f"test-campaign-step-{step or 'unknown'}",
        "campaign_name": "vesra_partner_program_test",
    }
    url_unsubscribe = unsubscribe_url(outbound_config, row)
    unsubscribe_targets = []
    if url_unsubscribe:
        unsubscribe_targets.append(f"<{url_unsubscribe}>")
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if unsubscribe_mailto:
        unsubscribe_subject = quote(outbound_config.get("unsubscribe_subject", "Unsubscribe"))
        unsubscribe_targets.append(f"<mailto:{unsubscribe_mailto}?subject={unsubscribe_subject}>")
    if unsubscribe_targets:
        message["List-Unsubscribe"] = ", ".join(unsubscribe_targets)
    if url_unsubscribe and url_unsubscribe not in body:
        if "Unsubscribe:" in body:
            body = f"{body.rstrip()}\nUnsubscribe: {url_unsubscribe}"
        else:
            unsubscribe_text = outbound_config.get(
                "unsubscribe_text",
                "If this is not relevant, reply unsubscribe and I will not contact you again.",
            )
            body = f"{body.rstrip()}\n\n{unsubscribe_text}\nUnsubscribe: {url_unsubscribe}"
    message.set_content(body)
    return message


def send_messages(messages: list[EmailMessage], outbound_config: dict) -> None:
    smtp_config = outbound_config["smtp"]
    username = os.environ.get(smtp_config["username_env"])
    password = os.environ.get(smtp_config["password_env"])
    if not username or not password:
        raise RuntimeError(
            f"Missing SMTP credentials. Set {smtp_config['username_env']} and {smtp_config['password_env']}."
        )

    with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        for message in messages:
            smtp.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a safe multi-step test campaign to one test inbox.")
    parser.add_argument("--init", action="store_true", help="Initialise the test sequence state.")
    parser.add_argument("--reset", action="store_true", help="Reset existing test campaign state.")
    parser.add_argument("--send", action="store_true", help="Actually send due messages. Omit for dry-run.")
    parser.add_argument("--max-due", type=int, default=1, help="Maximum due messages to send in this run.")
    parser.add_argument("--recipient", help="Override test recipient. Prefer VESRA_TEST_RECIPIENT env var.")
    args = parser.parse_args()

    outbound_config = load_outbound_config()
    test_config = load_test_config()
    recipient = args.recipient or os.environ.get(test_config["test_recipient_env"], "")
    if not recipient:
        raise SystemExit(f"Missing test recipient. Set {test_config['test_recipient_env']} or pass --recipient.")

    rows = init_state(recipient, reset=args.reset) if args.init or args.reset or not STATE_PATH.exists() else read_state()
    sequence = sequence_by_step()
    due_rows = [
        row
        for row in rows
        if row["status"] == "pending" and parse_dt(row["scheduled_at"]) <= now_utc()
    ][: args.max_due]

    if not due_rows:
        print("No due test campaign messages.")
        return

    messages = []
    for row in due_rows:
        item = sequence[row["step"]]
        messages.append(build_message(outbound_config, recipient, item["subject"], item["body"], row["step"]))

    dry_run = not args.send
    if dry_run:
        for message in messages:
            print(f"DRY RUN: {message['From']} -> {message['To']} | {message['Subject']}")
        print(f"Prepared {len(messages)} due test messages. No email sent.")
        return

    if outbound_config.get("review_required_before_send", True):
        raise SystemExit("Config has review_required_before_send=true. Set it false only after reviewing the test.")

    try:
        send_messages(messages, outbound_config)
    except Exception as exc:
        for row in due_rows:
            row["last_error"] = f"{type(exc).__name__}: {exc}"
        write_state(rows)
        raise

    sent_at = now_utc().isoformat()
    due_steps = {row["step"] for row in due_rows}
    for row in rows:
        if row["step"] in due_steps:
            row["status"] = "sent"
            row["sent_at"] = sent_at
            row["last_error"] = ""
    write_state(rows)
    for message in messages:
        print(f"SENT: {message['To']} | {message['Subject']}")


if __name__ == "__main__":
    main()
