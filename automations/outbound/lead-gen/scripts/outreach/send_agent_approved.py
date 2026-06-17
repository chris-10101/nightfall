from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from core.csv_store import read_csv, write_csv_atomic
from core.monitoring import init_sentry
from core.paths import data_dir, outreach_batches_dir
from outreach.send_outreach_smtp import APPROVED_AUTOMATION_STATUSES, validate_batch_rows, load_config


DATA_DIR = data_dir()
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
BATCH_DIR = outreach_batches_dir()

SEND_BATCH_HEADERS = [
    "lead_id",
    "icp_profile",
    "campaign_name",
    "campaign_variant",
    "company_name",
    "company_domain",
    "segment",
    "city_region",
    "decision_maker_name",
    "email",
    "email_type",
    "email_confidence",
    "email_source_url",
    "email_acquisition_method",
    "evidence_url",
    "subject",
    "draft_body",
    "tier",
    "fit_score",
    "campaign_status",
    "reply_status",
    "bounce_status",
    "send_count",
    "follow_up_count",
    "max_follow_ups",
    "next_action_due_at",
    "eligibility_status",
    "eligibility_reasons",
]


def approved_rows(limit: int) -> list[dict[str, str]]:
    config = load_config()
    queue_rows = read_csv(QUEUE_PATH)
    rows = [
        row
        for row in queue_rows
        if (row.get("campaign_status") or "").strip().lower() in APPROVED_AUTOMATION_STATUSES
    ]
    rows = rows[:limit]
    if not rows:
        return []
    return validate_batch_rows(config, rows, queue_rows)


def write_batch(rows: list[dict[str, str]]) -> Path:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BATCH_DIR / f"agent_approved_{stamp}.csv"
    write_csv_atomic(path, [{header: row.get(header, "") for header in SEND_BATCH_HEADERS} for row in rows], SEND_BATCH_HEADERS)
    return path


def main() -> None:
    init_sentry("send-agent-approved")
    parser = argparse.ArgumentParser(description="Send rows explicitly approved for Vesra agent automation.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--send", action="store_true", help="Actually send. Omit for dry-run.")
    args = parser.parse_args()

    if args.send and os.environ.get("VESRA_AUTO_SEND_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        print("Approved auto-send is disabled. Set VESRA_AUTO_SEND_ENABLED=true to allow sending approved rows.")
        return

    rows = approved_rows(args.limit)
    if not rows:
        print("No approved rows to send.")
        return
    batch_path = write_batch(rows)
    command = [
        sys.executable,
        "lead-gen/scripts/outreach/send_outreach_smtp.py",
        str(batch_path),
        "--allow-approved-automation",
    ]
    if args.send:
        command.append("--send")
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], text=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
