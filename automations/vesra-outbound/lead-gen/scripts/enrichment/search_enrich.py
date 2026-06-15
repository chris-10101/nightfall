from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import re
import time
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from core.csv_store import read_csv, write_csv_atomic
from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"
SEARCH_URL = "https://duckduckgo.com/html/?q={query}"
BING_SEARCH_URL = "https://www.bing.com/search?format=rss&q={query}"

BLOCKED_WEBSITE_DOMAINS = {
    "bing.com",
    "companycheck.co.uk",
    "companieshouse.gov.uk",
    "duckduckgo.com",
    "facebook.com",
    "find-and-update.company-information.service.gov.uk",
    "google.com",
    "hrmagazine.co.uk",
    "instagram.com",
    "linkedin.com",
    "maps.apple.com",
    "maps.google.com",
    "merriam-webster.com",
    "peoplehr.com",
    "personneltoday.com",
    "twitter.com",
    "x.com",
    "yell.com",
    "wikipedia.org",
}
BLOCKED_DOMAIN_PARTS = {
    "192.com",
    "bizify",
    "checkcompany",
    "cylex",
    "dictionary",
    "directory",
    "find-open",
    "glassdoor",
    "hrmagazine",
    "indeed",
    "merriam-webster",
    "opencorporates",
    "personneltoday",
    "reviews",
    "thegazette",
    "thefreedictionary",
    "trustpilot",
    "wikipedia",
    "yelp",
}
GENERIC_COMPANY_WORDS = {
    "accountancy",
    "accountants",
    "and",
    "co",
    "company",
    "consultancy",
    "consultants",
    "employment",
    "hr",
    "law",
    "limited",
    "llp",
    "ltd",
    "services",
    "solicitors",
    "support",
    "the",
    "uk",
}


class SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_link = False
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")
        href = attrs_dict.get("href", "")
        if "result__a" in class_name or href.startswith("/l/?") or "uddg=" in href:
            self._in_link = True
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._in_link:
            return
        href = decode_duckduckgo_href(self._href)
        title = re.sub(r"\s+", " ", unescape(" ".join(self._text))).strip()
        if href and title:
            self.results.append({"url": href, "title": title})
        self._in_link = False
        self._href = ""
        self._text = []


def decode_duckduckgo_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/l/?") or "duckduckgo.com/l/?" in href:
        query = urlparse(href).query
        uddg = parse_qs(query).get("uddg", [""])[0]
        return unquote(uddg)
    return href


def read_rows() -> list[dict[str, str]]:
    return read_csv(PROSPECTS_PATH)


def write_rows(rows: list[dict[str, str]]) -> None:
    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)


def fetch_html(url: str, timeout: int = 15) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(1_500_000).decode("utf-8", errors="replace")


def parse_bing_results(html: str) -> list[dict[str, str]]:
    if html.lstrip().startswith("<?xml") or "<rss" in html[:200]:
        return parse_bing_rss_results(html)

    results = []
    pattern = re.compile(
        r'<li[^>]+class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?<h2[^>]*>\s*'
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.I | re.S,
    )
    for href, raw_title in pattern.findall(html):
        title = re.sub(r"<[^>]+>", " ", raw_title)
        title = re.sub(r"\s+", " ", unescape(title)).strip()
        url = unescape(href)
        if title and url.startswith("http"):
            results.append({"url": url, "title": title})
    return results


def parse_bing_rss_results(xml_text: str) -> list[dict[str, str]]:
    results = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return results
    for item in root.findall("./channel/item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        if link.startswith("http"):
            results.append(
                {
                    "url": unescape(link.strip()),
                    "title": re.sub(r"\s+", " ", unescape(f"{title} {description}")).strip(),
                }
            )
    return results


def parse_duckduckgo_results(html: str) -> list[dict[str, str]]:
    parser = SearchParser()
    parser.feed(html)
    return parser.results


def fetch_search(query: str, timeout: int = 15) -> list[dict[str, str]]:
    encoded_query = quote_plus(query)

    bing_html = fetch_html(BING_SEARCH_URL.format(query=encoded_query), timeout=timeout)
    results = parse_bing_results(bing_html)
    if results:
        return results

    duckduckgo_html = fetch_html(SEARCH_URL.format(query=encoded_query), timeout=timeout)
    return parse_duckduckgo_results(duckduckgo_html)


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def root_domain(url: str) -> str:
    parts = host(url).split(".")
    if len(parts) <= 2:
        return host(url)
    return ".".join(parts[-2:])


def clean_company_name(company_name: str) -> str:
    value = company_name.split("|", 1)[0]
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\b(HQ|Manchester|Leeds|York|Newcastle|Bradford|Sheffield)\b", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in GENERIC_COMPANY_WORDS
    ]


def is_blocked_website(url: str) -> bool:
    domain = root_domain(url)
    if domain in BLOCKED_WEBSITE_DOMAINS or host(url) in BLOCKED_WEBSITE_DOMAINS:
        return True
    return any(part in domain or part in host(url) for part in BLOCKED_DOMAIN_PARTS)


def is_company_website_candidate(row: dict[str, str], result: dict[str, str]) -> bool:
    url = result["url"]
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if is_blocked_website(url):
        return False

    company_tokens = tokens(clean_company_name(row["company_name"]))
    if not company_tokens:
        return False

    haystack = " ".join([host(url), result["title"]]).lower()
    matched = sum(1 for token in company_tokens if token in haystack)

    if matched >= min(2, len(company_tokens)):
        return True
    if len(company_tokens) == 1 and matched == 1:
        return True
    return False


def is_linkedin_candidate(row: dict[str, str], result: dict[str, str]) -> bool:
    url = result["url"]
    parsed = urlparse(url)
    if "linkedin.com" not in parsed.netloc.lower():
        return False
    if "/company/" not in parsed.path and "/in/" not in parsed.path:
        return False

    company_tokens = tokens(clean_company_name(row["company_name"]))
    decision_tokens = tokens(row.get("decision_maker_name", ""))
    haystack = " ".join([unquote(parsed.path), result["title"]]).lower()

    if "/company/" in parsed.path:
        return any(token in haystack for token in company_tokens)
    if decision_tokens:
        return all(token in haystack for token in decision_tokens[:2])
    return any(token in haystack for token in company_tokens)


def best_website(row: dict[str, str]) -> str:
    queries = [
        f'"{clean_company_name(row["company_name"])}" "{row.get("city_region", "")}" official website',
        f'"{clean_company_name(row["company_name"])}" "{row.get("segment", "")}"',
    ]
    for query in queries:
        for result in fetch_search(query):
            if is_company_website_candidate(row, result):
                return result["url"]
        time.sleep(0.4)
    return ""


def best_linkedin(row: dict[str, str]) -> tuple[str, str]:
    queries = [
        f'"{clean_company_name(row["company_name"])}" LinkedIn',
        f'"{clean_company_name(row["company_name"])}" site:linkedin.com/company',
    ]
    if row.get("decision_maker_name"):
        queries.insert(0, f'"{row["decision_maker_name"]}" "{clean_company_name(row["company_name"])}" site:linkedin.com/in')

    for query in queries:
        for result in fetch_search(query):
            if is_linkedin_candidate(row, result):
                path = urlparse(result["url"]).path
                field = "decision_maker_linkedin_url" if "/in/" in path else "company_linkedin_url"
                return field, result["url"]
        time.sleep(0.4)
    return "", ""


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


def enrich_row(row: dict[str, str], include_websites: bool, include_linkedin: bool) -> bool:
    changed = False

    if include_websites and not row.get("website_url"):
        try:
            website_url = best_website(row)
        except Exception as exc:
            row["notes"] = append_note(row.get("notes", ""), f"Search website failed: {type(exc).__name__}")
            website_url = ""
            changed = True
        if website_url:
            row["website_url"] = website_url
            if not row.get("source_url"):
                row["source_url"] = website_url
            changed = True

    if include_linkedin and not (row.get("company_linkedin_url") and row.get("decision_maker_linkedin_url")):
        try:
            field, linkedin_url = best_linkedin(row)
        except Exception as exc:
            row["notes"] = append_note(row.get("notes", ""), f"Search LinkedIn failed: {type(exc).__name__}")
            field, linkedin_url = "", ""
            changed = True
        if field and linkedin_url and not row.get(field):
            row[field] = linkedin_url
            row["linkedin_source_url"] = linkedin_url
            changed = True

    if changed:
        row["last_researched_at"] = date.today().isoformat()
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill missing websites and LinkedIn URLs from public search results.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows to attempt.")
    parser.add_argument("--websites-only", action="store_true")
    parser.add_argument("--linkedin-only", action="store_true")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many eligible rows before attempting enrichment.")
    parser.add_argument("--checkpoint", action="store_true", help="Write prospects.csv after each changed row.")
    parser.add_argument("--debug-query", help="Print parsed search results for one query and exit.")
    args = parser.parse_args()

    if args.debug_query:
        for result in fetch_search(args.debug_query):
            print(f"{result['title']} | {result['url']}")
        return

    include_websites = not args.linkedin_only
    include_linkedin = not args.websites_only

    rows = read_rows()
    attempted = 0
    changed = 0

    eligible_rows = []
    for row in rows:
        needs_website = include_websites and not row.get("website_url")
        needs_linkedin = include_linkedin and not (row.get("company_linkedin_url") and row.get("decision_maker_linkedin_url"))
        if needs_website or needs_linkedin:
            eligible_rows.append(row)

    for row in eligible_rows[args.offset:]:
        if attempted >= args.limit:
            break
        attempted += 1
        if enrich_row(row, include_websites, include_linkedin):
            changed += 1
            if args.checkpoint:
                write_rows(rows)
                print(f"Progress: attempted={attempted} updated={changed}", flush=True)
        time.sleep(1.0)

    write_rows(rows)
    print(f"Attempted {attempted} rows; updated {changed} rows.")


if __name__ == "__main__":
    main()
