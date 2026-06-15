from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import os
import smtplib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from core.csv_store import read_csv
from core.icp_profiles import active_profiles, profile_for_row
from core.monitoring import init_sentry
from core.paths import config_dir, data_dir, outreach_batches_dir, reports_dir


CONFIG_DIR = config_dir()
DATA_DIR = data_dir()
REPORT_DIR = reports_dir()
OUTREACH_BATCH_DIR = outreach_batches_dir()
CONFIG_PATH = CONFIG_DIR / "outbound_config.json"
CONFIG_EXAMPLE_PATH = CONFIG_DIR / "outbound_config.example.json"
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"
DEFAULT_RECIPIENT = "chris@vesra.io"
UK_TZ = ZoneInfo("Europe/London")
READY_STATUSES = {"ready_for_draft", "selected_for_review"}
STOP_REPLY_STATUSES = {"replied", "positive", "interested", "not_interested", "do_not_contact", "out_of_office"}
BOUNCE_STATUSES = {"bounce", "bounced", "hard_bounce", "soft_bounce"}


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    with path.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def local_now() -> datetime:
    return datetime.now(UK_TZ)


def sunday_for(value: date) -> date:
    return value - timedelta(days=(value.weekday() + 1) % 7)


def parse_week_start(value: str | None, today: date | None = None) -> date:
    if value:
        parsed = date.fromisoformat(value)
    else:
        parsed = sunday_for(today or local_now().date())
    if parsed.weekday() != 6:
        raise SystemExit("--week-start must be a Sunday date in YYYY-MM-DD format.")
    return parsed


def friday_for_week(week_start: date) -> date:
    return week_start + timedelta(days=5)


def iso_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def iso_datetime_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return iso_date(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(UK_TZ).date()


def within_dates(value: str, start: date, end: date, *, datetime_value: bool = False) -> bool:
    parsed = iso_datetime_date(value) if datetime_value else iso_date(value)
    return bool(parsed and start <= parsed <= end)


def int_value(value: str) -> int:
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0


def profile_key_for_prospect(row: dict[str, str]) -> str:
    key, _ = profile_for_row(row)
    return key or "unknown"


def queue_profile_key(row: dict[str, str]) -> str:
    return row.get("icp_profile") or profile_key_for_prospect(row)


def status_count(rows: list[dict[str, str]], field: str) -> Counter:
    values = [row.get(field, "").strip() or "(blank)" for row in rows]
    return Counter(values)


def batch_files_in_week(week_start: date, week_end: date) -> list[Path]:
    if not OUTREACH_BATCH_DIR.exists():
        return []
    files: list[Path] = []
    for path in sorted(OUTREACH_BATCH_DIR.glob("batch_*.csv")):
        batch_date = iso_date(path.stem.replace("batch_", ""))
        if batch_date and week_start <= batch_date <= week_end:
            files.append(path)
    return files


def batch_row_count(path: Path) -> int:
    return len(read_csv(path))


def collect_metrics(week_start: date, week_end: date) -> dict:
    config = load_config()
    prospects = read_csv(PROSPECTS_PATH)
    queue = read_csv(QUEUE_PATH)
    suppression = read_csv(SUPPRESSION_PATH)
    profiles = active_profiles()

    prospects_by_profile = Counter(profile_key_for_prospect(row) for row in prospects)
    email_prospects_by_profile = Counter(
        profile_key_for_prospect(row) for row in prospects if row.get("email", "").strip()
    )
    queue_by_profile = Counter(queue_profile_key(row) for row in queue)
    ready_by_profile = Counter(
        queue_profile_key(row) for row in queue if is_ready_for_outbound(row)
    )
    sent_by_profile = Counter(
        queue_profile_key(row) for row in queue if int_value(row.get("send_count", "")) > 0
    )
    sent_this_week_by_profile = Counter(
        queue_profile_key(row)
        for row in queue
        if within_dates(row.get("last_outbound_at", ""), week_start, week_end, datetime_value=True)
    )
    replies_this_week_by_profile = Counter(
        queue_profile_key(row)
        for row in queue
        if within_dates(row.get("last_reply_at", ""), week_start, week_end, datetime_value=True)
    )

    batch_files = batch_files_in_week(week_start, week_end)
    return {
        "config": config,
        "profiles": profiles,
        "prospects": prospects,
        "queue": queue,
        "suppression": suppression,
        "prospects_by_profile": prospects_by_profile,
        "email_prospects_by_profile": email_prospects_by_profile,
        "queue_by_profile": queue_by_profile,
        "ready_by_profile": ready_by_profile,
        "sent_by_profile": sent_by_profile,
        "sent_this_week_by_profile": sent_this_week_by_profile,
        "replies_this_week_by_profile": replies_this_week_by_profile,
        "new_prospects_this_week": [
            row for row in prospects if within_dates(row.get("last_researched_at", ""), week_start, week_end)
        ],
        "sent_this_week": [
            row
            for row in queue
            if within_dates(row.get("last_outbound_at", ""), week_start, week_end, datetime_value=True)
        ],
        "replies_this_week": [
            row
            for row in queue
            if within_dates(row.get("last_reply_at", ""), week_start, week_end, datetime_value=True)
        ],
        "bounces_this_week": [
            row
            for row in queue
            if within_dates(row.get("last_bounce_at", ""), week_start, week_end, datetime_value=True)
        ],
        "suppressions_this_week": [
            row for row in suppression if within_dates(row.get("added_at", ""), week_start, week_end)
        ],
        "batch_files": batch_files,
        "batch_rows_this_week": sum(batch_row_count(path) for path in batch_files),
        "queue_status_counts": status_count(queue, "campaign_status"),
        "reply_status_counts": status_count(queue, "reply_status"),
        "bounce_status_counts": status_count(queue, "bounce_status"),
    }


def is_ready_for_outbound(row: dict[str, str]) -> bool:
    if row.get("campaign_status", "").strip() not in READY_STATUSES:
        return False
    if row.get("eligibility_status") and row.get("eligibility_status") != "eligible":
        return False
    if row.get("reply_status", "").strip().lower() in STOP_REPLY_STATUSES:
        return False
    if row.get("bounce_status", "").strip().lower() in BOUNCE_STATUSES:
        return False
    return bool(row.get("email", "").strip())


def discovery_targets(metrics: dict) -> dict[str, int]:
    profiles = metrics["profiles"]
    remaining = {
        key: max(int_value(profile.get("target_count", "")) - metrics["prospects_by_profile"].get(key, 0), 0)
        for key, profile in profiles.items()
    }
    total_remaining = sum(remaining.values())
    weekly_discovery_goal = 100
    if total_remaining <= 0:
        return {key: 0 for key in profiles}
    targets: dict[str, int] = {}
    for key in profiles:
        share = remaining[key] / total_remaining if total_remaining else 0
        targets[key] = min(remaining[key], round(weekly_discovery_goal * share))
    if sum(targets.values()) == 0 and profiles:
        key = max(remaining, key=remaining.get)
        targets[key] = min(remaining[key], weekly_discovery_goal)
    return targets


def weekly_send_target(metrics: dict) -> int:
    daily_limit = int_value(metrics["config"].get("daily_send_limit", 20))
    daily_review_limit = min(daily_limit, 10)
    ready_count = sum(1 for row in metrics["queue"] if is_ready_for_outbound(row))
    return min(ready_count, daily_review_limit * 5)


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def generate_plan_markdown(week_start: date) -> str:
    week_end = friday_for_week(week_start)
    metrics = collect_metrics(week_start, week_end)
    config = metrics["config"]
    targets = discovery_targets(metrics)
    send_target = weekly_send_target(metrics)
    generated_at = local_now().strftime("%Y-%m-%d %H:%M %Z")
    daily_limit = int_value(config.get("daily_send_limit", 20))
    daily_review_limit = min(daily_limit, 10)

    summary_rows = [
        ["Prospects", len(metrics["prospects"])],
        ["Email-backed prospects", sum(1 for row in metrics["prospects"] if row.get("email", "").strip())],
        ["Queued contacts", len(metrics["queue"])],
        ["Ready queue", sum(1 for row in metrics["queue"] if is_ready_for_outbound(row))],
        ["Suppression entries", len(metrics["suppression"])],
        ["Daily send limit", daily_limit],
        ["Per-domain daily limit", config.get("per_domain_daily_limit", 1)],
        ["Recommended weekly send target", send_target],
    ]
    profile_rows = []
    for key, profile in metrics["profiles"].items():
        prospect_count = metrics["prospects_by_profile"].get(key, 0)
        target_count = int_value(profile.get("target_count", ""))
        profile_rows.append(
            [
                profile.get("label", key),
                target_count,
                prospect_count,
                metrics["email_prospects_by_profile"].get(key, 0),
                metrics["ready_by_profile"].get(key, 0),
                metrics["sent_by_profile"].get(key, 0),
                max(target_count - prospect_count, 0),
                targets.get(key, 0),
            ]
        )

    plan = [
        "# Vesra Weekly Lead-Gen Plan",
        "",
        f"Week: Sunday {week_start.isoformat()} to Friday {week_end.isoformat()}",
        f"Generated: {generated_at}",
        "",
        "## Summary",
        "",
        markdown_table(["Metric", "Value"], summary_rows),
        "",
        "## ICP Focus",
        "",
        markdown_table(
            [
                "ICP",
                "Target",
                "Prospects",
                "Email-backed",
                "Ready queue",
                "Sent total",
                "Gap",
                "Discovery target",
            ],
            profile_rows,
        ),
        "",
        "## Weekly Targets",
        "",
        f"- Discovery: add up to {sum(targets.values())} email-backed ICP-fit prospects.",
        f"- Enrichment: run decision-maker and public-web enrichment before queue builds.",
        f"- Queue: rebuild after enrichment and keep at least {daily_review_limit * 5} reviewed candidates available.",
        f"- Outreach: prepare and review up to {daily_review_limit} contacts per weekday, capped by SMTP safety gates.",
        "- Monitoring: check replies, bounces, unsubscribes, and suppression before any follow-up work.",
        "",
        "## Daily Plan",
        "",
        daily_plan_markdown(week_start, daily_review_limit),
        "",
        "## Commands",
        "",
        "```bash",
        "python lead-gen/scripts/discovery/discover_email_backed_icp.py --max-new 20 --checkpoint",
        "python lead-gen/scripts/enrichment/enrich_decision_makers.py",
        "python lead-gen/scripts/enrichment/enrich_public_web.py --limit 25 --max-pages 2 --only-missing-email",
        "python lead-gen/scripts/outreach/build_campaign_queue.py",
        f"python lead-gen/scripts/outreach/prepare_outreach_batch.py --limit {daily_review_limit}",
        "python lead-gen/scripts/outreach/send_outreach_smtp.py lead-gen/outreach/batches/batch_YYYY-MM-DD.csv",
        "```",
        "",
    ]
    return "\n".join(plan)


def daily_plan_markdown(week_start: date, daily_review_limit: int) -> str:
    rows = []
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for offset, label in enumerate(labels, start=1):
        day = week_start + timedelta(days=offset)
        if label == "Monday":
            focus = "Discovery, enrichment, queue rebuild, first reviewed batch."
        elif label in {"Tuesday", "Wednesday", "Thursday"}:
            focus = "Discovery top-up, enrichment, reviewed batch, reply monitoring."
        else:
            focus = "Final reviewed batch, weekly report, blockers for next week."
        rows.append([label, day.isoformat(), focus, f"Prepare up to {daily_review_limit}"])
    return markdown_table(["Day", "Date", "Focus", "Batch target"], rows)


def generate_report_markdown(week_start: date) -> str:
    week_end = friday_for_week(week_start)
    metrics = collect_metrics(week_start, week_end)
    generated_at = local_now().strftime("%Y-%m-%d %H:%M %Z")
    sent_count = len(metrics["sent_this_week"])
    reply_count = len(metrics["replies_this_week"])
    bounce_count = len(metrics["bounces_this_week"])
    reply_rate = f"{(reply_count / sent_count * 100):.1f}%" if sent_count else "0.0%"
    bounce_rate = f"{(bounce_count / sent_count * 100):.1f}%" if sent_count else "0.0%"

    scorecard_rows = [
        ["New prospects researched", len(metrics["new_prospects_this_week"])],
        ["Batch rows prepared", metrics["batch_rows_this_week"]],
        ["Emails sent", sent_count],
        ["Replies logged", reply_count],
        ["Reply rate", reply_rate],
        ["Bounces logged", bounce_count],
        ["Bounce rate", bounce_rate],
        ["New suppressions", len(metrics["suppressions_this_week"])],
        ["Ready queue remaining", sum(1 for row in metrics["queue"] if is_ready_for_outbound(row))],
    ]
    profile_rows = []
    for key, profile in metrics["profiles"].items():
        profile_rows.append(
            [
                profile.get("label", key),
                metrics["prospects_by_profile"].get(key, 0),
                metrics["queue_by_profile"].get(key, 0),
                metrics["ready_by_profile"].get(key, 0),
                metrics["sent_this_week_by_profile"].get(key, 0),
                metrics["replies_this_week_by_profile"].get(key, 0),
            ]
        )

    batch_rows = [[path.name, batch_row_count(path)] for path in metrics["batch_files"]]
    if not batch_rows:
        batch_rows = [["No batch files dated in this reporting window", 0]]

    report = [
        "# Vesra Weekly Lead-Gen Report",
        "",
        f"Week: Sunday {week_start.isoformat()} to Friday {week_end.isoformat()}",
        f"Generated: {generated_at}",
        "",
        "## Scorecard",
        "",
        markdown_table(["Metric", "Value"], scorecard_rows),
        "",
        "## ICP Performance",
        "",
        markdown_table(
            ["ICP", "Prospects", "Queued", "Ready queue", "Sent this week", "Replies this week"],
            profile_rows,
        ),
        "",
        "## Batch Activity",
        "",
        markdown_table(["Batch file", "Rows"], batch_rows),
        "",
        "## Queue Status",
        "",
        markdown_table(["Campaign status", "Rows"], counter_rows(metrics["queue_status_counts"])),
        "",
        "## Reply Status",
        "",
        markdown_table(["Reply status", "Rows"], counter_rows(metrics["reply_status_counts"])),
        "",
        "## Next Actions",
        "",
        *next_actions(metrics),
        "",
    ]
    return "\n".join(report)


def counter_rows(counter: Counter) -> list[list[object]]:
    rows = [[key, value] for key, value in counter.most_common()]
    return rows or [["No rows", 0]]


def next_actions(metrics: dict) -> list[str]:
    actions = []
    ready_count = sum(1 for row in metrics["queue"] if is_ready_for_outbound(row))
    daily_limit = int_value(metrics["config"].get("daily_send_limit", 20))
    weekly_review_target = min(daily_limit, 10) * 5
    if ready_count < weekly_review_target:
        actions.append(
            f"- Replenish the ready queue: {ready_count} contacts are ready against a {weekly_review_target} weekly review target."
        )
    if metrics["bounces_this_week"]:
        actions.append("- Review bounced contacts and add confirmed bad domains or addresses to suppression.")
    if not metrics["replies_this_week"]:
        actions.append("- Confirm reply monitoring is working before scheduling follow-up sends.")
    if not metrics["batch_files"]:
        actions.append("- Prepare reviewed outreach batches before any live sends next week.")
    if not actions:
        actions.append("- Keep the daily discovery, enrichment, queue, review, send, and monitoring loop running.")
    return actions


def default_output_path(kind: str, week_start: date) -> Path:
    suffix_date = week_start if kind == "plan" else friday_for_week(week_start)
    return REPORT_DIR / f"weekly_{kind}_{suffix_date.isoformat()}.md"


def write_markdown(markdown: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def send_email(config: dict, recipient: str, subject: str, markdown: str) -> None:
    smtp_config = config.get("smtp") or {}
    username_env = smtp_config.get("username_env")
    password_env = smtp_config.get("password_env")
    username = os.environ.get(username_env or "")
    password = os.environ.get(password_env or "")
    if not smtp_config.get("host") or not smtp_config.get("port"):
        raise SystemExit("SMTP config is missing host or port.")
    if not username or not password:
        raise SystemExit(f"Missing SMTP credentials. Set {username_env} and {password_env}.")

    message = EmailMessage()
    sender_name = config.get("sender_name", "Vesra")
    from_email = config.get("from_email", DEFAULT_RECIPIENT)
    message["From"] = f"{sender_name} <{from_email}>"
    message["To"] = recipient
    message["Subject"] = subject
    if config.get("reply_to"):
        message["Reply-To"] = config["reply_to"]
    message.set_content(markdown)

    port = int(smtp_config["port"])
    if port == 465:
        with smtplib.SMTP_SSL(smtp_config["host"], port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        return
    with smtplib.SMTP(smtp_config["host"], port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def save_and_optionally_send(
    *,
    kind: str,
    markdown: str,
    output: str | None,
    week_start: date,
    send: bool,
    recipient: str,
    subject: str,
) -> Path:
    path = Path(output) if output else default_output_path(kind, week_start)
    write_markdown(markdown, path)
    if send:
        send_email(load_config(), recipient, subject, markdown)
        print(f"SENT: {recipient} | {subject}")
    else:
        print(f"DRY RUN: no email sent. Use --send to email {recipient}.")
    print(f"Wrote {path}")
    return path
