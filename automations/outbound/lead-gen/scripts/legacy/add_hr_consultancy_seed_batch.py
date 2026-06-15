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
    ("Lappin HR", "North Yorkshire", "https://lappinhr.co.uk/", "contact@lappinhr.co.uk", "Outsourced HR for start-up, small and growing businesses in Yorkshire and the North East."),
    ("OneSource HR", "Sheffield / Yorkshire", "https://www.onesourcehr.co.uk/outsourced-hr-support", "help@onesourcehr.co.uk", "Fixed-price outsourced HR support across Yorkshire."),
    ("HR People Hub", "Driffield / East Yorkshire", "https://hrpeople-hub.co.uk/", "hello@hrpeople-hub.co.uk", "Affordable expert HR support for small businesses and start-ups across Yorkshire."),
    ("Paveley HR Solutions", "Yorkshire", "https://www.paveleyhr.com/", "", "Outsourced HR support for SMEs, ad-hoc support and managed HR solutions."),
    ("Pennine HR", "Huddersfield", "https://penninehr.co.uk/", "", "Human resource consultancy in Huddersfield providing outsourced HR services across the North of England."),
    ("HR Circle", "UK / remote", "https://hrcircleuk.com/", "info@hrcircleuk.com", "Specialist HR for small businesses with managed HR support and projects."),
    ("Spark HR", "UK / digital and creative", "https://www.spark-hr.com/", "", "HR consultancy for digital, creative and tech businesses."),
    ("MY HR Consultancy", "UK", "https://www.myhrconsultancy.com/", "", "Flexible HR consultancy and retainers for SMEs."),
    ("HR Download", "Cheshire / Manchester", "https://www.hrdownload.co.uk/", "info@hrdownload.co.uk", "HR consultants in Cheshire and Manchester for growing businesses."),
    ("DaisyHR", "Bolton / Manchester / North West", "https://www.daisyhr.co.uk/", "", "Fractional HR directors and outsourced HR for North West SMEs."),
    ("P3PM", "Altrincham / Manchester", "https://www.p3pm.co.uk/", "", "Outsourced HR services for SMEs across Greater Manchester and the North West."),
    ("Accelerate HR", "Newcastle / North East", "https://acceleratehr.co.uk/", "", "Newcastle HR consultancy providing outsourced HR support to SMEs across the North East."),
    ("People Matters HR", "Bury / Manchester", "https://www.peoplemattershr.co.uk/", "", "Outsourced HR partner for UK SMEs from Bury and the North West."),
    ("LighterHR", "Manchester / North West", "https://lighterhr.co.uk/lp/hr-consultancy-manchester/", "", "HR consultancy services for Manchester businesses and SMEs."),
    ("Emberscale", "Manchester", "https://emberscale.com/uk-hr-serviced-areas/hr-services-manchester/", "", "HR consultancy and outsourcing services for startups and SMEs."),
    ("Hallidays HR", "Manchester / Stockport", "https://hallidayshr.co.uk/hr-consultancy-manchester/", "", "HR support for small businesses without in-house HR."),
    ("MIG HR Solutions", "Wigan / Bolton / Manchester", "https://www.mighrsolutions.co.uk/about-us/", "", "HR solutions for Greater Manchester organisations."),
    ("Loates HR Consultancy", "Derby / Nottingham / East Midlands", "https://loateshr.net/", "", "Outsourced HR and employment law consultancy for SMEs in Derby, Nottingham and East Midlands."),
    ("Wright People HR", "Nottingham", "https://www.wrightpeoplehr.com/locations/nottingham/", "", "Outsourced HR services for small and growing businesses across Nottinghamshire."),
    ("Jennetts HR Solutions", "Lincoln", "https://jennettshrsolutions.co.uk/", "info@jennettshrsolutions.co.uk", "Lincoln HR consultancy providing practical, flexible HR support."),
    ("Nuvo HR", "Derby / Nottingham", "https://nuvo.co.uk/hr/", "", "HR consultancy for SMEs and business growth."),
    ("Nectar HR", "Derby", "https://nectarhr.co.uk/hr-consultant-derby/", "hello@nectarhr.co.uk", "HR consultancy and HR services for Derby businesses."),
    ("Jam HR", "Nottingham / UK", "https://jam-hr.com/", "", "Independent HR consulting, outsourcing and employment law advice for small businesses."),
    ("Rico HR", "Warrington / North West", "https://www.ricohr.co.uk/", "hello@ricohr.co.uk", "Affordable HR support to small and medium-sized businesses."),
    ("Dekela HR Services", "North Wales / North West", "https://dekela.com/", "Hey@dekela.com", "HR retainers and HR services for small businesses across North Wales and North West England."),
    ("Privilege HR", "Liverpool", "https://privilegehr.co.uk/", "", "Outsourced HR services for SMEs from Liverpool."),
    ("186hr", "Preston / North West", "https://186hr.co.uk/about/", "", "Generalist HR consultancy based near Preston serving SMEs."),
    ("Inspire Excellence", "Warrington", "https://inspireexcellence.co.uk/faqs/", "", "HR, coaching and training consultancy near Warrington."),
    ("HPC", "Liverpool / North West", "https://hpc.uk.com/liverpool-hr-support/", "", "Boutique outsourced HR and health & safety consultancy."),
    ("Wurkplace", "Chester / Liverpool / Manchester", "https://wurkplace.co.uk/hr-support-services/hr-services/", "", "HR and health & safety outsourcing for SME businesses."),
    ("Employee Management Ltd", "Warrington", "https://employeemanagement.co.uk/services/hr-services/", "enquiries@employeemanagement.co.uk", "HR consultancy, outsourcing, advice, contracts and documentation."),
    ("Highridge HR", "Huddersfield / Yorkshire", "https://www.highridge-hr.co.uk/", "", "HR business partner support for SME businesses."),
    ("Impact HR", "Leeds / Huddersfield / Yorkshire", "https://impacthr.co.uk/impact-hub/news/a-new-chapter-for-hr-consultancy-in-leeds/", "hello@impacthr.co.uk", "HR consultancy supporting Northern SMEs; acquired Positive People HR."),
    ("Beanstalk HR", "Holmfirth / West Yorkshire", "https://beanstalkhr.com/hr-setup.html", "yvette.whitwam@beanstalkhr.com", "HR membership and consultancy support for small businesses and micro-employers."),
    ("Kea HR Solutions", "Rotherham / South Yorkshire", "https://kea-hr.co.uk/", "", "HR solutions for new, micro, small and medium businesses."),
    ("OutsourcedHR", "Darlington / North East", "https://www.outsourcedhrltd.co.uk", "", "North East HR consultancy delivering retained services and employer support for SMEs."),
    ("People Puzzles Yorkshire and North East", "Yorkshire / North East", "https://peoplepuzzles.co.uk/areas-covered/yorkshire-north-east-of-england/", "", "Fractional people directors supporting Yorkshire and North East businesses."),
    ("The HR Guru", "Hull / East Yorkshire", "https://www.thehrguru.co.uk", "", "Independent HR consultancy for small and medium businesses in Yorkshire."),
    ("cHRysos HR Solutions", "Hull", "https://www.chrysos.org.uk", "info@chrysos.org.uk", "HR training, CIPD programmes and SME HR support."),
    ("Cheviot HR", "Newcastle / North East", "http://www.cheviothr.co.uk", "", "Outsourced HR for SMEs with practical HR support and compliance."),
    ("Willow and Semp HR Consultancy", "Bawtry / Doncaster", "http://www.willowandsemp.co.uk", "", "HR advice and consultancy services from Bawtry, Doncaster."),
    ("Talentnest Solution", "Manchester", "https://www.talentnestsolution.com", "", "HR consulting and outsourcing services based in Manchester."),
    ("Breathing Space HR", "Leeds / West Yorkshire", "http://www.breathingspacehr.co.uk", "hello@breathingspacehr.co.uk", "Independent HR consultancy in Yorkshire supporting SMEs."),
    ("Spire HR Solutions", "Warrington / Cheshire", "https://spirehr.co.uk/", "info@spirehr.co.uk", "HR solutions in Warrington for SMEs and outsourced HR support."),
    ("Ashton People Solutions", "Chester / North Wales", "https://ashtonpeoplesolutions.co.uk/", "info@ashtonpeoplesolutions.co.uk", "Outsourced HR specialist based near Chester, supporting SMEs."),
    ("Ig-hr", "Chester", "https://www.ig-hr.co.uk/areas-we-cover/hr-consultant-chester", "", "HR consultant in Chester for small businesses and growing startups."),
    ("The HR Dept Wrexham & Chester", "Wrexham / Chester", "https://www.hrdept.co.uk/wrexham-chester/who-we-are/", "wrexches@hrdept.co.uk", "HR solutions for small businesses across Wrexham and Chester."),
    ("Turnstone HR", "Cumbria / Lancashire", "https://turnstonehr.com/", "info@turnstonehr.com", "HR consultancy supporting SME clients across Cumbria and the North West."),
    ("Employment Law Solutions", "Cheshire", "https://employmentlawsolutions.co.uk/sectors/hr-advice-in-cheshire/", "", "Outsourced HR consultancy and employment law advice for Cheshire SMEs."),
    ("KCA People", "Chester / North West", "https://kcapeople.co.uk/services/hr-solutions/", "", "HR outsourcing and consultancy services for SMEs."),
    ("HRall", "Liverpool", "http://www.hrall.co.uk", "hello@hrall.co.uk", "North West outsourced HR consultancy working with SMEs."),
    ("Realise HR", "Cumbria", "https://realisehr.co.uk/about/", "", "Cumbria-based HR, training and recruitment consultancy with outsourced HR support."),
    ("Davidson HR Associates", "Carlisle / Cumbria", "https://davidson-hr.co.uk/", "debbie@davidson-hr.co.uk", "HR consultancy, employment law support and HR Hub for SMEs."),
    ("Elcons Employment Law Consultants", "Sowerby Bridge / Halifax", "https://elcons.co.uk/hr-consultancy/", "info@elcons.co.uk", "HR consultancy and employment law support from Sowerby Bridge."),
    ("Meraki HR Solutions", "Kendal / Cumbria", "http://www.merakihr.com", "", "Outsourced HR for ambitious scale-ups with a Kendal location."),
    ("Simpl3 HR", "Rotherham", "https://www.bark.com/en/gb/b/simpl3-hr-ltd/pBQW6/", "", "Boutique outsourced HR consultancy based in Rotherham; source is directory listing."),
    ("Fields of Change", "North Lincolnshire / South Yorkshire", "https://directory.lincolnshirelive.co.uk/search/doncaster/human-resource-consultants", "", "Directory result: works with SME owners, leaders and managers in North Lincolnshire and South Yorkshire."),
    ("The HR Dept Wigan & St Helens", "Wigan / St Helens", "https://www.hrdept.co.uk/wigan-st-helens/who-we-are", "", "Local HR Dept branch supporting local companies with practical HR advice."),
    ("The HR Dept Trafford & Warrington", "Trafford / Warrington", "https://www.hrdept.co.uk/trafford-and-warrington/event/hr-for-non-hr-managers-one-day-workshop-2", "", "Award-winning HR consultancy business providing outsourced HR to SMEs."),
    ("The HR Dept Grimsby Lincoln & Doncaster", "Lincoln / Doncaster", "https://www.yell.com/biz/hr-dept-grimsby-lincoln-and-doncaster-grimsby-10232920/", "", "Directory result for local HR Dept branch covering Grimsby, Lincoln and Doncaster."),
    ("The HR Dept Newcastle, Durham & Northumberland North", "Newcastle / Durham / Northumberland", "https://www.hrdept.co.uk/newcastle-north-north-tyneside-northumberland/who-we-are/", "", "Local HR Dept branch supporting SMEs across Newcastle, Durham and Northumberland."),
    ("Stran HR", "Derby", "https://www.stranhr.co.uk/", "", "LinkedIn source: 2-10 employee HR consultancy providing bespoke HR management services."),
    ("PW Consulting", "Derby", "https://www.pwconsulting.uk/", "", "LinkedIn source: outsourced HR management service to SMEs across rail and engineering."),
    ("PersonalHR", "Manchester", "http://www.personalhr.net", "", "LinkedIn source: 2-10 employee strategic HR service accessible to SMEs."),
    ("MPCG HR & Recruitment", "Newcastle-under-Lyme / Staffordshire", "http://www.mpcg.co.uk", "", "LinkedIn source: 2-10 employee outsourced HR support and HR management services."),
    ("alphr", "Manchester / Stockport", "https://www.alphr.uk/", "", "LinkedIn source: 2-10 employee employment law and HR services."),
    ("CM HR Consulting", "Derby", "http://www.cmhrconsulting.com", "enquiries@cmhrconsulting.com", "LinkedIn source: 2-10 employee HR consultancy supporting SMEs, NGOs and INGOs."),
    ("MB Human Resources Consulting", "Redcar / Teesside", "http://www.mbhrconsulting.com", "", "LinkedIn source: 2-10 employee HR and organisational development consultancy."),
    ("House of Growth HR", "Leeds", "https://www.houseofgrowth.org", "", "LinkedIn source: 2-10 employee outsourced HR for founders and scaling businesses."),
    ("HR4You", "Derby / East Midlands", "http://www.hr4you.co.uk", "", "LinkedIn source: 2-10 employee HR support for SMEs in East Midlands and Central regions."),
    ("Averist HR Services", "Wigan / North West", "https://www.averist.co.uk/", "support@averist.co.uk", "LinkedIn source: 2-10 employee HR and employment law support for SMEs, CICs and charities."),
    ("Oculus HR", "Sunderland", "https://linktr.ee/oculushr", "", "LinkedIn source: 2-10 employee HR consultancy in Sunderland."),
    ("Crawford HR", "Barnsley", "http://www.crawfordHR.com", "", "LinkedIn source: 2-10 employee small HR consultancy based in Barnsley."),
    ("Enablement Group", "Hull / Doncaster", "https://www.enablementgroup.co.uk", "", "LinkedIn source: 2-10 employee consultancy providing HR, recruitment, L&D and H&S services."),
    ("Human - People & Culture", "Sheffield", "https://humanpeopleandculture.com", "", "LinkedIn source: 2-10 employee people and culture consultancy in Sheffield."),
    ("VIBE HR and Training", "Liverpool", "https://www.vibe-hr.co.uk", "", "LinkedIn source: 2-10 employee HR and training consultancy in Liverpool."),
    ("The HR Experts", "Sheffield", "http://www.thehrexperts.co.uk", "info@thehrexperts.co.uk", "LinkedIn source: 2-10 employee specialist HR consultancy in Sheffield."),
    ("Clario", "Sheffield", "https://www.clario-services.co.uk", "", "LinkedIn source: 2-10 employee professional services firm offering HR support for SMEs."),
    ("ourHRpeople", "Chester / Liverpool / Knutsford", "https://www.ourhrpeople.co.uk/", "", "LinkedIn source: 2-10 employee HR consultancy/franchise with North West locations."),
]


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def root_domain(url: str) -> str:
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
    if "small" in row.get("notes", "").lower() or "sme" in row.get("notes", "").lower():
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


def main() -> None:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    existing_ids = {row["lead_id"] for row in rows}
    existing_names = {normalize(row["company_name"]) for row in rows}
    existing_domains = {root_domain(row["website_url"]) for row in rows if row.get("website_url")}

    added = 0
    skipped = 0

    for company_name, city_region, website_url, email, notes in SEED_ROWS:
        name_key = normalize(company_name)
        domain_key = root_domain(website_url)
        if name_key in existing_names or domain_key in existing_domains:
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
                "email_type": "generic" if email and email.split("@", 1)[0].lower() in {"hello", "info", "contact", "help", "enquiries"} else ("named" if email else ""),
                "email_confidence": "high" if email else "",
                "email_source_url": website_url if email else "",
                "status": "ready_to_review" if email else "enriched",
                "source": "Curated public search result",
                "source_url": website_url,
                "notes": notes,
                "last_researched_at": TODAY,
            }
        )
        row["fit_score"], row["priority"] = score_row(row)

        rows.append(row)
        existing_ids.add(row["lead_id"])
        existing_names.add(name_key)
        existing_domains.add(domain_key)
        added += 1

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Added {added} rows; skipped {skipped} duplicates. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
