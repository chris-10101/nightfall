from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from datetime import date
from pathlib import Path

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"
TODAY = date.today().isoformat()


SOURCE_URL_ENRICHMENTS = {
    "https://hrindependents.co.uk/directory-listing/hr-think/": {
        "decision_maker_name": "Liz Jewer",
        "decision_maker_role": "Director",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/hr-think/",
    },
    "https://hrindependents.co.uk/directory-listing/inspiring-reward-ltd/": {
        "decision_maker_name": "Andrea Rae",
        "decision_maker_role": "Reward Consultant",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/inspiring-reward-ltd/",
    },
    "https://hrindependents.co.uk/directory-listing/task-hr-ltd/": {
        "decision_maker_name": "Katy Mcminn",
        "decision_maker_role": "Founder & Director",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/task-hr-ltd/",
    },
    "https://hrindependents.co.uk/directory-listing/the-strategic-enterprise-group/": {
        "decision_maker_name": "Bernard Horsford",
        "decision_maker_role": "Executive Chairman",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/the-strategic-enterprise-group/",
    },
    "https://hrindependents.co.uk/directory-listing/focus-on-the-balance-ltd/": {
        "decision_maker_name": "Katie Osborne",
        "decision_maker_role": "Owner / HR Consultant",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/focus-on-the-balance-ltd/",
    },
    "https://hrindependents.co.uk/directory-listing/pentland-hr/": {
        "decision_maker_name": "Kirsten Warden",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/pentland-hr/",
    },
    "https://hrindependents.co.uk/directory-listing/pocket-hr-ltd-ta-kate-underwood-hr-and-training/": {
        "decision_maker_name": "Catherine Underwood",
        "decision_maker_role": "Managing Director and HR Director",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/pocket-hr-ltd-ta-kate-underwood-hr-and-training/",
    },
    "https://hrindependents.co.uk/directory-listing/humber-hr-people-yorkshire-limited/": {
        "decision_maker_name": "Kate van der Sluis",
        "decision_maker_role": "Joint Managing Director",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/humber-hr-people-yorkshire-limited/",
    },
    "https://hrindependents.co.uk/directory-listing/maysante-consultancy/": {
        "decision_maker_name": "Mary Asante",
        "decision_maker_role": "Chief Executive",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/maysante-consultancy/",
    },
    "https://hrindependents.co.uk/directory-listing/mast-people-support/": {
        "decision_maker_name": "Kate Marston",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/mast-people-support/",
    },
    "https://hrindependents.co.uk/directory-listing/stress-free-hr-ltd/": {
        "decision_maker_name": "Anabela Yourell",
        "decision_maker_role": "HR Consultant",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/stress-free-hr-ltd/",
    },
    "https://hrindependents.co.uk/directory-listing/metro-hr-ltd/": {
        "decision_maker_name": "Charlotte Allfrey",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/metro-hr-ltd/",
    },
    "https://hrindependents.co.uk/directory-listing/cooperativehr-ltd/": {
        "decision_maker_name": "Theresa Cooper",
        "decision_maker_role": "Managing Director",
        "linkedin_source_url": "https://hrindependents.co.uk/directory-listing/cooperativehr-ltd/",
    },
    "https://www.hrdept.co.uk/leeds-south/who-we-are": {
        "decision_maker_name": "Sarah Bradley",
        "decision_maker_role": "Director",
        "email": "sarah.bradley@hrdept.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.hrdept.co.uk/leeds-south/who-we-are",
    },
    "https://www.hrdept.co.uk/wigan-st-helens/who-we-are": {
        "decision_maker_name": "Nigel Finch",
        "decision_maker_role": "Managing Director",
        "linkedin_source_url": "https://www.hrdept.co.uk/wigan-st-helens/who-we-are",
    },
}


COMPANY_ENRICHMENTS = {
    "The HR Dept Bradford": {
        "decision_maker_name": "Sarah Bradley",
        "decision_maker_role": "Director",
    },
    "Norton Loxley | Outsourced HR Consultants": {
        "decision_maker_name": "Sian Whelan",
        "decision_maker_role": "Co-founder",
        "linkedin_source_url": "https://www.nortonloxley.com",
    },
    "Norton Loxley (Leeds)": {
        "decision_maker_name": "Sian Whelan",
        "decision_maker_role": "Co-founder",
        "linkedin_source_url": "https://www.nortonloxley.com",
    },
    "The HR Branch": {
        "decision_maker_name": "Katharine Nundy",
        "company_linkedin_url": "https://uk.linkedin.com/company/the-hr-branch-limited",
        "email": "info@thehrbranch.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://thehrbranch.co.uk",
        "linkedin_source_url": "https://thehrbranch.co.uk",
    },
    "Breathing Space HR": {
        "company_linkedin_url": "https://uk.linkedin.com/company/breathing-space-hr-consultants-leeds",
        "decision_maker_name": "Suzie Bogle",
        "decision_maker_role": "Business Owner & Senior HRBP",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/suziebogle",
        "email": "suzie@breathingspacehr.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://breathingspacehr.co.uk/meet-the-team/",
        "linkedin_source_url": "https://breathingspacehr.co.uk/meet-the-team/",
    },
    "Rico HR": {
        "company_linkedin_url": "https://www.linkedin.com/company/rico-hr-consultancy-ltd/",
        "linkedin_source_url": "https://www.ricohr.co.uk/",
    },
    "Spire HR Solutions": {
        "company_linkedin_url": "https://www.linkedin.com/company/spire-hr-solutions-ltd/",
        "linkedin_source_url": "https://spirehr.co.uk/",
    },
    "Ashton People Solutions": {
        "company_linkedin_url": "https://www.linkedin.com/company/ashtonpeoplesolutions",
        "linkedin_source_url": "https://ashtonpeoplesolutions.co.uk/",
    },
    "Davidson HR Associates": {
        "decision_maker_name": "Debbie Davidson",
        "decision_maker_linkedin_url": "https://www.linkedin.com/in/davidsonhrassociates/",
        "email": "debbie@davidson-hr.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://davidson-hr.co.uk/",
        "linkedin_source_url": "https://davidson-hr.co.uk/",
    },
    "Averist HR Services": {
        "company_linkedin_url": "https://www.linkedin.com/company/averist-business-services/",
        "linkedin_source_url": "https://www.averist.co.uk/",
    },
    "Positive People HR": {
        "company_linkedin_url": "https://www.linkedin.com/company/positive-people-hr/",
        "decision_maker_name": "Paul Addy",
        "decision_maker_role": "Managing Director",
        "email": "info@positivepeoplehr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://positivepeoplehr.co.uk/about/",
        "linkedin_source_url": "https://positivepeoplehr.co.uk/about/",
    },
    "ComplexHR": {
        "company_linkedin_url": "https://www.linkedin.com/company/complex-hr/",
        "decision_maker_name": "Helen Kirk-Blythe",
        "decision_maker_role": "HR Consultant",
        "decision_maker_linkedin_url": "https://www.linkedin.com/in/helen-kirk-blythe-032532136/",
        "email": "helen@complexhr.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.complexhr.co.uk/",
        "linkedin_source_url": "https://www.complexhr.co.uk/",
    },
    "Beanstalk HR": {
        "company_linkedin_url": "https://www.linkedin.com/company/beanstalk-hr/",
        "decision_maker_name": "Yvette Whitwam",
        "decision_maker_role": "HR Consultant",
        "email": "yvette.whitwam@beanstalkhr.com",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://beanstalkhr.com/",
        "linkedin_source_url": "https://beanstalkhr.com/",
    },
    "Paveley HR Solutions": {
        "decision_maker_name": "Sarah Paveley",
        "decision_maker_role": "HR Consultant",
        "decision_maker_linkedin_url": "https://www.linkedin.com/in/sarah-paveley-hr/",
        "linkedin_source_url": "https://www.paveleyhr.com/",
    },
    "Impact HR": {
        "company_linkedin_url": "https://www.linkedin.com/company/impact-hr-consulting-limited/",
        "email": "hello@impacthr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://impacthr.co.uk/about-impact-hr/team/",
        "linkedin_source_url": "https://impacthr.co.uk/about-impact-hr/team/",
    },
    "Loates HR Consultancy": {
        "company_linkedin_url": "https://www.linkedin.com/showcase/loates-hr/",
        "email": "hello@loateshr.net",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://loateshr.net/about-us/",
        "linkedin_source_url": "https://loateshr.net/about-us/",
    },
}


BAD_EMAILS = {"user@domain.com"}


def score_priority(row: dict[str, str]) -> tuple[str, str]:
    score = 0
    if row.get("segment"):
        score += 25
    if row.get("city_region"):
        score += 15
    if row.get("estimated_headcount"):
        score += 15
    if row.get("decision_maker_name"):
        score += 15 if row.get("decision_maker_role") else 10
    if row.get("notes") or row.get("subtype"):
        score += 15
    if row.get("email") and (row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url")):
        score += 15
    elif row.get("email") or row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url"):
        score += 10
    elif row.get("website_url"):
        score += 5

    score = min(score, 100)
    if score >= 80:
        priority = "high"
    elif score >= 60:
        priority = "medium"
    elif score >= 40:
        priority = "low"
    else:
        priority = "park"
    return str(score), priority


def normalize_source_url(value: str) -> str:
    return value.strip().rstrip("/")


def apply_values(row: dict[str, str], values: dict[str, str]) -> int:
    changed_fields = 0
    for field, value in values.items():
        if not value:
            continue
        if field == "email" and row.get("email_type") == "generic" and values.get("email_type") == "named":
            row[field] = value
            changed_fields += 1
            continue
        if field in {"email_type", "email_confidence", "email_source_url"} and values.get("email_type") == "named" and row.get("email_type") == "generic":
            row[field] = value
            changed_fields += 1
            continue
        if value and not row.get(field):
            row[field] = value
            changed_fields += 1
    return changed_fields


def maybe_extract_name_from_notes(row: dict[str, str]) -> int:
    notes = row.get("notes", "")
    if row.get("decision_maker_name"):
        return 0
    match = re.search(r"\b(Managing Director|Director)\s+([A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)+)\b", notes)
    if not match:
        return 0
    row["decision_maker_role"] = row.get("decision_maker_role") or match.group(1)
    row["decision_maker_name"] = match.group(2).rstrip(".")
    row["linkedin_source_url"] = row.get("linkedin_source_url") or row.get("source_url", "")
    return 2


def main() -> None:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    updated_rows = 0
    updated_fields = 0
    cleaned_emails = 0

    source_map = {normalize_source_url(key): values for key, values in SOURCE_URL_ENRICHMENTS.items()}

    for row in rows:
        row_changed = 0

        if row.get("email", "").lower() in BAD_EMAILS:
            row["email"] = ""
            row["email_type"] = ""
            row["email_confidence"] = ""
            row["email_source_url"] = ""
            cleaned_emails += 1
            row_changed += 4

        source_values = source_map.get(normalize_source_url(row.get("source_url", "")))
        if source_values:
            row_changed += apply_values(row, source_values)

        company_values = COMPANY_ENRICHMENTS.get(row.get("company_name", ""))
        if company_values:
            row_changed += apply_values(row, company_values)

        row_changed += maybe_extract_name_from_notes(row)

        if row_changed:
            row["last_researched_at"] = TODAY
            row["fit_score"], row["priority"] = score_priority(row)
            if row.get("website_url") and (row.get("email") or row.get("decision_maker_linkedin_url") or row.get("decision_maker_name")):
                row["status"] = "ready_to_review"
            elif row.get("website_url"):
                row["status"] = "enriched"
            updated_rows += 1
            updated_fields += row_changed

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated_rows} rows; filled/cleaned {updated_fields} fields; removed {cleaned_emails} bad emails.")


if __name__ == "__main__":
    main()
