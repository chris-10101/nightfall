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
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from imports.import_hr_consultancies import HEADERS


BASE_DIR = Path(__file__).resolve().parents[2]
PROSPECTS_PATH = BASE_DIR / "data" / "prospects.csv"
TODAY = date.today().isoformat()
SEARCH_URL = "https://find-and-update.company-information.service.gov.uk/search/companies?q={query}&page={page}"
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.I)

SEARCH_TERMS = [
    "HR Consultancy",
    "HR Consultants",
    "HR Consulting",
    "HR Support",
    "HR Services",
    "Human Resources Consultancy",
    "Human Resources Consultants",
    "Human Resources Support",
    "Outsourced HR",
    "Retained HR",
    "People Consultancy HR",
    "Employee Relations Consultancy",
]

EXCLUDE_NAME_TERMS = {
    "accounts",
    "accountancy",
    "construction",
    "financial",
    "finance",
    "investment",
    "property",
    "recruitment",
    "software",
    "training",
}


def read_rows() -> list[dict[str, str]]:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[dict[str, str]]) -> None:
    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def fetch_page(query: str, page: int, timeout: int) -> str:
    url = SEARCH_URL.format(query=quote_plus(query), page=page)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def parse_results(html: str) -> list[dict[str, str]]:
    items = re.findall(r'<li class="type-company">(.*?)</li>', html, flags=re.I | re.S)
    results = []
    for item in items:
        link_match = re.search(r'<a[^>]+href="(/company/([^"]+))"[^>]*>(.*?)</a>', item, flags=re.I | re.S)
        meta_match = re.search(r'<p class="meta crumbtrail">\s*(.*?)\s*</p>', item, flags=re.I | re.S)
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", item, flags=re.I | re.S)
        if not link_match or not meta_match:
            continue
        address = ""
        if paragraphs:
            address = clean_text(paragraphs[-1])
            if "Matching previous names" in address:
                address = ""
        results.append(
            {
                "url": "https://find-and-update.company-information.service.gov.uk" + link_match.group(1),
                "company_number": link_match.group(2).strip(),
                "company_name": clean_text(link_match.group(3)),
                "meta": clean_text(meta_match.group(1)),
                "address": address,
            }
        )
    return results


def is_probable_hr_company(result: dict[str, str]) -> bool:
    name = result["company_name"].lower()
    meta = result["meta"].lower()
    if "dissolved" in meta:
        return False
    if "liquidation" in meta:
        return False
    if any(term in name for term in EXCLUDE_NAME_TERMS):
        return False
    has_hr_term = (
        re.search(r"\bhr\b", name)
        or "h.r." in name
        or "human resources" in name
        or ("people" in name and ("consult" in name or "support" in name or "services" in name))
        or "employee relations" in name
    )
    has_service_term = any(term in name for term in ["consult", "support", "service", "advis", "outsourc", "people"])
    return bool(has_hr_term and has_service_term)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def next_id(company_name: str, company_number: str, existing_ids: set[str]) -> str:
    base = slugify(f"{company_name}-{company_number}")
    candidate = base
    index = 1
    while candidate in existing_ids:
        index += 1
        candidate = f"{base[:38]}-{index:02d}"
    return candidate


def extract_postcode(address: str) -> str:
    match = POSTCODE_RE.search(address)
    return match.group(1).upper() if match else ""


def extract_city(address: str) -> str:
    postcode = extract_postcode(address)
    trimmed = address
    if postcode:
        trimmed = address[: address.upper().find(postcode)]
    parts = [part.strip() for part in trimmed.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return parts[0] if parts else "UK"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import source-backed HR consultancy company names from Companies House search.")
    parser.add_argument("--target-total", type=int, default=500)
    parser.add_argument("--max-pages-per-term", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()

    rows = read_rows()
    existing_ids = {row["lead_id"] for row in rows}
    existing_names = {row["company_name"].strip().lower() for row in rows}
    existing_source_urls = {row.get("source_url", "") for row in rows if row.get("source_url")}
    added = 0

    for term in SEARCH_TERMS:
        for page in range(1, args.max_pages_per_term + 1):
            if len(rows) >= args.target_total:
                write_rows(rows)
                print(f"Added {added} Companies House rows. Total rows: {len(rows)}")
                return

            try:
                html = fetch_page(term, page, args.timeout)
            except Exception as exc:
                print(f"SKIP term={term!r} page={page} error={type(exc).__name__}", flush=True)
                time.sleep(args.sleep)
                continue

            page_added = 0
            for result in parse_results(html):
                if len(rows) >= args.target_total:
                    break
                name_key = result["company_name"].strip().lower()
                if name_key in existing_names or result["url"] in existing_source_urls:
                    continue
                if not is_probable_hr_company(result):
                    continue

                company_number = result["company_number"]
                row = {header: "" for header in HEADERS}
                row.update(
                    {
                        "lead_id": next_id(result["company_name"], company_number, existing_ids),
                        "company_name": result["company_name"].title(),
                        "segment": "HR Consultancy",
                        "subtype": "HR consultancy / Companies House research needed",
                        "address": result["address"],
                        "city_region": extract_city(result["address"]),
                        "postcode": extract_postcode(result["address"]),
                        "estimated_headcount": "unknown",
                        "fit_score": "45",
                        "priority": "low",
                        "status": "research_needed",
                        "source": "Companies House public company search",
                        "source_url": result["url"],
                        "notes": f"Companies House result for query '{term}'. Company number {company_number}. {result['meta']}. Needs website, contact, client-model, and software-platform review before outreach.",
                        "last_researched_at": TODAY,
                    }
                )
                rows.append(row)
                existing_ids.add(row["lead_id"])
                existing_names.add(name_key)
                existing_source_urls.add(result["url"])
                added += 1
                page_added += 1

            if page_added:
                write_rows(rows)
                print(f"ADD term={term!r} page={page} added={page_added} total={len(rows)}", flush=True)
            time.sleep(args.sleep)

    write_rows(rows)
    print(f"Added {added} Companies House rows. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
