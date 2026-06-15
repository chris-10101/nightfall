from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from datetime import date
from pathlib import Path

from core.csv_store import read_csv, write_csv_atomic
from core.eligibility_rules import (
    company_key,
    dedupe_keys,
    email_domain,
    evaluate_prospect,
    website_domain,
)
from core.icp_profiles import campaign_name, is_active_segment, outreach_config, profile_for_row, profile_positive_score
from core.monitoring import init_sentry
from core.paths import data_dir


DATA_DIR = data_dir()
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
SUPPRESSION_PATH = DATA_DIR / "suppression.csv"
TODAY = date.today().isoformat()
CAMPAIGN_NAME = "vesra_partner_program_v1"
MAX_FOLLOW_UPS = "3"


QUEUE_HEADERS = [
    "lead_id",
    "icp_profile",
    "campaign_name",
    "company_name",
    "company_domain",
    "segment",
    "city_region",
    "decision_maker_name",
    "decision_maker_role",
    "email",
    "email_type",
    "email_confidence",
    "email_source_url",
    "email_acquisition_method",
    "website_url",
    "company_linkedin_url",
    "decision_maker_linkedin_url",
    "linkedin_source_url",
    "fit_score",
    "priority",
    "tier",
    "personalisation",
    "short_reason",
    "subject",
    "draft_body",
    "campaign_status",
    "gmail_draft_id",
    "gmail_message_id",
    "last_outbound_at",
    "last_reply_at",
    "reply_status",
    "bounce_status",
    "last_bounce_at",
    "send_count",
    "follow_up_count",
    "max_follow_ups",
    "next_action_due_at",
    "next_action",
    "source_url",
    "evidence_url",
    "eligibility_status",
    "eligibility_reasons",
    "suppression_checked_at",
]


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    write_csv_atomic(path, rows, headers)


def first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name else "there"


def suppression_values() -> set[str]:
    rows = read_csv(SUPPRESSION_PATH)
    values = set()
    for row in rows:
        for key in ("email", "domain", "company_name"):
            value = row.get(key, "").strip().lower()
            if value:
                values.add(value)
        normalized_company = company_key(row)
        if normalized_company:
            values.add(normalized_company)
    return values


def is_suppressed(row: dict[str, str], suppressed: set[str]) -> bool:
    email = row.get("email", "").strip().lower()
    company = row.get("company_name", "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""
    return email in suppressed or company in suppressed or domain in suppressed


def tier(row: dict[str, str]) -> str:
    has_name = bool(row.get("decision_maker_name"))
    has_named_email = row.get("email_type") == "named"
    has_email = bool(row.get("email"))
    has_linkedin = bool(row.get("decision_maker_linkedin_url") or row.get("company_linkedin_url"))
    if has_name and has_named_email:
        return "tier_1_named_dm_email"
    if has_name and has_email:
        return "tier_2_named_dm_generic_email"
    if has_email and has_linkedin:
        return "tier_3_company_contactable"
    if has_email:
        return "tier_4_email_only"
    return "exclude_missing_email"


def personalisation(row: dict[str, str]) -> tuple[str, str]:
    outreach = outreach_config(row)
    if outreach:
        detail = outreach.get("detail", "supports businesses in a way that looks relevant")
        reason = outreach.get("short_reason", "your advisory work")
        city = row.get("city_region", "").strip()
        subtype = row.get("subtype", "").strip()
        if city and city.lower() not in detail.lower():
            detail += f" around {city}"
        if subtype and subtype.lower() not in detail.lower():
            reason = subtype
        return detail, reason

    notes = row.get("notes", "").strip()
    subtype = row.get("subtype", "").strip()
    city = row.get("city_region", "").strip()
    segment = row.get("segment", "").strip().lower()

    if "sme" in notes.lower() or "small" in notes.lower():
        reason = "your work with SMEs"
        detail = "appears to support SMEs and owner-managed businesses"
    elif "outsourced" in notes.lower() or "retained" in notes.lower():
        reason = "your outsourced advisory work"
        detail = "offers outsourced or retained support to clients"
    elif "hr" in segment:
        reason = "your HR advisory work"
        detail = "works with businesses on HR and people support"
    elif "account" in segment:
        reason = "your advisory work with business clients"
        detail = "advises businesses on practical operational issues"
    elif "law" in segment:
        reason = "your employment law work"
        detail = "supports employers with employment and people issues"
    else:
        reason = "your advisory work"
        detail = "supports businesses in a way that looks relevant"

    if city:
        detail += f" around {city}"
    if subtype and subtype.lower() not in detail.lower():
        reason = subtype

    return detail, reason


def draft_body(row: dict[str, str], detail: str) -> str:
    outreach = outreach_config(row)
    name = first_name(row.get("decision_maker_name", ""))
    company = row["company_name"]
    if outreach.get("body_template"):
        return outreach["body_template"].format(
            first_name=name,
            company_name=company,
            detail=detail,
            city_region=row.get("city_region", ""),
        )
    return (
        f"Hi {name},\n\n"
        f"I came across {company} and noticed you provide HR support to SMEs.\n\n"
        "One thing we have heard repeatedly from HR consultancies is that clients increasingly expect a software platform alongside advice, policies, and support.\n\n"
        "Vesra helps HR consultancies offer a branded HR platform to clients without having to build or maintain software themselves.\n\n"
        "The result is stronger client retention, a more complete service offering, and an additional recurring revenue stream.\n\n"
        "Would it be worth sending over a short overview?\n\n"
        "If this is not relevant, reply unsubscribe and I will not contact you again.\n\n"
        "Best,\n"
        "Chris"
    )


def company_domain(row: dict[str, str]) -> str:
    return website_domain(row) or email_domain(row)


def evidence_url(row: dict[str, str]) -> str:
    return (
        row.get("email_source_url")
        or row.get("source_url")
        or row.get("website_url")
        or row.get("company_linkedin_url")
        or row.get("decision_maker_linkedin_url")
        or ""
    )


def email_acquisition_method(row: dict[str, str]) -> str:
    if row.get("email_source_url"):
        return "public_page"
    if row.get("source_url"):
        return "public_source"
    return ""


def eligibility_reason_codes(result: dict) -> str:
    codes = [
        reason["code"]
        for reason in result.get("reasons", [])
        if reason.get("severity") in {"block", "warn"}
    ]
    return ";".join(codes) if codes else "eligible"


def build_queue_rows() -> list[dict[str, str]]:
    prospects = read_csv(PROSPECTS_PATH)
    existing_queue = {row["lead_id"]: row for row in read_csv(QUEUE_PATH)}
    suppressed = suppression_values()

    candidates: list[dict[str, str]] = []
    for prospect in prospects:
        if not prospect.get("email"):
            continue
        if not is_active_segment(prospect.get("segment", "")):
            continue
        if "recruit" in prospect.get("subtype", "").lower():
            continue
        if prospect.get("status", "").lower() in {"do_not_contact", "not_fit"}:
            continue
        if is_suppressed(prospect, suppressed):
            continue

        prospect_tier = tier(prospect)
        if prospect_tier == "exclude_missing_email":
            continue

        detail, reason = personalisation(prospect)
        profile_key, _ = profile_for_row(prospect)
        existing = existing_queue.get(prospect["lead_id"], {})
        row = {header: "" for header in QUEUE_HEADERS}
        row.update(
            {
                "lead_id": prospect["lead_id"],
                "icp_profile": profile_key,
                "campaign_name": campaign_name(prospect, CAMPAIGN_NAME),
                "company_name": prospect["company_name"],
                "company_domain": company_domain(prospect),
                "segment": prospect["segment"],
                "city_region": prospect["city_region"],
                "decision_maker_name": prospect["decision_maker_name"],
                "decision_maker_role": prospect["decision_maker_role"],
                "email": prospect["email"],
                "email_type": prospect["email_type"],
                "email_confidence": prospect.get("email_confidence", ""),
                "email_source_url": prospect.get("email_source_url", ""),
                "email_acquisition_method": email_acquisition_method(prospect),
                "website_url": prospect["website_url"],
                "company_linkedin_url": prospect["company_linkedin_url"],
                "decision_maker_linkedin_url": prospect["decision_maker_linkedin_url"],
                "linkedin_source_url": prospect.get("linkedin_source_url", ""),
                "fit_score": prospect["fit_score"] or str(min(100, 60 + profile_positive_score(prospect))),
                "priority": prospect["priority"],
                "tier": prospect_tier,
                "personalisation": detail,
                "short_reason": reason,
                "subject": outreach_config(prospect).get("subject", "Quick question"),
                "draft_body": draft_body(prospect, detail),
                "campaign_status": existing.get("campaign_status") or "ready_for_draft",
                "gmail_draft_id": existing.get("gmail_draft_id", ""),
                "gmail_message_id": existing.get("gmail_message_id", ""),
                "last_outbound_at": existing.get("last_outbound_at", ""),
                "last_reply_at": existing.get("last_reply_at", ""),
                "reply_status": existing.get("reply_status", ""),
                "bounce_status": existing.get("bounce_status", ""),
                "last_bounce_at": existing.get("last_bounce_at", ""),
                "send_count": existing.get("send_count", "0"),
                "follow_up_count": existing.get("follow_up_count", "0"),
                "max_follow_ups": existing.get("max_follow_ups", MAX_FOLLOW_UPS),
                "next_action_due_at": existing.get("next_action_due_at", ""),
                "next_action": existing.get("next_action", "create_draft"),
                "source_url": prospect.get("source_url") or prospect.get("email_source_url") or prospect.get("website_url", ""),
                "evidence_url": evidence_url(prospect),
                "suppression_checked_at": TODAY,
            }
        )
        candidates.append(row)

    order = {
        "tier_1_named_dm_email": 0,
        "tier_2_named_dm_generic_email": 1,
        "tier_3_company_contactable": 2,
        "tier_4_email_only": 3,
    }
    candidates.sort(key=lambda row: (order.get(row["tier"], 99), -(int(row["fit_score"] or 0)), row["company_name"].lower()))

    rows: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    seen_domains: set[str] = set()
    seen_companies: set[str] = set()
    seen_company_domains: set[str] = set()
    for row in candidates:
        keys = dedupe_keys(row)
        domain = row.get("company_domain", "").lower()
        if domain and domain in seen_domains:
            continue
        if keys["company"] and keys["company"] in seen_companies:
            continue
        result = evaluate_prospect(
            row,
            suppressed_values=suppressed,
            seen_email_keys=seen_emails,
            seen_company_domain_keys=seen_company_domains,
            seen_company_keys=seen_companies,
            max_sequence_steps=int(row.get("max_follow_ups") or MAX_FOLLOW_UPS),
        )
        row["eligibility_status"] = "eligible" if result["eligible"] else "blocked"
        row["eligibility_reasons"] = eligibility_reason_codes(result)
        if not result["eligible"]:
            continue
        seen_emails.add(keys["email"])
        if domain:
            seen_domains.add(domain)
        if keys["company"]:
            seen_companies.add(keys["company"])
        if keys["company_domain"]:
            seen_company_domains.add(keys["company_domain"])
        rows.append(row)

    return rows


def main() -> None:
    init_sentry("build-campaign-queue")
    parser = argparse.ArgumentParser(description="Build campaign_queue.csv from eligible prospects.")
    parser.add_argument("--dry-run", action="store_true", help="Print the row count without writing campaign_queue.csv.")
    args = parser.parse_args()

    rows = build_queue_rows()
    if args.dry_run:
        print(f"DRY RUN: would write {len(rows)} queued contacts to {QUEUE_PATH}")
        return

    write_csv(QUEUE_PATH, rows, QUEUE_HEADERS)

    if not SUPPRESSION_PATH.exists():
        write_csv(SUPPRESSION_PATH, [], ["email", "domain", "company_name", "reason", "added_at"])

    print(f"Wrote {len(rows)} queued contacts to {QUEUE_PATH}")
    print(f"Generated on {TODAY}")


if __name__ == "__main__":
    main()
