from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import re
from datetime import date
from pathlib import Path

from core.csv_store import read_csv, write_csv_atomic
from core.eligibility_rules import dedupe_keys, evaluate_prospect
from core.paths import data_dir, outreach_batches_dir


DATA_DIR = data_dir()
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"
BATCH_DIR = outreach_batches_dir()


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    write_csv_atomic(path, rows, headers)


def suppression_values() -> set[str]:
    rows = read_csv(SUPPRESSION_PATH) if SUPPRESSION_PATH.exists() else []
    values = set()
    for row in rows:
        for key in ("email", "domain", "company_name"):
            value = row.get(key, "").strip().lower()
            if value:
                values.add(value)
    return values


def email_matches_name(row: dict[str, str]) -> bool:
    if row.get("email_type") == "generic":
        return True
    email = row.get("email", "")
    local_part = email.split("@", 1)[0].lower() if "@" in email else ""
    name_parts = [part.lower() for part in re.split(r"[^A-Za-z]+", row.get("decision_maker_name", "")) if part]
    return any(part in local_part for part in name_parts)


def eligible(row: dict[str, str], suppressed: set[str]) -> bool:
    if row.get("campaign_status") not in {"ready_for_draft", "selected_for_review"}:
        return False
    if not row.get("email"):
        return False
    if row.get("reply_status") in {"not_interested", "do_not_contact"}:
        return False
    if row.get("bounce_status") in {"hard_bounce", "bounced"}:
        return False
    if row.get("eligibility_status") and row.get("eligibility_status") != "eligible":
        return False
    result = evaluate_prospect(row, suppressed_values=suppressed, max_sequence_steps=int(row.get("max_follow_ups") or 3))
    if not result["eligible"]:
        return False
    if row.get("tier") == "tier_1_named_dm_email" and not email_matches_name(row):
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a reviewed outreach batch from campaign_queue.csv.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--tier", action="append", help="Tier to include. Can be repeated.")
    parser.add_argument("--per-domain-limit", type=int, default=1, help="Maximum rows per company domain in one batch.")
    parser.add_argument("--output", help="Optional output CSV path.")
    args = parser.parse_args()

    tiers = set(args.tier or ["tier_1_named_dm_email"])
    suppressed = suppression_values()
    rows = [row for row in read_csv(QUEUE_PATH) if row.get("tier") in tiers and eligible(row, suppressed)]
    batch_rows = []
    seen_emails = set()
    seen_company_domains = set()
    domain_counts: dict[str, int] = {}
    for row in rows:
        keys = dedupe_keys(row)
        domain = row.get("company_domain", "").strip().lower() or keys["domain"]
        if keys["email"] in seen_emails:
            continue
        if keys["company_domain"] and keys["company_domain"] in seen_company_domains:
            continue
        if domain and domain_counts.get(domain, 0) >= args.per_domain_limit:
            continue
        batch_rows.append(row)
        seen_emails.add(keys["email"])
        if keys["company_domain"]:
            seen_company_domains.add(keys["company_domain"])
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if len(batch_rows) >= args.limit:
            break

    BATCH_DIR.mkdir(exist_ok=True)
    output_path = Path(args.output) if args.output else BATCH_DIR / f"batch_{date.today().isoformat()}.csv"
    headers = [
        "lead_id",
        "icp_profile",
        "campaign_name",
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
        "eligibility_status",
        "eligibility_reasons",
    ]
    write_csv(output_path, [{header: row.get(header, "") for header in headers} for row in batch_rows], headers)
    print(f"Wrote {len(batch_rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
