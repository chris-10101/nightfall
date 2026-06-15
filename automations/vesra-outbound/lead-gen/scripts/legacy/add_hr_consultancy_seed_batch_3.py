from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"
TODAY = date.today().isoformat()


SEED_ROWS = [
    ("Humber HR People (Yorkshire) Limited", "Humber / Lincolnshire", "http://www.humberhrpeople.co.uk/", "", "https://hrindependents.co.uk/directory-listing/humber-hr-people-yorkshire-limited/", "HRi source: accredited outsourced HR and talent consultancy for Yorkshire and Humber SMEs."),
    ("BeeSure HR", "County Durham / North East / Yorkshire", "https://www.beesurehr.co.uk", "", "https://www.durhamstartups.co.uk/story/north-east-hr-consultancy-celebrates-double-national-award-success/", "Public source: County Durham HR consultancy supporting small to medium-sized businesses across the North East and Yorkshire."),
    ("Inspired HR", "Blyth / North East", "https://www.inspired-hr.co.uk", "", "https://hrindependents.co.uk/directory-listing/inspired-hr-ltd/", "HRi source: North East HR group offering generalist and strategic HR consultancy, legal, recruitment and wellbeing support."),
    ("NCS HR Solutions", "Middlewich / Cheshire", "https://www.ncshr.co.uk", "nicola@ncshr.co.uk", "https://uk.linkedin.com/company/ncs-hr", "LinkedIn source: 2-10 employee Cheshire HR consultancy providing outsourced HR to small business owners and charities."),
    ("HR Think", "UK-wide", "https://hrthink.co.uk/", "", "https://hrindependents.co.uk/directory-listing/hr-think/", "HRi source: accredited HR consultancy specialising in workplace mediation, conflict coaching and impartial investigations."),
    ("Inspiring Reward Ltd", "UK-wide", "https://www.inspiringreward.co.uk/", "", "https://hrindependents.co.uk/directory-listing/inspiring-reward-ltd/", "HRi source: HR consultancy specialising in reward and benefits strategy to attract and retain employees."),
    ("Task HR Ltd", "UK-wide", "https://www.taskhr.co.uk/", "", "https://hrindependents.co.uk/directory-listing/task-hr-ltd/", "HRi source: independent HR consultancy for start-ups, scaling companies and established professional services businesses."),
    ("The Strategic Enterprise Group", "UK-wide", "https://www.strategic-enterprise.com/", "", "https://hrindependents.co.uk/directory-listing/the-strategic-enterprise-group/", "HRi source: human resource consultants and occupational psychologists providing outsourced HR and employment law advice."),
    ("Focus on the Balance Ltd", "UK-wide", "http://www.focusonthebalance.co.uk", "", "https://hrindependents.co.uk/directory-listing/focus-on-the-balance-ltd/", "HRi source: HR consultancy providing HR partnership to small businesses, start-ups and scale-ups."),
    ("Pentland HR", "Scottish Borders / Lincoln / UK-wide", "http://www.pentlandhr.co.uk", "", "https://hrindependents.co.uk/directory-listing/pentland-hr/", "HRi source: HR support for SMEs, including clients in Lincoln and higher-risk employee safety environments."),
    ("Pocket HR / Kate Underwood HR and Training", "UK-wide", "http://www.kateunderwoodhr.co.uk", "", "https://hrindependents.co.uk/directory-listing/pocket-hr-ltd-ta-kate-underwood-hr-and-training/", "HRi source: independent HR and training consultancy."),
    ("Maysante Consultancy", "UK-wide", "http://www.maysante.co.uk", "", "https://hrindependents.co.uk/directory-listing/maysante-consultancy/", "HRi source: strategic HR consulting, leadership and technology consultancy."),
    ("Mast People Support", "UK-wide", "http://www.mastpeoplesupport.co.uk", "", "https://hrindependents.co.uk/directory-listing/mast-people-support/", "HRi source: investigations, HR and ethics support for business owners."),
    ("Stress Free HR Ltd", "UK-wide", "http://www.stressfreehr.co.uk", "", "https://hrindependents.co.uk/directory-listing/stress-free-hr-ltd/", "HRi source: HR consultancy supporting employers from first employee through complex employee relations issues."),
    ("Bamboo People Solutions", "UK-wide", "http://www.bamboopeoplesolutions.co.uk", "", "https://hrindependents.co.uk/directory-listing/bamboo-people-solutions/", "HRi source: flexible HR director, coaching and HR support for business owners and leaders."),
    ("Metro HR Ltd", "UK-wide", "http://www.metrohr.co.uk", "", "https://hrindependents.co.uk/directory-listing/metro-hr-ltd/", "HRi source: professional and practical HR advice to improve organisational effectiveness and performance."),
    ("CooperativeHR Ltd", "UK-wide", "http://www.cooperativehr.co.uk", "", "https://hrindependents.co.uk/directory-listing/cooperativehr-ltd/", "HRi source: HR outsourcing provider helping business owners with HR across sectors."),
    ("The HR Dept Leeds South", "Leeds", "https://www.hrdept.co.uk/leeds-south/who-we-are", "sarah.bradley@hrdept.co.uk", "https://www.hrdept.co.uk/leeds-south/who-we-are", "Branch source: outsourced HR and employment law support for local SMEs; Director Sarah Bradley."),
    ("The HR Dept Wigan & St Helens", "Wigan / St Helens", "https://www.hrdept.co.uk/wigan-st-helens/who-we-are", "", "https://www.hrdept.co.uk/wigan-st-helens/who-we-are", "Branch source: local outsourced HR support for companies; Managing Director Nigel Finch."),
    ("The HR Dept North Derbyshire", "North Derbyshire", "https://www.hrdept.co.uk/north-derbyshire/who-we-are", "", "https://www.hrdept.co.uk/north-derbyshire/who-we-are", "Branch source: outsourced HR services for smaller owner-manager businesses and SMEs."),
    ("The HR Dept Leicester & NW Leicestershire", "Leicester / North West Leicestershire", "https://www.hrdept.co.uk/leicester-nw-leicestershire", "hr.nwleicsandleicester@hrdept.co.uk", "https://www.hrdept.co.uk/leicester-nw-leicestershire", "Branch source: outsourced HR services and employment law advice for SMEs across the wider East Midlands."),
]


GENERIC_LOCAL_PARTS = {"hello", "info", "contact", "help", "enquiries", "support", "sayhello"}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def root_domain(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"co", "org", "ac", "gov"} and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def next_id(company_name: str, existing_ids: set[str]) -> str:
    base_id = slugify(company_name)
    index = 1
    while True:
        lead_id = f"{base_id}-{index:02d}"
        if lead_id not in existing_ids:
            return lead_id
        index += 1


def score_row(row: dict[str, str]) -> tuple[str, str]:
    score = 25
    if row.get("city_region"):
        score += 15
    if row.get("website_url"):
        score += 15
    if row.get("email"):
        score += 10
    notes = row.get("notes", "").lower()
    if "sme" in notes or "small" in notes or "start-up" in notes or "outsourced" in notes:
        score += 20
    if "uk-wide" in row.get("city_region", "").lower():
        score -= 10
    score = max(0, min(score, 100))
    if score >= 80:
        priority = "high"
    elif score >= 60:
        priority = "medium"
    elif score >= 40:
        priority = "low"
    else:
        priority = "park"
    return str(score), priority


def email_type(email: str) -> str:
    if not email:
        return ""
    local_part = email.split("@", 1)[0].lower()
    return "generic" if local_part in GENERIC_LOCAL_PARTS else "named"


def main() -> None:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    existing_ids = {row["lead_id"] for row in rows}
    existing_names = {normalize(row["company_name"]) for row in rows}
    existing_domains = {root_domain(row["website_url"]) for row in rows if row.get("website_url")}
    existing_source_urls = {row["source_url"].rstrip("/") for row in rows if row.get("source_url")}

    added = 0
    skipped = 0

    for company_name, city_region, website_url, email, source_url, notes in SEED_ROWS:
        name_key = normalize(company_name)
        domain_key = root_domain(website_url)
        source_key = source_url.rstrip("/")
        allow_same_domain = "hrdept.co.uk" in domain_key
        if (
            name_key in existing_names
            or (domain_key and domain_key in existing_domains and not allow_same_domain)
            or source_key in existing_source_urls
        ):
            skipped += 1
            continue

        row = {header: "" for header in HEADERS}
        row.update(
            {
                "lead_id": next_id(company_name, existing_ids),
                "company_name": company_name,
                "segment": "HR Consultancy",
                "subtype": "Outsourced HR / SME HR support",
                "city_region": city_region,
                "website_url": website_url,
                "email": email,
                "email_type": email_type(email),
                "email_confidence": "high" if email else "",
                "email_source_url": website_url if email else "",
                "status": "ready_to_review" if email else "enriched",
                "source": "Curated HR directory / public listing",
                "source_url": source_url,
                "notes": notes,
                "last_researched_at": TODAY,
            }
        )
        row["fit_score"], row["priority"] = score_row(row)

        rows.append(row)
        existing_ids.add(row["lead_id"])
        existing_names.add(name_key)
        if domain_key and not allow_same_domain:
            existing_domains.add(domain_key)
        existing_source_urls.add(source_key)
        added += 1

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Added {added} rows; skipped {skipped} duplicates. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
