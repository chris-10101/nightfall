from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from imports.import_hr_consultancies import HEADERS


BASE_DIR = Path(__file__).resolve().parents[2]
PROSPECTS_PATH = BASE_DIR / "data" / "prospects.csv"
TODAY = date.today().isoformat()

SOURCES = [
    {
        "name": "The HR Dept",
        "sitemap": "https://www.hrdept.co.uk/sitemaps-1-section-licensees-1-sitemap.xml",
        "url_filter": "hrdept",
        "subtype": "Outsourced HR (franchise)",
    },
    {
        "name": "face2faceHR",
        "sitemap": "https://face2facehr.com/consultants-sitemap.xml",
        "url_filter": "face2face",
        "subtype": "Outsourced HR (franchise)",
    },
]


def read_rows() -> list[dict[str, str]]:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[dict[str, str]]) -> None:
    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def fetch_xml(url: str) -> ElementTree.Element:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=25) as response:
        return ElementTree.fromstring(response.read())


def sitemap_locs(url: str) -> list[str]:
    root = fetch_xml(url)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text or "" for loc in root.findall(".//sm:loc", ns)]


def slug_parts(url: str) -> list[str]:
    return [part for part in urlparse(url).path.split("/") if part]


def clean_location(value: str) -> str:
    value = re.sub(r"^hr-consultant-", "", value)
    value = re.sub(r"-+", " ", value).strip()
    value = re.sub(r"\b(nw|ne|sw|se)\b", lambda m: m.group(1).upper(), value)
    return value.title().replace(" And ", " and ")


def lead_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:42] or "lead"


def next_id(company_name: str, existing_ids: set[str]) -> str:
    base = lead_slug(company_name)
    index = 1
    while True:
        lead_id = f"{base}-{index:02d}"
        if lead_id not in existing_ids:
            return lead_id
        index += 1


def source_urls(source: dict[str, str]) -> list[str]:
    urls = []
    for url in sitemap_locs(source["sitemap"]):
        parts = slug_parts(url)
        if source["url_filter"] == "hrdept":
            if len(parts) == 1:
                urls.append(url)
        elif source["url_filter"] == "face2face":
            if len(parts) == 2 and parts[0] == "consultants" and parts[1].startswith("hr-consultant-"):
                urls.append(url)
    return sorted(set(urls))


def main() -> None:
    rows = read_rows()
    existing_ids = {row["lead_id"] for row in rows}
    existing_urls = {row.get("website_url", "").rstrip("/") for row in rows if row.get("website_url")}
    existing_names = {row.get("company_name", "").strip().lower() for row in rows}
    added = 0

    for source in SOURCES:
        for url in source_urls(source):
            clean_url = url.rstrip("/")
            if clean_url in existing_urls:
                continue

            location_slug = slug_parts(clean_url)[-1]
            location = clean_location(location_slug)
            company_name = f"{source['name']} {location}"
            if company_name.lower() in existing_names:
                continue

            row = {header: "" for header in HEADERS}
            row.update(
                {
                    "lead_id": next_id(company_name, existing_ids),
                    "company_name": company_name,
                    "segment": "HR Consultancy",
                    "subtype": source["subtype"],
                    "city_region": location,
                    "estimated_headcount": "2-50",
                    "website_url": clean_url,
                    "fit_score": "75",
                    "priority": "medium",
                    "status": "enriched",
                    "source": f"{source['name']} public sitemap",
                    "source_url": source["sitemap"],
                    "notes": f"Public {source['name']} location/consultant page. Requires manual ICP review for software/platform exclusions before sending.",
                    "last_researched_at": TODAY,
                }
            )
            rows.append(row)
            existing_ids.add(row["lead_id"])
            existing_urls.add(clean_url)
            existing_names.add(company_name.lower())
            added += 1

    write_rows(rows)
    print(f"Added {added} network location rows. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
