from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from pathlib import Path

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"


SEED_PROSPECTS = [
    {
        "company_name": "PG Accounting Services Ltd",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "address": "Suite 4, Crossgates House, 67 Crossgates Shopping Centre, Station Road, Leeds LS15 8EU",
        "city_region": "Leeds",
        "postcode": "LS15 8EU",
        "phone": "0113 260 8614",
        "website_url": "https://pgaccounting.co.uk/",
        "email": "info@pgaccounting.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://pgaccounting.co.uk/",
        "source": "Public website",
        "source_url": "https://pgaccounting.co.uk/",
        "notes": "Family-run accounting practice based in Crossgates, Leeds; serves one-person start-ups through larger businesses.",
    },
    {
        "company_name": "All Paul Limited",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "Leeds",
        "website_url": "https://www.all-paul.co.uk/",
        "source": "Public website",
        "source_url": "https://www.all-paul.co.uk/",
        "notes": "Leeds accountants focused on smaller businesses and owners.",
    },
    {
        "company_name": "Wyatt & Co Chartered Accountants",
        "segment": "Accountancy",
        "subtype": "Chartered accountancy",
        "city_region": "Garforth / Leeds",
        "website_url": "https://www.wyattandco.net/",
        "source": "Public website",
        "source_url": "https://www.wyattandco.net/",
        "notes": "Third-generation family-run chartered accountancy practice in Garforth, Leeds.",
    },
    {
        "company_name": "Four Accountancy",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "Leeds",
        "phone": "0113 2677980",
        "website_url": "https://www.fouraccountancy.co.uk/",
        "email": "info@fouraccountancy.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.fouraccountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://www.fouraccountancy.co.uk/",
        "notes": "Family-run Leeds accountancy business with small-business, tax, payroll, CIS and VAT services.",
    },
    {
        "company_name": "Leon & Company",
        "segment": "Accountancy",
        "subtype": "Chartered accountancy",
        "city_region": "Leeds",
        "phone": "0113 288 8111",
        "website_url": "https://leonandcompany.co.uk/",
        "source": "Public website",
        "source_url": "https://leonandcompany.co.uk/",
        "notes": "Leeds accountancy firm offering payroll, VAT, business advisory, tax and bookkeeping services.",
    },
    {
        "company_name": "Avanti Accounting Services",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "Leeds",
        "website_url": "https://www.avantias.co.uk/",
        "source": "Public website",
        "source_url": "https://www.avantias.co.uk/",
        "notes": "Yorkshire-based accountants for small and medium businesses; site describes a team of two.",
    },
    {
        "company_name": "RS Accountancy",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "Leeds",
        "phone": "03332 421 129",
        "website_url": "https://rsaccountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://rsaccountancy.co.uk/",
        "notes": "Modern online accounting services for small and local businesses.",
    },
    {
        "company_name": "Torque Law",
        "segment": "Employment Law",
        "subtype": "Specialist employment law firm",
        "address": "1st Floor Box Tree House, Northminster Business Park, Upper Poppleton, York YO26 6QR",
        "city_region": "York",
        "postcode": "YO26 6QR",
        "phone": "01904 437 680",
        "website_url": "https://torquelaw.co.uk/",
        "decision_maker_name": "Emma Whiting",
        "decision_maker_role": "Partner & Specialist Employment Law Solicitor",
        "email": "info@torquelaw.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://torquelaw.co.uk/",
        "source": "Public website",
        "source_url": "https://torquelaw.co.uk/about-torque-law/",
        "notes": "Specialist employment law firm founded by Tiggy Clifford and Emma Whiting; advises SME employers and senior executives.",
    },
    {
        "company_name": "Morrish Solicitors",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Leeds",
        "website_url": "https://www.morrishsolicitors.com/services/employment/",
        "source": "Public website",
        "source_url": "https://www.morrishsolicitors.com/services/employment/",
        "notes": "Leeds employment law team acting nationally on unfair dismissal, discrimination, redundancy, TUPE and whistleblowing.",
    },
    {
        "company_name": "Winston Solicitors",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Leeds",
        "phone": "0113 320 5000",
        "website_url": "https://www.winstonsolicitors.co.uk/employment",
        "decision_maker_name": "Samira Cakali",
        "decision_maker_role": "Head of Employment Law",
        "source": "Public website",
        "source_url": "https://www.winstonsolicitors.co.uk/employment",
        "notes": "Leeds employment law team; site identifies Samira Cakali as Head of Employment law.",
    },
    {
        "company_name": "Blacks Solicitors LLP",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Leeds",
        "phone": "0113 207 0000",
        "website_url": "https://www.lawblacks.com/personal/employment-law/",
        "source": "Public website",
        "source_url": "https://www.lawblacks.com/personal/employment-law/",
        "notes": "Leeds employment law team; public page references David Ward and Tom Moyes in employment law testimonials.",
    },
    {
        "company_name": "MCO Accountancy",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "York",
        "website_url": "https://mcoaccountancy.co.uk/",
        "decision_maker_name": "Mike",
        "email": "mike@mcoaccountancy.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://mcoaccountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://mcoaccountancy.co.uk/",
        "notes": "Independent York accountancy practice for small businesses, digital services and trades.",
    },
    {
        "company_name": "Equilibrium Accountants",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "York",
        "website_url": "https://www.equilaccs.co.uk/",
        "decision_maker_name": "Nikki",
        "decision_maker_role": "Managing Director",
        "email": "hello@equilaccs.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.equilaccs.co.uk/",
        "source": "Public website",
        "source_url": "https://www.equilaccs.co.uk/",
        "notes": "York-based firm focused on small businesses; site says it is led by Managing Director Nikki.",
    },
    {
        "company_name": "Fewston Business Services",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "city_region": "Harrogate",
        "phone": "01423 788241",
        "website_url": "https://www.fbsaccountants.co.uk/",
        "decision_maker_name": "Claire",
        "email": "claire@fbsaccountants.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.fbsaccountants.co.uk/",
        "source": "Public website",
        "source_url": "https://www.fbsaccountants.co.uk/",
        "notes": "Family-run Harrogate accountancy practice supporting small local businesses and individuals.",
    },
    {
        "company_name": "Baqri & Co Chartered Certified Accountants",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "address": "21 Burngreave Road, Sheffield S3 9DA",
        "city_region": "Sheffield",
        "postcode": "S3 9DA",
        "phone": "0114 360 0001",
        "website_url": "https://www.baqriandco.com/",
        "source": "Public website",
        "source_url": "https://www.baqriandco.com/",
        "notes": "Sheffield accountants helping small businesses, self-employed individuals and landlords with tax, VAT, payroll and accounts.",
    },
    {
        "company_name": "CBS Accountancy",
        "segment": "Accountancy",
        "subtype": "Small business accountancy",
        "address": "60A Birley Moor Road, Sheffield S12 4WD",
        "city_region": "Sheffield",
        "postcode": "S12 4WD",
        "phone": "0114 265 9800",
        "website_url": "https://www.cbs-accountancy.co.uk/",
        "email": "enquiries@cbs-accountancy.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.cbs-accountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://www.cbs-accountancy.co.uk/",
        "notes": "Sheffield small business specialist with bookkeeping, tax returns, payroll and company setup support.",
    },
    {
        "company_name": "Brown & Rear Accountants",
        "segment": "Accountancy",
        "subtype": "Accountancy and tax",
        "city_region": "Sheffield",
        "website_url": "https://brownandrear.co.uk/",
        "email": "accounts@brownandrear.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://brownandrear.co.uk/",
        "source": "Public website",
        "source_url": "https://brownandrear.co.uk/",
        "notes": "Sheffield and South Yorkshire accountancy firm providing accounts, bookkeeping, payroll and tax planning.",
    },
    {
        "company_name": "BR Accountancy",
        "segment": "Accountancy",
        "subtype": "Accountancy and tax",
        "city_region": "Sheffield / Yorkshire",
        "website_url": "https://www.braccountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://www.braccountancy.co.uk/",
        "notes": "Yorkshire accountancy firm supporting sole traders through limited companies with accounts, tax, payroll and bookkeeping.",
    },
    {
        "company_name": "Wilson Howe",
        "segment": "Accountancy",
        "subtype": "Chartered accountancy",
        "city_region": "Sheffield",
        "website_url": "https://www.wilsonhowe.co.uk/",
        "source": "Public website",
        "source_url": "https://www.wilsonhowe.co.uk/",
        "notes": "Family-run chartered accountancy firm based in Sheffield with a satellite office in Matlock.",
    },
    {
        "company_name": "Longs Accountancy",
        "segment": "Accountancy",
        "subtype": "Accountancy and business advisory",
        "city_region": "York",
        "website_url": "https://longsaccountancy.co.uk/",
        "decision_maker_name": "Antony",
        "email": "antony@longsaccountancy.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://longsaccountancy.co.uk/",
        "source": "Public website",
        "source_url": "https://longsaccountancy.co.uk/",
        "notes": "York accountancy practice positioning around trusted accountancy and business advice.",
    },
    {
        "company_name": "MCC Accountants",
        "segment": "Accountancy",
        "subtype": "Chartered accountancy",
        "address": "18 Woodstock Drive, Worsley, Manchester M28 2WW",
        "city_region": "Manchester / Worsley",
        "postcode": "M28 2WW",
        "website_url": "https://www.mccaccountants.co.uk/",
        "email": "info@mccaccountants.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.mccaccountants.co.uk/",
        "source": "Public website",
        "source_url": "https://www.mccaccountants.co.uk/",
        "notes": "North West chartered accountancy practice focused on business tax and management accounting.",
    },
    {
        "company_name": "Bridge Employment Law",
        "segment": "Employment Law",
        "subtype": "Specialist employment law and HR",
        "address": "First Floor, Appleyards, Escrick Grange, York YO19 6EB",
        "city_region": "York / Leeds",
        "postcode": "YO19 6EB",
        "phone": "01904 360 295",
        "website_url": "https://www.bridgeemploymentlaw.com/",
        "email": "enquiries@bridgeehr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.bridgeemploymentlaw.com/",
        "source": "Public website",
        "source_url": "https://www.bridgeemploymentlaw.com/",
        "notes": "Employment solicitors and HR specialists supporting employers on day-to-day employment and HR needs.",
    },
    {
        "company_name": "Chambers O'Neill",
        "segment": "Employment Law",
        "subtype": "Dedicated employment law practice",
        "city_region": "Manchester",
        "website_url": "https://chambersoneill.com/",
        "source": "Public website",
        "source_url": "https://chambersoneill.com/",
        "notes": "Dedicated Manchester employment law practice advising employers and employees; includes HR Partners support.",
    },
    {
        "company_name": "Martin & Co Solicitors",
        "segment": "Employment Law",
        "subtype": "Specialist employment solicitors",
        "city_region": "Manchester",
        "phone": "0161 833 9266",
        "website_url": "https://www.martinandcosolicitors.co.uk/",
        "decision_maker_name": "John Martin",
        "decision_maker_role": "Specialist Employment Solicitor",
        "source": "Public website",
        "source_url": "https://www.martinandcosolicitors.co.uk/",
        "notes": "Manchester specialist employment solicitors advising employees and employers since 1999.",
    },
    {
        "company_name": "Trent Law",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Sheffield / Nottingham / Derby",
        "phone": "0333 3444 397",
        "website_url": "https://www.trentlaw.co.uk/employment-law",
        "email": "sheffield@trentlaw.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.trentlaw.co.uk/employment-law",
        "source": "Public website",
        "source_url": "https://www.trentlaw.co.uk/employment-law",
        "notes": "Employment law services primarily for employers, with offices including Sheffield.",
    },
    {
        "company_name": "Taylor Emmet",
        "segment": "Employment Law",
        "subtype": "Employment law and HR support",
        "city_region": "Sheffield",
        "phone": "0114 218 4320",
        "website_url": "https://www.tayloremmet.co.uk/business/employment-law/",
        "source": "Public website",
        "source_url": "https://www.tayloremmet.co.uk/business/employment-law/",
        "notes": "Sheffield employment team providing outsourced employment and HR support through TE HR Assist.",
    },
    {
        "company_name": "Wake Smith Solicitors",
        "segment": "Employment Law",
        "subtype": "Employment law and HR services",
        "city_region": "Sheffield",
        "website_url": "https://www.wake-smith.co.uk/",
        "decision_maker_name": "Charlotte Wallage",
        "decision_maker_role": "Solicitor in Employment Law & HR Services",
        "source": "Public website",
        "source_url": "https://www.wake-smith.co.uk/",
        "notes": "Sheffield solicitors with employment law and HR services; site names Charlotte Wallage in employment law.",
    },
    {
        "company_name": "Analysis Legal",
        "segment": "Employment Law",
        "subtype": "Niche employment law practice",
        "city_region": "Manchester / Stockport",
        "website_url": "https://analysislegal.co.uk/",
        "source": "Public website",
        "source_url": "https://analysislegal.co.uk/",
        "notes": "Niche employment law practice working with employers and senior individuals, including small businesses.",
    },
    {
        "company_name": "Stephensons Solicitors LLP",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Manchester / Greater Manchester",
        "website_url": "https://www.stephensons.co.uk/site/businesses/srvemployee/employment-law-solicitors-greater-manchester/",
        "source": "Public website",
        "source_url": "https://www.stephensons.co.uk/site/businesses/srvemployee/employment-law-solicitors-greater-manchester/",
        "notes": "Employment law solicitors for businesses of all sizes across Greater Manchester, including SMEs.",
    },
    {
        "company_name": "Garratts Solicitors",
        "segment": "Employment Law",
        "subtype": "Employment law for employers",
        "city_region": "Manchester / Oldham",
        "website_url": "https://www.garrattssolicitors.co.uk/business-legal-services/employment-law.html",
        "source": "Public website",
        "source_url": "https://www.garrattssolicitors.co.uk/business-legal-services/employment-law.html",
        "notes": "Business solicitors offering employment law advice and protection for employers in Manchester and Oldham.",
    },
    {
        "company_name": "EBS Law",
        "segment": "Employment Law",
        "subtype": "Employment law for employers",
        "city_region": "Sheffield",
        "phone": "01625 874400",
        "website_url": "https://www.ebslaw.co.uk/employment-law-solicitors-sheffield/",
        "decision_maker_name": "John Bloor",
        "source": "Public website",
        "source_url": "https://www.ebslaw.co.uk/employment-law-solicitors-sheffield/",
        "notes": "Employment law solicitors covering Sheffield for employers, business owners and managers.",
    },
    {
        "company_name": "Banner Jones Solicitors",
        "segment": "Employment Law",
        "subtype": "Employment law solicitors",
        "city_region": "Sheffield / Chesterfield",
        "website_url": "https://www.bannerjones.co.uk/you-your-family/services/employment-law",
        "source": "Public website",
        "source_url": "https://www.bannerjones.co.uk/you-your-family/services/employment-law",
        "notes": "Employment law specialists supporting Sheffield, Chesterfield, Dronfield and Mansfield.",
    },
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def read_rows() -> list[dict[str, str]]:
    if not PROSPECTS_PATH.exists():
        return []
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[dict[str, str]]) -> None:
    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def next_id(company_name: str, existing_ids: set[str]) -> str:
    base_id = slugify(company_name)
    index = 1
    while True:
        lead_id = f"{base_id}-{index:02d}"
        if lead_id not in existing_ids:
            return lead_id
        index += 1


def main() -> None:
    rows = read_rows()
    existing_ids = {row["lead_id"] for row in rows}
    existing_keys = {
        normalize(row.get("company_name", "")): row
        for row in rows
        if row.get("company_name")
    }

    added = 0
    updated = 0

    for prospect in SEED_PROSPECTS:
        key = normalize(prospect["company_name"])
        if key in existing_keys:
            row = existing_keys[key]
            for field, field_value in prospect.items():
                if field_value and not row.get(field):
                    row[field] = field_value
                    updated += 1
            continue

        row = {header: "" for header in HEADERS}
        row.update(prospect)
        row["lead_id"] = next_id(prospect["company_name"], existing_ids)
        row["status"] = "enriched" if row.get("website_url") or row.get("email") else "research_needed"
        rows.append(row)
        existing_ids.add(row["lead_id"])
        existing_keys[key] = row
        added += 1

    write_rows(rows)
    print(f"Added {added} rows; filled {updated} blank fields in existing rows.")


if __name__ == "__main__":
    main()
