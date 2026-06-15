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
    {
        "company_name": "Athena HR",
        "city_region": "York",
        "website_url": "https://athena-hr.com/",
        "company_linkedin_url": "https://uk.linkedin.com/company/athena-hr",
        "notes": "LinkedIn source: 2-10 employee York HR consultancy providing SME HR support and outsourced HR department services.",
    },
    {
        "company_name": "Grounded HR",
        "city_region": "York",
        "website_url": "https://www.groundedhr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/groundedhr-uk",
        "email": "hello@groundedhr.co.uk",
        "notes": "LinkedIn source: 2-10 employee York HR consultancy providing straightforward, compassionate HR support.",
    },
    {
        "company_name": "HR Hand",
        "city_region": "York",
        "website_url": "http://www.hrhand.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/hr-hand",
        "notes": "LinkedIn source: 2-10 employee York HR consultancy handling HR and legal people issues.",
    },
    {
        "company_name": "McMillan and Associates Ltd",
        "city_region": "York",
        "website_url": "http://www.mcmillanandassociateshr.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/mcmillan-and-associates-ltd",
        "notes": "LinkedIn source: 2-10 employee York HR and OD consultancy providing outsourced services.",
    },
    {
        "company_name": "PinkCube HR Consultancy",
        "city_region": "York",
        "website_url": "https://www.pinkcubehr.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/pinkcube-hr-consultancy",
        "notes": "LinkedIn source: 2-10 employee York HR consultancy for start-ups and SMEs.",
    },
    {
        "company_name": "Norton Loxley",
        "city_region": "York / Leeds / North Yorkshire",
        "website_url": "https://www.nortonloxley.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/nortonloxley",
        "email": "sayhello@nortonloxley.com",
        "notes": "LinkedIn and website source: 2-10 employee outsourced HR and recruitment consultancy for SMEs and scale-ups across Yorkshire and the North East.",
    },
    {
        "company_name": "Cloud Eleven Human Resources",
        "city_region": "Harrogate",
        "website_url": "http://www.cloud11hr.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/cloud-eleven-human-resources-limited",
        "notes": "LinkedIn source: 2-10 employee Harrogate HR consultancy and people management business partner.",
    },
    {
        "company_name": "Candid HR",
        "city_region": "Ilkley",
        "website_url": "http://www.candidhr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/candidhr",
        "notes": "LinkedIn source: 2-10 employee Ilkley outsourced HR consultancy focused on commercially grounded HR.",
    },
    {
        "company_name": "apple hr support",
        "city_region": "Leeds",
        "website_url": "https://www.applehr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/apple-hr-support-ltd",
        "email": "kate@applehr.co.uk",
        "notes": "LinkedIn source: 2-10 employee Leeds outsourced HR consultancy specialising in SMEs.",
    },
    {
        "company_name": "Positive People HR",
        "city_region": "Huddersfield",
        "website_url": "http://www.positivepeoplehr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/positive-people-hr",
        "email": "info@positivepeoplehr.co.uk",
        "notes": "LinkedIn and website source: 2-10 employee outsourced HR support and small business HR advice.",
    },
    {
        "company_name": "Argan HR Consultancy",
        "city_region": "Rochdale / North West",
        "website_url": "https://arganhrconsultancy.co.uk",
        "email": "help@arganhrconsultancy.co.uk",
        "notes": "Website source: HR consultancy working exclusively with SMEs across the North West and UK-wide.",
    },
    {
        "company_name": "Rob Heerin HR",
        "city_region": "Stockton / Teesside",
        "website_url": "https://robheerinhr.co.uk",
        "notes": "Website source: HR consultancy for owner-managed businesses and SMEs across Stockton, Middlesbrough, Darlington, Hartlepool, Durham and Newcastle.",
    },
    {
        "company_name": "Kate Edwards HR Solutions",
        "city_region": "Teesside",
        "website_url": "https://hr-solutions.net",
        "email": "kate@hr-solutions.net",
        "notes": "Website source: experienced HR consultant and workplace mediator offering clear and pragmatic support.",
    },
    {
        "company_name": "Holgate HR",
        "city_region": "Newcastle upon Tyne",
        "website_url": "http://www.holgatehr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/holgate-hr",
        "notes": "LinkedIn source: 2-10 employee people management and HR consultancy across North East, Teesside, North Yorkshire, Leeds and Cumbria.",
    },
    {
        "company_name": "Your HR Manager UK",
        "city_region": "Newcastle upon Tyne",
        "website_url": "http://www.yourhrmanager.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/yourhrmanager",
        "notes": "LinkedIn source: 2-10 employee North East outsourced HR function for start-ups, micro SMEs and larger organisations.",
    },
    {
        "company_name": "The HR Branch",
        "city_region": "Lincoln",
        "website_url": "https://thehrbranch.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/the-hr-branch-limited",
        "email": "info@thehrbranch.co.uk",
        "notes": "LinkedIn source: 2-10 employee Lincoln HR consultancy offering practical HR support to start-ups and SMEs.",
    },
    {
        "company_name": "Guardian People Management",
        "city_region": "Nottingham / Northwich",
        "website_url": "https://guardian.online",
        "company_linkedin_url": "https://uk.linkedin.com/company/guardian-people-management",
        "notes": "LinkedIn source: 2-10 employee people management consultancy with HR tools, training and advice for UK employers.",
    },
    {
        "company_name": "Opexcell",
        "city_region": "Lincoln",
        "website_url": "https://opexcell.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/opexcell-limited",
        "notes": "LinkedIn source: 2-10 employee operations and HR consultancy offering HR policy, engagement and performance support.",
    },
    {
        "company_name": "My HR Hub",
        "city_region": "Nottingham",
        "website_url": "http://www.myhrhub.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/my-hr-hub",
        "notes": "LinkedIn source: 2-10 employee award-winning HR consultancy for start-up, small and fast-growing businesses.",
    },
    {
        "company_name": "TOOJAYS Training & HR Consultancy",
        "city_region": "Peterborough",
        "website_url": "http://www.toojays.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/toojays-training-%26-hr-consultancy-ltd",
        "notes": "LinkedIn source: 2-10 employee HR consultancy and leadership training firm within the wider York radius.",
    },
    {
        "company_name": "1850",
        "city_region": "Chester",
        "website_url": "http://www.e18hteen50.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/1850-business-solutions-ltd",
        "notes": "LinkedIn source: 2-10 employee Cheshire people and culture consultancy providing tailored HR solutions.",
    },
    {
        "company_name": "Ashfield HR",
        "city_region": "Macclesfield / Cheshire",
        "website_url": "http://www.ashfieldhr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/ashfield-hr",
        "notes": "LinkedIn and website source: 2-10 employee HR consultancy for start-ups and SMEs across Cheshire and the North West.",
    },
    {
        "company_name": "Peach Law",
        "city_region": "Cheadle Hulme / Cheshire",
        "website_url": "http://www.peachlaw.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/peach-law-limited",
        "notes": "LinkedIn source: 2-10 employee employment law and HR specialist for flexible employer support.",
    },
    {
        "company_name": "Collaborate HR",
        "city_region": "Stockport / Greater Manchester",
        "website_url": "https://collaboratehr.co.uk/",
        "notes": "Website source: outsourced HR consultancy for female-led small businesses and entrepreneurs.",
    },
    {
        "company_name": "Cornerstone Resources",
        "city_region": "Stockport / Greater Manchester",
        "website_url": "https://cornerstoneresources.co.uk/",
        "notes": "Website source: HR consultancy for small businesses, charities and non-profits with outsourced HR packages.",
    },
    {
        "company_name": "WorkPlace HR",
        "city_region": "Manchester / UK",
        "website_url": "http://www.workplace-hr.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/workplace-hr",
        "notes": "LinkedIn source: 2-10 employee outsourced HR and employment law advice provider for SMEs.",
    },
    {
        "company_name": "Avella People",
        "city_region": "Manchester",
        "website_url": "https://www.avellapeople.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/avella-people",
        "notes": "LinkedIn source: 2-10 employee subscription-based HR and recruitment provider for modern organisations.",
    },
    {
        "company_name": "Anderson Wright Consulting",
        "city_region": "Manchester",
        "website_url": "http://www.andersonwright.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/anderson-wright-consulting-ltd",
        "notes": "LinkedIn source: 2-10 employee recruitment firm with outsourced HR solutions and CIPD-qualified HR consultancy.",
    },
    {
        "company_name": "DML Consulting",
        "city_region": "Manchester",
        "website_url": "http://www.dml-consulting.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/dmlconsulting",
        "notes": "LinkedIn source: 2-10 employee Manchester HR consultancy partnering with ambitious high-growth organisations.",
    },
    {
        "company_name": "Luna HR Solutions",
        "city_region": "Manchester",
        "website_url": "https://lunahrsolutions.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/luna-hr-solutions",
        "notes": "LinkedIn source: 2-10 employee Manchester outsourced HR consultancy packages and ad-hoc employment support.",
    },
    {
        "company_name": "Mint HR",
        "city_region": "Leeds / Yorkshire",
        "website_url": "https://www.mint-hr.com",
        "email": "tracy@mint-hr.com",
        "notes": "Website source: Yorkshire outsourced HR consultancy serving small businesses across Leeds, Sheffield, Huddersfield and Hull.",
    },
    {
        "company_name": "HR Recruitify Group",
        "city_region": "Derby",
        "website_url": "https://www.hr-recruitify.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/hr-recruitify-group-ltd",
        "email": "info@hr-recruitify.com",
        "notes": "LinkedIn source: 2-10 employee Derby HR consultancy and recruitment provider.",
    },
    {
        "company_name": "Solutions For HR",
        "city_region": "Bury / Lancashire",
        "website_url": "https://www.solutionsforhr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/solutions-for-hr",
        "notes": "LinkedIn source: 2-10 employee HR outsourcing and employment law consultancy for SMEs.",
    },
    {
        "company_name": "Halo Consultancy & Business Services",
        "city_region": "Preston / Lancashire",
        "website_url": "https://www.haloconsultancy.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/halo-consultancy-and-business-services",
        "email": "contact@haloconsultancy.uk",
        "notes": "LinkedIn source: 2-10 employee consultancy helping SMEs with HR, employment law, governance, risk and compliance.",
    },
    {
        "company_name": "Employer Solutions",
        "city_region": "Lancaster / Lancashire",
        "website_url": "http://employersolutions.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/employer-solutions",
        "notes": "LinkedIn source: 2-10 employee HR consultancy for SMEs and employee handbook support.",
    },
    {
        "company_name": "Sereniti",
        "city_region": "Sheffield",
        "website_url": "https://www.sereniti.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/sereniti-ltd",
        "notes": "Website and LinkedIn source: Sheffield HR, training and business psychology consultancy offering outsourced HR and pay-as-you-go HR consulting.",
    },
    {
        "company_name": "Diverse HR Consultancy",
        "city_region": "Thirsk / North Yorkshire",
        "website_url": "https://www.diversehrconsultancy.com/",
        "company_linkedin_url": "https://uk.linkedin.com/company/diverse-hr-consultancyltd",
        "notes": "LinkedIn source: 1 employee specialist HR consultancy providing tailored HR solutions across North Yorkshire.",
    },
    {
        "company_name": "Vantage HR Consultancy",
        "city_region": "Peterborough",
        "website_url": "",
        "company_linkedin_url": "https://www.linkedin.com/company/vantage-hr-consultancy-limited",
        "notes": "LinkedIn source: HR consultancy supporting SMEs without internal HR departments; website not visible in search snippet.",
    },
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
    if row.get("company_linkedin_url"):
        score += 10
    if row.get("email"):
        score += 10
    notes = row.get("notes", "").lower()
    if "small" in notes or "sme" in notes or "start-up" in notes or "micro" in notes:
        score += 20
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
    existing_linkedin = {row["company_linkedin_url"].rstrip("/") for row in rows if row.get("company_linkedin_url")}

    added = 0
    skipped = 0

    for prospect in SEED_ROWS:
        name_key = normalize(prospect["company_name"])
        domain_key = root_domain(prospect.get("website_url", ""))
        linkedin_key = prospect.get("company_linkedin_url", "").rstrip("/")
        if (
            name_key in existing_names
            or (domain_key and domain_key in existing_domains)
            or (linkedin_key and linkedin_key in existing_linkedin)
        ):
            skipped += 1
            continue

        email = prospect.get("email", "")
        source_url = prospect.get("company_linkedin_url") or prospect.get("website_url", "")
        row = {header: "" for header in HEADERS}
        row.update(
            {
                "lead_id": next_id(prospect["company_name"], existing_ids),
                "company_name": prospect["company_name"],
                "segment": "HR Consultancy",
                "subtype": "Outsourced HR / SME HR support",
                "city_region": prospect.get("city_region", ""),
                "website_url": prospect.get("website_url", ""),
                "company_linkedin_url": prospect.get("company_linkedin_url", ""),
                "email": email,
                "email_type": email_type(email),
                "email_confidence": "high" if email else "",
                "email_source_url": prospect.get("website_url", "") if email else "",
                "linkedin_source_url": prospect.get("company_linkedin_url", ""),
                "status": "ready_to_review" if email else "enriched",
                "source": "Curated public search result",
                "source_url": source_url,
                "notes": prospect.get("notes", ""),
                "last_researched_at": TODAY,
            }
        )
        row["fit_score"], row["priority"] = score_row(row)

        rows.append(row)
        existing_ids.add(row["lead_id"])
        existing_names.add(name_key)
        if domain_key:
            existing_domains.add(domain_key)
        if linkedin_key:
            existing_linkedin.add(linkedin_key)
        added += 1

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Added {added} rows; skipped {skipped} duplicates. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
