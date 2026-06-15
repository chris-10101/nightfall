from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import re
import time
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.csv_store import read_csv, write_csv_atomic
from imports.import_hr_consultancies import HEADERS


BASE_DIR = Path(__file__).resolve().parents[2]
PROSPECTS_PATH = BASE_DIR / "data" / "prospects.csv"
TODAY = date.today().isoformat()

GENERIC_TOKENS = {
    "advice",
    "advisory",
    "and",
    "business",
    "bureau",
    "co",
    "company",
    "consultancy",
    "consultancies",
    "consultant",
    "consultants",
    "consulting",
    "group",
    "human",
    "limited",
    "ltd",
    "management",
    "od",
    "people",
    "resource",
    "resources",
    "service",
    "services",
    "solutions",
    "support",
    "the",
    "uk",
}

HR_SIGNALS = (
    "hr consultancy",
    "hr consultant",
    "hr consultants",
    "hr support",
    "hr services",
    "hr advice",
    "human resources",
    "employment law",
    "employee relations",
    "outsourced hr",
    "retained hr",
    "people consultancy",
    "people management",
    "workplace",
)

HARD_BAD_ROOTS = {
    "acorninsure.co.uk",
    "ajbell.co.uk",
    "aim-group.org.uk",
    "alpha.org",
    "associatedlead.co.uk",
    "bbc.co.uk",
    "bbcollab.com",
    "biblestudytools.com",
    "blackboard.com",
    "breakintoenglish.com",
    "climate.gov",
    "creativebooster.net",
    "dailyrecord.co.uk",
    "englandnetball.co.uk",
    "formula1.com",
    "global.weir",
    "healthline.com",
    "investopedia.com",
    "managementstudyguide.com",
    "mercedes-benz.co.uk",
    "microsoft.com",
    "newsweek.com",
    "nhs.uk",
    "rhs.org.uk",
    "rspb.org.uk",
    "sec.gov",
    "sheffieldcitycentre.com",
    "themortgagelender.com",
    "vocabulary.com",
    "webmd.com",
    "wikihow.com",
}


def fetch_page(url: str, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "VesraLeadResearch/1.0 (+source-backed website validation)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return ""
        return response.read(600_000).decode("utf-8", errors="replace")


def clean_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip().lower()


def root_domain(value: str) -> str:
    host = urlparse(value).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "org", "ac", "gov"}:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def company_tokens(company_name: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[a-z0-9]+", company_name.lower()):
        if len(token) >= 3 and token not in GENERIC_TOKENS and token != "hr":
            tokens.append(token)
    return tokens


def has_brand_match(company_name: str, url: str, text: str) -> bool:
    domain_stem = root_domain(url).split(".", 1)[0]
    tokens = company_tokens(company_name)
    if not tokens:
        return False
    return any(token in domain_stem or domain_stem in token or re.search(rf"\b{re.escape(token)}\b", text) for token in tokens)


def has_hr_signal(text: str) -> bool:
    return any(signal in text for signal in HR_SIGNALS)


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


def clear_website_and_email(row: dict[str, str], reason: str) -> None:
    website_url = row.get("website_url", "")
    email = row.get("email", "")
    row["notes"] = append_note(row.get("notes", ""), f"Removed unvalidated Companies House website/email enrichment: {reason}")
    row["website_url"] = ""
    if row.get("source_url") == website_url:
        row["source_url"] = ""
    if email:
        row["email"] = ""
        row["email_type"] = ""
        row["email_confidence"] = ""
        row["email_source_url"] = ""
    row["status"] = "research_needed"
    row["fit_score"], row["priority"] = score_priority(row)
    row["last_researched_at"] = TODAY


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


def validate_row(row: dict[str, str], timeout: int) -> str:
    url = row.get("website_url", "").strip()
    if not url:
        return "skipped"
    root = root_domain(url)
    if root in HARD_BAD_ROOTS:
        clear_website_and_email(row, f"known unrelated domain {root}")
        return "cleared"

    try:
        html = fetch_page(url, timeout=timeout)
    except Exception as exc:
        clear_website_and_email(row, f"website fetch failed for {url}: {type(exc).__name__}")
        return "cleared"

    text = clean_html(html)
    if not text:
        clear_website_and_email(row, f"non-html or empty website content for {url}")
        return "cleared"
    if not has_brand_match(row.get("company_name", ""), url, text):
        clear_website_and_email(row, f"no brand match for {row.get('company_name', '')} at {url}")
        return "cleared"
    if not has_hr_signal(text):
        clear_website_and_email(row, f"no HR consultancy signal found at {url}")
        return "cleared"

    row["notes"] = append_note(row.get("notes", ""), f"Validated Companies House website against HR consultancy signal: {url}")
    row["last_researched_at"] = TODAY
    row["fit_score"], row["priority"] = score_priority(row)
    return "kept"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate noisy Companies House website/email enrichments before outreach.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--checkpoint", action="store_true")
    args = parser.parse_args()

    rows = read_csv(PROSPECTS_PATH)
    eligible = [
        row
        for row in rows
        if row.get("source") == "Companies House public company search" and row.get("website_url")
    ]

    attempted = 0
    counts = {"kept": 0, "cleared": 0, "skipped": 0}
    for row in eligible:
        if attempted >= args.limit:
            break
        attempted += 1
        result = validate_row(row, timeout=args.timeout)
        counts[result] += 1
        if args.checkpoint:
            write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
            print(f"Progress: attempted={attempted} kept={counts['kept']} cleared={counts['cleared']}", flush=True)
        time.sleep(0.2)

    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    print(f"Attempted {attempted}; kept {counts['kept']}; cleared {counts['cleared']}; skipped {counts['skipped']}.")


if __name__ == "__main__":
    main()
