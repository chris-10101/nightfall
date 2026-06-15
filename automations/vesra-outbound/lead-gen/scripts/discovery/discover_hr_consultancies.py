from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import re
import time
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"
TODAY = date.today().isoformat()

BING_RSS_URL = "https://www.bing.com/search?format=rss&q={query}"

SEARCH_CITIES = [
    "York",
    "Harrogate",
    "Leeds",
    "Bradford",
    "Wakefield",
    "Huddersfield",
    "Halifax",
    "Barnsley",
    "Sheffield",
    "Rotherham",
    "Doncaster",
    "Hull",
    "Middlesbrough",
    "Yarm",
    "Darlington",
    "Durham",
    "Newcastle upon Tyne",
    "Gateshead",
    "Sunderland",
    "Stockport",
    "Manchester",
    "Bury",
    "Bolton",
    "Oldham",
    "Preston",
    "Wigan",
    "Warrington",
    "Liverpool",
    "Chesterfield",
    "Nottingham",
    "Derby",
    "Lincoln",
    "Birmingham",
    "Coventry",
    "Leicester",
    "Northampton",
    "Milton Keynes",
    "Cambridge",
    "Norwich",
    "Ipswich",
    "Chelmsford",
    "London",
    "Reading",
    "Oxford",
    "Swindon",
    "Bristol",
    "Bath",
    "Gloucester",
    "Cheltenham",
    "Cardiff",
    "Swansea",
    "Exeter",
    "Plymouth",
    "Southampton",
    "Portsmouth",
    "Brighton",
    "Guildford",
    "Maidstone",
    "Canterbury",
    "Bournemouth",
    "Poole",
    "Belfast",
    "Edinburgh",
    "Glasgow",
    "Aberdeen",
    "Dundee",
    "Inverness",
    "Stirling",
    "Perth",
    "Wrexham",
    "Newport",
    "Shrewsbury",
    "Telford",
    "Stoke-on-Trent",
    "Stafford",
    "Worcester",
    "Hereford",
    "Carlisle",
    "Lancaster",
    "Blackpool",
    "Blackburn",
    "Burnley",
    "Rochdale",
    "Salford",
    "Chorley",
    "Crewe",
    "Macclesfield",
    "Altrincham",
    "Cheshire",
    "West Yorkshire",
    "South Yorkshire",
    "North Yorkshire",
    "East Yorkshire",
    "Lancashire",
    "Cheshire",
    "Midlands",
    "North East",
    "North West",
    "South East",
    "South West",
]

QUERY_PATTERNS = [
    '"HR consultancy" "{city}"',
    '"outsourced HR" "{city}"',
    '"retained HR support" "{city}"',
    '"HR support" "SMEs" "{city}"',
    '"HR support" "small business" "{city}"',
    '"HR consultants" "small business" "{city}"',
    '"HR consultant" "SME" "{city}"',
    '"human resources consultancy" "{city}"',
]

BLOCKED_DOMAINS = {
    "adp.com",
    "bbc.co.uk",
    "bbc.com",
    "brighthr.com",
    "bing.com",
    "cipd.org",
    "coursera.org",
    "facebook.com",
    "find-and-update.company-information.service.gov.uk",
    "google.com",
    "instagram.com",
    "linkedin.com",
    "maps.google.com",
    "twitter.com",
    "x.com",
    "history.com",
    "hrmagazine.co.uk",
    "peoplehr.com",
}

BLOCKED_DOMAIN_PARTS = {
    "192.com",
    "approvedbusiness",
    "bizseek",
    "businessmagnet",
    "checkcompany",
    "companycheck",
    "companiesintheuk",
    "cylex",
    "directory",
    "endole",
    "find-and-update",
    "find-open",
    "findtheneedle",
    "glassdoor",
    "indeed",
    "mimoji",
    "opencorporates",
    "recommendedcompany",
    "reviews",
    "thecompanycheck",
    "trustpilot",
    "wiza",
    "yell",
    "yelp",
    "reed",
    "totaljobs",
    "cv-library",
    "monster",
    "ziprecruiter",
}

HR_TERMS = {
    "employment law",
    "hr consultancy",
    "hr consultant",
    "hr consultants",
    "hr services",
    "hr support",
    "human resources consultancy",
    "outsourced hr",
    "people consultancy",
    "people management consultancy",
}

BAD_TITLE_TERMS = {
    "body for hr",
    "career",
    "course",
    "guide",
    "history",
    "job",
    "jobs",
    "login",
    "magazine",
    "payroll software",
    "salary",
    "software",
    "training course",
    "vacancies",
    "what is",
    "wikipedia",
    "recruitment agency",
    "recruiter",
}

GENERIC_NAME_TERMS = {
    "about",
    "best",
    "business",
    "consultancy",
    "consultants",
    "contact",
    "employment",
    "home",
    "hr",
    "human",
    "law",
    "management",
    "resources",
    "services",
    "support",
    "the",
    "uk",
}


def fetch_rss(query: str, timeout: int = 15) -> list[dict[str, str]]:
    request = Request(
        BING_RSS_URL.format(query=quote_plus(query)),
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Accept": "application/rss+xml,text/xml,application/xml,text/html",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        xml_text = response.read(1_200_000).decode("utf-8", errors="replace")

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    results = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        if link.startswith("http"):
            results.append(
                {
                    "title": clean_text(title),
                    "url": unescape(link.strip()),
                    "description": clean_text(description),
                }
            )
    return results


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def root_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"co", "org", "ac", "gov"} and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_blocked_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    if parsed.path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
        return True

    domain = root_domain(url)
    full_host = host(url)
    if domain in BLOCKED_DOMAINS or full_host in BLOCKED_DOMAINS:
        return True
    return any(part in domain or part in full_host for part in BLOCKED_DOMAIN_PARTS)


def is_hr_result(result: dict[str, str]) -> bool:
    haystack = f"{result['title']} {result['description']} {host(result['url'])}".lower()
    if not any(term in haystack for term in HR_TERMS):
        return False
    if any(term in result["title"].lower() for term in BAD_TITLE_TERMS):
        return False
    if "recruitment agency" in haystack and "hr consultancy" not in haystack and "outsourced hr" not in haystack:
        return False
    return True


def name_from_result(result: dict[str, str]) -> str:
    title = result["title"]
    parts = re.split(r"\s+[|–—-]\s+|\s*:\s*", title)
    candidates = []
    for part in parts:
        part = clean_company_name(part)
        if is_good_name(part):
            candidates.append(part)

    if candidates:
        return min(candidates, key=len)

    domain = root_domain(result["url"]).split(".", 1)[0]
    domain = re.sub(r"[-_]+", " ", domain)
    return clean_company_name(domain).title()


def clean_company_name(value: str) -> str:
    value = re.sub(r"\b(HR Consultancy|Human Resources Consultancy|Outsourced HR|HR Support)\b", "", value, flags=re.I)
    value = re.sub(r"\b(Leeds|York|Manchester|Sheffield|Newcastle|Bradford|Wakefield|Harrogate|Hull|Derby|Nottingham|Lincoln)\b", "", value, flags=re.I)
    value = re.sub(r"\b(Official Website|Home Page|Home)\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -|:,.")
    return value


def is_good_name(value: str) -> bool:
    lowered = value.lower()
    if len(value) < 3 or len(value) > 70:
        return False
    if any(term in lowered for term in ["best ", "top ", "near me", "consultants in", "services in"]):
        return False
    tokens = re.findall(r"[a-z0-9]+", lowered)
    useful_tokens = [token for token in tokens if token not in GENERIC_NAME_TERMS and len(token) > 2]
    return bool(useful_tokens)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


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
        score += 12
    if row.get("website_url"):
        score += 15
    if row.get("email"):
        score += 10
    if row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url"):
        score += 10
    if "small" in row.get("notes", "").lower() or "sme" in row.get("notes", "").lower():
        score += 15
    if row.get("estimated_headcount"):
        score += 10
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


def read_rows() -> list[dict[str, str]]:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[dict[str, str]]) -> None:
    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def discover(limit: int) -> list[dict[str, str]]:
    candidates = []
    seen_domains = set()

    for city in SEARCH_CITIES:
        for pattern in QUERY_PATTERNS:
            if len(candidates) >= limit:
                return candidates
            query = pattern.format(city=city)
            try:
                results = fetch_rss(query)
            except Exception:
                time.sleep(1.5)
                continue

            for result in results:
                if len(candidates) >= limit:
                    return candidates
                if is_blocked_url(result["url"]) or not is_hr_result(result):
                    continue
                domain = root_domain(result["url"])
                if domain in seen_domains:
                    continue
                company_name = name_from_result(result)
                if not is_good_name(company_name):
                    continue

                seen_domains.add(domain)
                subtype = "Outsourced HR / SME HR support"
                if "retained" in query.lower():
                    subtype = "Retained HR support"
                elif "outsourced" in query.lower():
                    subtype = "Outsourced HR"
                candidates.append(
                    {
                        "company_name": company_name,
                        "segment": "HR Consultancy",
                        "subtype": subtype,
                        "city_region": city,
                        "website_url": result["url"],
                        "source": "Bing RSS public search result",
                        "source_url": result["url"],
                        "notes": f"Discovered via query: {query}. Result title: {result['title']}",
                        "status": "enriched",
                        "last_researched_at": TODAY,
                    }
                )
            time.sleep(0.5)

    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover HR consultancy prospects from public search result RSS.")
    parser.add_argument("--target-total", type=int, default=300, help="Stop adding when prospects.csv reaches this row count.")
    parser.add_argument("--max-new", type=int, default=250, help="Maximum new rows to add in this run.")
    parser.add_argument("--timeout", type=int, default=8, help="Search request timeout in seconds.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between search requests.")
    args = parser.parse_args()

    rows = read_rows()
    existing_ids = {row["lead_id"] for row in rows}
    existing_names = {normalize(row["company_name"]) for row in rows}
    existing_domains = {root_domain(row["website_url"]) for row in rows if row.get("website_url")}

    needed = max(0, min(args.target_total - len(rows), args.max_new))
    if needed == 0:
        print("No rows needed.")
        return

    added = 0
    searched = 0
    seen_run_domains = set()

    for city in SEARCH_CITIES:
        for pattern in QUERY_PATTERNS:
            if added >= needed:
                write_rows(rows)
                print(f"Added {added} HR consultancy rows. Total rows: {len(rows)}", flush=True)
                return

            query = pattern.format(city=city)
            searched += 1
            try:
                results = fetch_rss(query, timeout=args.timeout)
            except Exception as exc:
                print(f"SKIP query={query!r} error={type(exc).__name__}", flush=True)
                time.sleep(args.sleep)
                continue

            query_added = 0
            for result in results:
                if added >= needed:
                    break
                if is_blocked_url(result["url"]) or not is_hr_result(result):
                    continue

                domain_key = root_domain(result["url"])
                if domain_key in existing_domains or domain_key in seen_run_domains:
                    continue

                company_name = name_from_result(result)
                if not is_good_name(company_name):
                    continue

                name_key = normalize(company_name)
                if name_key in existing_names:
                    continue

                subtype = "Outsourced HR / SME HR support"
                if "retained" in query.lower():
                    subtype = "Retained HR support"
                elif "outsourced" in query.lower():
                    subtype = "Outsourced HR"

                row = {header: "" for header in HEADERS}
                row.update(
                    {
                        "company_name": company_name,
                        "segment": "HR Consultancy",
                        "subtype": subtype,
                        "city_region": city,
                        "website_url": result["url"],
                        "source": "Bing RSS public search result",
                        "source_url": result["url"],
                        "notes": f"Discovered via query: {query}. Result title: {result['title']}",
                        "status": "enriched",
                        "last_researched_at": TODAY,
                    }
                )
                row["lead_id"] = next_id(row["company_name"], existing_ids)
                row["fit_score"], row["priority"] = score_row(row)

                rows.append(row)
                existing_ids.add(row["lead_id"])
                existing_names.add(name_key)
                existing_domains.add(domain_key)
                seen_run_domains.add(domain_key)
                added += 1
                query_added += 1

                if added % 10 == 0:
                    write_rows(rows)
                    print(f"Progress: added={added} total={len(rows)} searched={searched}", flush=True)

            if query_added:
                write_rows(rows)
                print(f"ADD query={query!r} added={query_added} total={len(rows)}", flush=True)
            time.sleep(args.sleep)

    write_rows(rows)
    print(f"Added {added} HR consultancy rows. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
