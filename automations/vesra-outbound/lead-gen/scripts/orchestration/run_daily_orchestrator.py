from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.csv_store import read_csv, write_csv_atomic
from core.eligibility_rules import (
    dedupe_keys,
    evaluate_prospect,
    sequence_count,
    stop_on_reply_or_bounce_reasons,
)
from core.icp_profiles import is_active_segment, profile_for_row
from core.monitoring import init_sentry
from core.paths import data_dir, orchestration_dir
from imports.import_hr_consultancies import HEADERS as PROSPECT_HEADERS
from outreach.build_campaign_queue import QUEUE_HEADERS, build_queue_rows


UK_TZ = ZoneInfo("Europe/London")
DATA_DIR = data_dir()
ORCHESTRATION_DIR = orchestration_dir()
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"

LIFECYCLE_FIELDS = [
    "lifecycle_state",
    "agent_next_action",
    "agent_next_action_at",
    "agent_last_decision_at",
    "agent_last_decision",
    "agent_blocked_reason",
    "agent_requires_review",
    "agent_owner",
    "campaign_step",
    "campaign_step_due_at",
    "last_agent_run_id",
]

READY_QUEUE_STATUSES = {"ready_for_draft", "selected_for_review"}
SENT_QUEUE_STATUSES = {"sent"}
STOP_QUEUE_STATUSES = {"stopped", "suppressed", "unsubscribed", "bounced", "failed"}


def now_uk() -> datetime:
    return datetime.now(UK_TZ)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def next_workday_at(hour: int, minute: int, *, current: datetime | None = None) -> datetime:
    candidate = (current or now_uk()).astimezone(UK_TZ)
    candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= (current or now_uk()).astimezone(UK_TZ):
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def parse_dt(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(UK_TZ)


def int_value(value: str, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def read_suppression_values() -> set[str]:
    values = set()
    for row in read_csv(SUPPRESSION_PATH):
        for key in ("email", "domain", "company_name"):
            value = row.get(key, "").strip().lower()
            if value:
                values.add(value)
        keys = dedupe_keys(row)
        values.update(key for key in keys.values() if key)
    return values


def ensure_fields(rows: list[dict[str, str]], headers: list[str]) -> list[str]:
    ordered = list(headers)
    for field in LIFECYCLE_FIELDS:
        if field not in ordered:
            ordered.append(field)
    for row in rows:
        for field in ordered:
            row.setdefault(field, "")
    return ordered


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def sync_queue_from_prospects(queue_rows: list[dict[str, str]], decisions_by_lead_id: dict[str, dict[str, str]]) -> None:
    headers = ensure_fields(queue_rows, QUEUE_HEADERS)
    for row in queue_rows:
        decision = decisions_by_lead_id.get(row.get("lead_id", ""))
        if not decision:
            continue
        for field in LIFECYCLE_FIELDS:
            row[field] = decision.get(field, row.get(field, ""))
    write_csv_atomic(QUEUE_PATH, queue_rows, headers)


def queue_by_lead_id() -> dict[str, dict[str, str]]:
    return {row.get("lead_id", ""): row for row in read_csv(QUEUE_PATH) if row.get("lead_id")}


def suppression_match(row: dict[str, str], suppressed_values: set[str]) -> bool:
    keys = dedupe_keys(row)
    return any(key and key in suppressed_values for key in keys.values())


def decision(
    prospect: dict[str, str],
    queue_row: dict[str, str] | None,
    suppressed_values: set[str],
    run_id: str,
    decision_at: str,
) -> dict[str, str]:
    combined = dict(prospect)
    if queue_row:
        combined.update({key: value for key, value in queue_row.items() if value})

    stop_reasons = stop_on_reply_or_bounce_reasons(combined)
    if suppression_match(combined, suppressed_values):
        return state("stopped", "none", decision_at, "Suppressed contact/company/domain.", "suppressed", "false", run_id)
    if stop_reasons:
        return state("stopped", "none", decision_at, "Stop condition: " + ", ".join(stop_reasons), "stopped", "false", run_id)

    status = (combined.get("status") or "").strip().lower()
    if status in {"do_not_contact", "not_fit", "suppressed", "unsubscribed"}:
        return state("stopped", "none", decision_at, f"Blocked prospect status: {status}.", "blocked_status", "false", run_id)

    if not is_active_segment(combined.get("segment", "")):
        return state("disqualified", "none", decision_at, "Inactive ICP segment.", "inactive_segment", "false", run_id)

    profile_key, _ = profile_for_row(combined)
    if not profile_key:
        return state("needs_review", "review_icp_fit", decision_at, "Could not map row to active ICP profile.", "missing_icp_profile", "true", run_id)

    if not combined.get("website_url") and not combined.get("email"):
        return state("research_needed", "discover_or_enrich_contact", decision_at, "Missing website and email.", "missing_contact_routes", "false", run_id)

    if not combined.get("email"):
        if combined.get("website_url"):
            return state("enrichment_needed", "enrich_public_email", decision_at, "Website exists but email is missing.", "missing_email", "false", run_id)
        return state("research_needed", "discover_contact_email", decision_at, "Email is missing.", "missing_email", "false", run_id)

    eligibility = evaluate_prospect(combined, suppressed_values=suppressed_values)
    if not eligibility["eligible"]:
        blocked_codes = [
            item["code"]
            for item in eligibility["reasons"]
            if item.get("severity") == "block"
        ]
        review = "true" if any(code in {"missing_icp_required_signal", "missing_public_evidence"} for code in blocked_codes) else "false"
        action = "review_data_quality" if review == "true" else "none"
        return state(
            "blocked",
            action,
            decision_at,
            "Eligibility blocked: " + ", ".join(blocked_codes),
            ",".join(blocked_codes),
            review,
            run_id,
        )

    if not queue_row:
        return state(
            "qualified",
            "await_queue_selection",
            decision_at,
            "Eligible but not selected into the current deduped campaign queue.",
            "",
            "false",
            run_id,
        )

    campaign_status = (queue_row.get("campaign_status") or "").strip().lower()
    if campaign_status in STOP_QUEUE_STATUSES:
        return state("stopped", "none", decision_at, f"Queue status is {campaign_status}.", campaign_status, "false", run_id)
    if campaign_status in READY_QUEUE_STATUSES:
        return state("ready_for_review", "review_campaign_copy", decision_at, "Campaign copy is ready for human review.", "", "true", run_id)
    if campaign_status in SENT_QUEUE_STATUSES:
        next_due = parse_dt(queue_row.get("next_action_due_at") or queue_row.get("follow_up_at", ""))
        count = sequence_count(queue_row)
        max_follow_ups = int_value(queue_row.get("max_follow_ups"), 3)
        if count >= max_follow_ups:
            return state("completed", "none", decision_at, "Campaign sequence cap reached.", "sequence_cap_reached", "false", run_id)
        if next_due and now_uk() >= next_due:
            return state("follow_up_due", "prepare_follow_up_review", decision_at, "Follow-up is due.", "", "true", run_id, next_due)
        due = next_due or next_workday_at(10, 0)
        return state("waiting_follow_up", "wait_until_due", decision_at, "Waiting for follow-up due date.", "", "false", run_id, due)

    return state("needs_review", "review_campaign_status", decision_at, f"Unhandled queue status: {campaign_status or 'blank'}.", "unknown_campaign_status", "true", run_id)


def state(
    lifecycle_state: str,
    next_action: str,
    decision_at: str,
    last_decision: str,
    blocked_reason: str,
    requires_review: str,
    run_id: str,
    next_action_at: datetime | None = None,
) -> dict[str, str]:
    return {
        "lifecycle_state": lifecycle_state,
        "agent_next_action": next_action,
        "agent_next_action_at": iso(next_action_at) if next_action_at else "",
        "agent_last_decision_at": decision_at,
        "agent_last_decision": last_decision,
        "agent_blocked_reason": blocked_reason,
        "agent_requires_review": requires_review,
        "agent_owner": "vesra-daily-orchestrator",
        "campaign_step": "",
        "campaign_step_due_at": iso(next_action_at) if next_action_at else "",
        "last_agent_run_id": run_id,
    }


def run(rebuild_queue: bool) -> dict:
    init_sentry("daily-orchestrator")
    current = now_uk()
    run_id = current.strftime("%Y%m%dT%H%M%S%z")
    decision_at = iso(current)

    if rebuild_queue:
        queue_rows = build_queue_rows()
        write_csv_atomic(QUEUE_PATH, queue_rows, ensure_fields(queue_rows, QUEUE_HEADERS))

    prospects = read_csv(PROSPECTS_PATH)
    prospect_headers = ensure_fields(prospects, PROSPECT_HEADERS)
    queue_rows = read_csv(QUEUE_PATH)
    queue_headers = ensure_fields(queue_rows, QUEUE_HEADERS)
    queue_lookup = {row.get("lead_id", ""): row for row in queue_rows if row.get("lead_id")}
    suppressed_values = read_suppression_values()

    decisions_by_lead_id: dict[str, dict[str, str]] = {}
    samples = []
    for prospect in prospects:
        lead_id = prospect.get("lead_id", "")
        result = decision(prospect, queue_lookup.get(lead_id), suppressed_values, run_id, decision_at)
        decisions_by_lead_id[lead_id] = result
        for field, value in result.items():
            prospect[field] = value
        if len(samples) < 25:
            samples.append(
                {
                    "lead_id": lead_id,
                    "company_name": prospect.get("company_name", ""),
                    "lifecycle_state": result["lifecycle_state"],
                    "agent_next_action": result["agent_next_action"],
                    "agent_blocked_reason": result["agent_blocked_reason"],
                    "agent_requires_review": result["agent_requires_review"],
                }
            )

    for row in queue_rows:
        result = decisions_by_lead_id.get(row.get("lead_id", ""))
        if not result:
            continue
        for field, value in result.items():
            row[field] = value

    write_csv_atomic(PROSPECTS_PATH, prospects, prospect_headers)
    write_csv_atomic(QUEUE_PATH, queue_rows, queue_headers)

    state_counts = Counter(row.get("lifecycle_state", "") for row in prospects)
    action_counts = Counter(row.get("agent_next_action", "") for row in prospects)
    review_count = sum(1 for row in prospects if row.get("agent_requires_review") == "true")
    summary = {
        "run_id": run_id,
        "ran_at": decision_at,
        "rebuild_queue": rebuild_queue,
        "prospects": len(prospects),
        "queue_rows": len(queue_rows),
        "requires_review": review_count,
        "state_counts": dict(sorted(state_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "samples": samples,
    }
    write_json(ORCHESTRATION_DIR / f"orchestrator_{run_id}.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vesra contact lifecycle orchestration.")
    parser.add_argument("--rebuild-queue", action="store_true", help="Rebuild campaign_queue.csv before deciding contact states.")
    parser.add_argument("--summary", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    summary = run(rebuild_queue=args.rebuild_queue)
    if args.summary:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print(
        f"Orchestrated {summary['prospects']} prospects; "
        f"queue_rows={summary['queue_rows']}; requires_review={summary['requires_review']}"
    )


if __name__ == "__main__":
    main()
