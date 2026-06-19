from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import re
import socket
import time
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from core.csv_store import read_csv, write_csv_atomic
from core.eligibility_rules import FREE_PERSONAL_DOMAINS
from core.monitoring import init_sentry
from core.paths import data_dir
from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = data_dir() / "prospects.csv"
socket.setdefaulttimeout(12)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/[^\s\"'<>]+", re.I)
ROLE_RE = re.compile(
    r"\b(founder|owner|managing director|director|partner|managing partner|"
    r"head of employment|head of employment law|principal consultant|"
    r"senior hr consultant|hr director)\b",
    re.I,
)
CONTACT_PATH_RE = re.compile(r"(contact|about|team|people|meet|who-we-are|our-team)", re.I)
GENERIC_EMAIL_PREFIXES = {
    "admin",
    "contact",
    "enquiries",
    "hello",
    "info",
    "mail",
    "office",
    "reception",
    "support",
}
BLOCKED_EMAIL_DOMAINS = {
    "example.com",
    "godaddy.com",
    "onmicrosoft.com",
    "sentry.wixpress.com",
    "wixpress.com",
}
BLOCKED_EMAIL_TLDS = {
    "gif",
    "jpg",
    "jpeg",
    "png",
    "svg",
    "webp",
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self.links.append(href)

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)


def read_rows() -> list[dict[str, str]]:
    return read_csv(PROSPECTS_PATH)


def write_rows(rows: list[dict[str, str]]) -> None:
    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)


def fetch(url: str, timeout: int = 8) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "VesraLeadResearch/1.0 (+local manual research workflow)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        return response.read(1_500_000).decode("utf-8", errors="replace")


def parse_page(html: str) -> tuple[str, list[str]]:
    parser = LinkParser()
    parser.feed(html)
    text = unescape(" ".join(parser.text_parts))
    text = re.sub(r"\s+", " ", text)
    return text, parser.links


def same_domain(base_url: str, candidate_url: str) -> bool:
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
    candidate_host = urlparse(candidate_url).netloc.lower().removeprefix("www.")
    return candidate_host == base_host


def candidate_pages(base_url: str, links: list[str], max_pages: int) -> list[str]:
    urls = [base_url]
    for link in links:
        absolute = urljoin(base_url, link)
        if not same_domain(base_url, absolute):
            continue
        parsed = urlparse(absolute)
        clean_url = parsed._replace(query="", fragment="").geturl()
        if CONTACT_PATH_RE.search(parsed.path) and clean_url not in urls:
            urls.append(clean_url)
    return urls[:max_pages]


def email_type(email: str) -> str:
    prefix = email.split("@", 1)[0].lower()
    return "generic" if prefix in GENERIC_EMAIL_PREFIXES else "named"


def is_valid_business_email(email: str) -> bool:
    if not EMAIL_RE.fullmatch(email):
        return False
    local_part, domain = email.lower().split("@", 1)
    domain_parts = domain.split(".")
    if domain in BLOCKED_EMAIL_DOMAINS:
        return False
    if domain in FREE_PERSONAL_DOMAINS:
        return False
    if domain_parts[-1] in BLOCKED_EMAIL_TLDS:
        return False
    if len(local_part) >= 24 and re.fullmatch(r"[a-f0-9]+", local_part):
        return False
    if len(local_part) >= 24 and re.fullmatch(r"[a-f0-9]+", local_part) and "bookwithme" in domain:
        return False
    if len(local_part) >= 24 and re.fullmatch(r"[a-f0-9]+", local_part) and domain == "face2facehr.com":
        return False
    if any(part in {"sentry", "wixpress", "static", "assets"} for part in domain_parts):
        return False
    return True


def priority(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "low"
    return "park"


def score_row(row: dict[str, str]) -> int:
    score = 0

    segment = row.get("segment", "").lower()
    if segment in {"hr consultancy", "accountancy", "employment law"}:
        score += 25

    city_region = row.get("city_region", "").lower()
    if any(city in city_region for city in ["york", "leeds", "harrogate", "wakefield", "bradford", "huddersfield"]):
        score += 15
    elif city_region:
        score += 10

    headcount = row.get("estimated_headcount", "").strip()
    if headcount:
        score += 15 if "<" in headcount or "1-" in headcount or "2-" in headcount or "11-" in headcount else 8
    elif "small" in row.get("notes", "").lower() or "family" in row.get("notes", "").lower() or "team of two" in row.get("notes", "").lower():
        score += 12

    if row.get("decision_maker_name") and row.get("decision_maker_role"):
        score += 15
    elif row.get("decision_maker_name") or row.get("decision_maker_role"):
        score += 8

    notes = row.get("notes", "").lower()
    if any(term in notes for term in ["sme", "small business", "payroll", "outsourced", "employer", "advisory", "family-run"]):
        score += 20
    elif notes:
        score += 10

    if row.get("decision_maker_linkedin_url") and row.get("email"):
        score += 10
    elif row.get("email") or row.get("company_linkedin_url"):
        score += 7
    elif row.get("website_url"):
        score += 3

    return min(score, 100)


def best_email(emails: set[str]) -> str:
    valid_emails = {email for email in emails if is_valid_business_email(email)}
    if not valid_emails:
        return ""
    sorted_emails = sorted(valid_emails, key=lambda item: (email_type(item) == "generic", item))
    return sorted_emails[0]


def emails_from_links(links: list[str]) -> set[str]:
    emails: set[str] = set()
    for link in links:
        decoded = unquote(link)
        if decoded.lower().startswith("mailto:"):
            decoded = decoded.split(":", 1)[1].split("?", 1)[0]
        emails.update(email.strip(".,;:") for email in EMAIL_RE.findall(decoded))
    return emails


def enrich_row(row: dict[str, str], max_pages: int, timeout: int) -> bool:
    website_url = row.get("website_url", "").strip()
    if not website_url:
        return False

    changed = False
    if row.get("email") and not is_valid_business_email(row["email"]):
        row["email"] = ""
        row["email_type"] = ""
        row["email_confidence"] = ""
        row["email_source_url"] = ""
        changed = True

    pages_seen = []
    emails: set[str] = set()
    linkedin_urls: set[str] = set()

    try:
        homepage_html = fetch(website_url, timeout=timeout)
    except Exception as exc:
        row["notes"] = append_note(row.get("notes", ""), f"Website fetch failed: {type(exc).__name__}")
        return True

    homepage_text, links = parse_page(homepage_html)
    all_links = list(links)
    pages = candidate_pages(website_url, links, max_pages)
    page_texts = [(website_url, homepage_text)]

    for page_url in pages[1:]:
        try:
            page_html = fetch(page_url, timeout=timeout)
        except Exception:
            continue
        page_text, page_links = parse_page(page_html)
        page_texts.append((page_url, page_text))
        links.extend(page_links)
        all_links.extend(page_links)
        time.sleep(0.2)

    for page_url, text in page_texts:
        pages_seen.append(page_url)
        emails.update(email.strip(".,;:") for email in EMAIL_RE.findall(text))
        linkedin_urls.update(url.rstrip(".,;:)/") for url in LINKEDIN_RE.findall(text))
    emails.update(emails_from_links(all_links))

    if not row.get("email"):
        email = best_email(emails)
        if email:
            row["email"] = email
            row["email_type"] = email_type(email)
            row["email_confidence"] = "high"
            row["email_source_url"] = pages_seen[0]
            changed = True

    if not row.get("company_linkedin_url"):
        company_linkedin = next((url for url in sorted(linkedin_urls) if "/company/" in url), "")
        if company_linkedin:
            row["company_linkedin_url"] = company_linkedin
            row["linkedin_source_url"] = pages_seen[0]
            changed = True

    if not row.get("decision_maker_linkedin_url"):
        person_linkedin = next((url for url in sorted(linkedin_urls) if "/in/" in url), "")
        if person_linkedin:
            row["decision_maker_linkedin_url"] = person_linkedin
            row["linkedin_source_url"] = pages_seen[0]
            changed = True

    if not row.get("decision_maker_role"):
        for _, text in page_texts:
            match = ROLE_RE.search(text)
            if match:
                row["decision_maker_role"] = match.group(0)
                changed = True
                break

    row["last_researched_at"] = date.today().isoformat()
    row["fit_score"] = str(score_row(row))
    row["priority"] = priority(int(row["fit_score"]))
    if row["fit_score"] and int(row["fit_score"]) >= 60:
        row["status"] = "ready_to_review" if row.get("email") or row.get("decision_maker_linkedin_url") else "enriched"
    changed = True

    return changed


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


def main() -> None:
    init_sentry("daily-enrichment-public-web")
    parser = argparse.ArgumentParser(description="Enrich prospect rows from public company websites.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows to attempt in this run.")
    parser.add_argument("--max-pages", type=int, default=3, help="Maximum public pages to fetch per company.")
    parser.add_argument("--only-missing-email", action="store_true", help="Skip rows that already have an email.")
    parser.add_argument("--timeout", type=int, default=8, help="Per-page fetch timeout in seconds.")
    parser.add_argument("--checkpoint", action="store_true", help="Write prospects.csv after each changed row.")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many eligible rows before attempting enrichment.")
    args = parser.parse_args()

    rows = read_rows()
    attempted = 0
    changed = 0

    eligible_rows = [
        row
        for row in rows
        if row.get("website_url") and not (args.only_missing_email and row.get("email"))
    ]

    for row in eligible_rows[args.offset:]:
        if attempted >= args.limit:
            break

        attempted += 1
        if enrich_row(row, max_pages=args.max_pages, timeout=args.timeout):
            changed += 1
            if args.checkpoint:
                write_rows(rows)
                print(f"Progress: attempted={attempted} updated={changed}", flush=True)
        time.sleep(0.5)

    write_rows(rows)
    print(f"Attempted {attempted} rows; updated {changed} rows.")


if __name__ == "__main__":
    main()
