from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import re
import time
from datetime import date
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from core.csv_store import read_csv, write_csv_atomic
from imports.import_hr_consultancies import HEADERS


BASE_DIR = Path(__file__).resolve().parents[2]
PROSPECTS_PATH = BASE_DIR / "data" / "prospects.csv"
TODAY = date.today().isoformat()
OFFICERS_URL = "https://find-and-update.company-information.service.gov.uk/company/{company_number}/officers"
COMPANY_NUMBER_RE = re.compile(r"Company number ([A-Z0-9]{8})", re.I)

ROLE_PRIORITY = {
    "director": 0,
    "managing director": 0,
    "secretary": 5,
}


def fetch_officers_page(company_number: str, timeout: int) -> str:
    request = Request(
        OFFICERS_URL.format(company_number=company_number),
        headers={
            "User-Agent": "VesraLeadResearch/1.0 (+source-backed Companies House enrichment)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(1_500_000).decode("utf-8", errors="replace")


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def company_number(row: dict[str, str]) -> str:
    match = COMPANY_NUMBER_RE.search(row.get("notes", ""))
    return match.group(1).upper() if match else ""


def parse_officers(html: str) -> list[dict[str, str]]:
    officers = []
    blocks = re.findall(r'<div class="appointment-\d+">(.*?)(?=<div class="appointment-\d+">|</div>\s*</div>\s*</div>|</main>)', html, re.I | re.S)
    if not blocks:
        blocks = re.findall(r'<span id="officer-name-(\d+)">(.*?)</span>.*?<dd id="officer-role-\1" class="data">(.*?)</dd>', html, re.I | re.S)
        for index, raw_name, raw_role in blocks:
            status_match = re.search(rf'id="officer-status-tag-{index}"[^>]*>(.*?)</span>', html, re.I | re.S)
            status = clean_html(status_match.group(1)) if status_match else ""
            officers.append(
                {
                    "name": normalize_name(clean_html(raw_name)),
                    "role": clean_html(raw_role),
                    "status": status,
                }
            )
        return officers

    for block in blocks:
        name_match = re.search(r'<span id="officer-name-\d+">(.*?)</span>', block, re.I | re.S)
        role_match = re.search(r'<dd id="officer-role-\d+" class="data">(.*?)</dd>', block, re.I | re.S)
        status_match = re.search(r'id="officer-status-tag-\d+"[^>]*>(.*?)</span>', block, re.I | re.S)
        if not name_match or not role_match:
            continue
        officers.append(
            {
                "name": normalize_name(clean_html(name_match.group(1))),
                "role": clean_html(role_match.group(1)),
                "status": clean_html(status_match.group(1)) if status_match else "",
            }
        )
    return officers


def normalize_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if "," not in value:
        return title_name(value)
    surname, given = [part.strip() for part in value.split(",", 1)]
    return title_name(f"{given} {surname}")


def title_name(value: str) -> str:
    particles = {"de", "del", "van", "von", "der", "of", "and"}
    parts = []
    for part in value.split():
        lower = part.lower()
        if lower in particles:
            parts.append(lower)
        elif "-" in part:
            parts.append("-".join(piece.capitalize() for piece in lower.split("-")))
        else:
            parts.append(lower.capitalize())
    return " ".join(parts)


def best_officer(officers: list[dict[str, str]]) -> dict[str, str]:
    active = [officer for officer in officers if officer["name"] and officer["role"] and officer.get("status", "").lower() != "resigned"]
    if not active:
        return {}
    active.sort(key=lambda officer: (ROLE_PRIORITY.get(officer["role"].lower(), 3), officer["name"]))
    return active[0]


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


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
        return str(score), "high"
    if score >= 60:
        return str(score), "medium"
    if score >= 40:
        return str(score), "low"
    return str(score), "park"


def enrich_row(row: dict[str, str], timeout: int) -> bool:
    number = company_number(row)
    if not number:
        return False
    if row.get("decision_maker_name") and row.get("decision_maker_role"):
        return False

    source_url = OFFICERS_URL.format(company_number=number)
    html = fetch_officers_page(number, timeout=timeout)
    officer = best_officer(parse_officers(html))
    if not officer:
        row["notes"] = append_note(row.get("notes", ""), f"Companies House officers checked; no active officer parsed: {source_url}")
        row["last_researched_at"] = TODAY
        return True

    changed = False
    if not row.get("decision_maker_name"):
        row["decision_maker_name"] = officer["name"]
        changed = True
    if not row.get("decision_maker_role"):
        row["decision_maker_role"] = officer["role"]
        changed = True
    row["notes"] = append_note(
        row.get("notes", ""),
        f"Companies House active officer: {officer['name']} ({officer['role']}); source: {source_url}",
    )
    row["last_researched_at"] = TODAY
    row["fit_score"], row["priority"] = score_priority(row)
    if row.get("website_url") and (row.get("email") or row.get("decision_maker_name")):
        row["status"] = "ready_to_review"
    elif row.get("website_url"):
        row["status"] = "enriched"
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Companies House rows with source-backed active officer names.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--checkpoint", action="store_true")
    args = parser.parse_args()

    rows = read_csv(PROSPECTS_PATH)
    eligible = [
        row
        for row in rows
        if row.get("source") == "Companies House public company search"
        and company_number(row)
        and not (row.get("decision_maker_name") and row.get("decision_maker_role"))
    ]

    attempted = 0
    changed = 0
    for row in eligible[args.offset:]:
        if attempted >= args.limit:
            break
        attempted += 1
        try:
            if enrich_row(row, timeout=args.timeout):
                changed += 1
                if args.checkpoint:
                    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
                    print(f"Progress: attempted={attempted} updated={changed}", flush=True)
        except Exception as exc:
            row["notes"] = append_note(row.get("notes", ""), f"Companies House officer fetch failed: {type(exc).__name__}")
            row["last_researched_at"] = TODAY
            changed += 1
            if args.checkpoint:
                write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
                print(f"Progress: attempted={attempted} updated={changed}", flush=True)
        time.sleep(0.3)

    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    print(f"Attempted {attempted} rows; updated {changed} rows.")


if __name__ == "__main__":
    main()
