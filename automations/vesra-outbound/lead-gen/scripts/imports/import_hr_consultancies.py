from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from pathlib import Path

import openpyxl


SOURCE_PATH = Path("/Users/chrissmith/Desktop/HR Consultancies Prospect List.xlsx")
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"

HEADERS = [
    "lead_id",
    "company_name",
    "segment",
    "subtype",
    "address",
    "city_region",
    "postcode",
    "distance_from_york_miles",
    "estimated_headcount",
    "headcount_source_url",
    "phone",
    "rating",
    "reviews",
    "website_url",
    "company_linkedin_url",
    "decision_maker_name",
    "decision_maker_role",
    "decision_maker_linkedin_url",
    "email",
    "email_type",
    "email_confidence",
    "email_source_url",
    "linkedin_source_url",
    "fit_score",
    "priority",
    "status",
    "source",
    "source_url",
    "notes",
    "last_researched_at",
    "contacted_at",
    "follow_up_at",
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
    "planned_tool",
    "planned_tool_args",
    "planned_reason",
    "tool_status",
    "tool_result_summary",
]

POSTCODE_RE = re.compile(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$", re.I)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def value(row: tuple, index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def main() -> None:
    workbook = openpyxl.load_workbook(SOURCE_PATH, read_only=True, data_only=True)
    sheet = workbook["HR Consultancies"]

    rows = []
    id_counts = {}

    for row in sheet.iter_rows(min_row=2, values_only=True):
        company_name = value(row, 1)
        if not company_name:
            continue

        base_id = slugify(company_name)
        id_counts[base_id] = id_counts.get(base_id, 0) + 1
        lead_id = f"{base_id}-{id_counts[base_id]:02d}"

        postcode_match = POSTCODE_RE.search(value(row, 3))

        rows.append(
            {
                "lead_id": lead_id,
                "company_name": company_name,
                "segment": "HR Consultancy",
                "subtype": value(row, 2),
                "address": value(row, 3),
                "city_region": value(row, 4),
                "postcode": postcode_match.group(1).upper() if postcode_match else "",
                "distance_from_york_miles": "",
                "estimated_headcount": "",
                "headcount_source_url": "",
                "phone": value(row, 5),
                "rating": value(row, 6),
                "reviews": value(row, 7),
                "website_url": "",
                "company_linkedin_url": "",
                "decision_maker_name": "",
                "decision_maker_role": "",
                "decision_maker_linkedin_url": "",
                "email": "",
                "email_type": "",
                "email_confidence": "",
                "email_source_url": "",
                "linkedin_source_url": "",
                "fit_score": "",
                "priority": "",
                "status": "research_needed",
                "source": SOURCE_PATH.name,
                "source_url": "",
                "notes": value(row, 11),
                "last_researched_at": "",
                "contacted_at": "",
                "follow_up_at": "",
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
