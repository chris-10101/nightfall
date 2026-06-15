from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from core.csv_store import read_csv, write_csv_atomic
from discovery.discover_hr_consultancies import fetch_rss, root_domain
from enrichment.enrich_public_web import best_email, candidate_pages, email_type, emails_from_links, fetch, parse_page
from core.icp_profiles import active_profiles, normalize
from core.paths import data_dir
from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = data_dir() / "prospects.csv"
TODAY = date.today().isoformat()
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

BLOCKED_DOMAIN_PARTS = {
    "192.com",
    "approvedbusiness",
    "bizseek",
    "businessmagnet",
    "checkcompany",
    "companieshouse",
    "cylex",
    "directory",
    "facebook",
    "find-open",
    "franchise-uk",
    "franchiseinfo",
    "franchisedirect",
    "franchiseeurope",
    "franchiselocal",
    "franchisesupermarket",
    "glassdoor",
    "indeed",
    "instagram",
    "linkedin",
    "opencorporates",
    "reviews",
    "thebfa",
    "trustpilot",
    "twitter",
    "wikipedia",
    "x.com",
    "yell",
}


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


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def blocked_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    if parsed.path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
        return True
    domain_text = f"{host(url)} {root_domain(url)}"
    return any(part in domain_text for part in BLOCKED_DOMAIN_PARTS)


def has_any(text: str, terms: list[str]) -> bool:
    normalized_text = normalize(text)
    return any(normalize(term) in normalized_text for term in terms)


def hits(text: str, terms: list[str]) -> list[str]:
    normalized_text = normalize(text)
    return [term for term in terms if normalize(term) in normalized_text]


def name_from_title(title: str, url: str) -> str:
    for separator in (" | ", " - ", " – ", " — ", ":"):
        if separator in title:
            title = title.split(separator, 1)[0]
            break
    title = re.sub(r"\b(official website|home page|home|franchise opportunities|franchise)\b", " ", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -|:,.")
    if len(title) >= 3:
        return title[:90]
    domain = root_domain(url).split(".", 1)[0]
    return re.sub(r"[-_]+", " ", domain).title()


def geographies(discovery: dict) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    singular_types = {"cities": "city", "regions": "region", "countries": "country"}
    for geo_type in ("cities", "regions", "countries"):
        singular = singular_types[geo_type]
        for value in discovery.get(geo_type, []):
            values.append((value, singular))
    legacy_locations = discovery.get("locations", [])
    for value in legacy_locations:
        values.append((value, "location"))
    return values or [("UK", "country")]


def expand_queries(profile: dict) -> list[tuple[str, str, str]]:
    discovery = profile.get("discovery", {})
    templates = discovery.get("query_templates", [])
    geo_values = geographies(discovery)
    verticals = discovery.get("verticals", [""])
    queries = []
    for template in templates:
        for geo, geo_type in geo_values:
            if "{vertical}" in template:
                for vertical in verticals:
                    queries.append((template.format(geo=geo, location=geo, vertical=vertical), geo, geo_type))
            else:
                queries.append((template.format(geo=geo, location=geo), geo, geo_type))
    return queries


def fetch_site_context(url: str, max_pages: int, timeout: int) -> tuple[str, str, str]:
    homepage_html = fetch(url, timeout=timeout)
    homepage_text, links = parse_page(homepage_html)
    pages = candidate_pages(url, links, max_pages)
    all_links = list(links)
    texts = [homepage_text]
    email_source_url = url

    for page_url in pages[1:]:
        try:
            page_html = fetch(page_url, timeout=timeout)
        except Exception:
            continue
        page_text, page_links = parse_page(page_html)
        texts.append(page_text)
        all_links.extend(page_links)
        time.sleep(0.2)

    emails = set()
    for text in texts:
        emails.update(email.strip(".,;:") for email in EMAIL_RE.findall(text))
    emails.update(emails_from_links(all_links))
    return " ".join(texts), best_email(emails), email_source_url


def score_row(row: dict[str, str], positive_hits: list[str]) -> tuple[str, str]:
    score = 45
    if row.get("website_url"):
        score += 10
    if row.get("email"):
        score += 15
    if row.get("city_region"):
        score += 5
    score += min(len(positive_hits) * 4, 20)
    score = min(score, 100)
    if score >= 80:
        return str(score), "high"
    if score >= 60:
        return str(score), "medium"
    if score >= 40:
        return str(score), "low"
    return str(score), "park"


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover prospects for any active ICP, adding only rows with public emails.")
    parser.add_argument("--profile", action="append", help="ICP profile key to run. Defaults to all active profiles.")
    parser.add_argument("--max-new", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--checkpoint", action="store_true")
    args = parser.parse_args()

    profiles = active_profiles()
    if args.profile:
        profiles = {key: profiles[key] for key in args.profile if key in profiles}
    if not profiles:
        raise SystemExit("No active ICP profiles selected.")

    rows = read_csv(PROSPECTS_PATH)
    existing_ids = {row["lead_id"] for row in rows}
    existing_domains = {root_domain(row["website_url"]) for row in rows if row.get("website_url")}
    existing_emails = {row["email"].strip().lower() for row in rows if row.get("email")}
    existing_names = {normalize(row["company_name"]) for row in rows}

    added = 0
    searched = 0
    considered = 0

    for profile_key, profile in profiles.items():
        segment = profile.get("segments", [""])[0]
        for query, geo, geo_type in expand_queries(profile):
            if added >= args.max_new:
                break
            searched += 1
            try:
                results = fetch_rss(query, timeout=args.timeout)
            except Exception as exc:
                print(f"SKIP profile={profile_key} query={query!r} error={type(exc).__name__}", flush=True)
                time.sleep(args.sleep)
                continue

            for result in results:
                if added >= args.max_new:
                    break
                url = result.get("url", "")
                if blocked_url(url):
                    continue
                domain = root_domain(url)
                if domain in existing_domains:
                    continue

                result_text = f"{result.get('title', '')} {result.get('description', '')} {domain}"
                if not has_any(result_text, profile.get("required_terms_any", [])):
                    continue
                if has_any(result_text, profile.get("exclude_terms", [])):
                    continue

                company_name = name_from_title(result.get("title", ""), url)
                if normalize(company_name) in existing_names:
                    continue

                considered += 1
                try:
                    page_text, email, email_source_url = fetch_site_context(url, args.max_pages, args.timeout)
                except Exception:
                    continue
                combined_text = f"{result_text} {page_text}"
                exclusion_hits = hits(combined_text, profile.get("exclude_terms", []))
                if exclusion_hits:
                    continue
                required_hits = hits(combined_text, profile.get("required_terms_any", []))
                if not required_hits:
                    continue
                if not email or email.lower() in existing_emails:
                    continue

                positive_hits = hits(combined_text, profile.get("positive_terms", []))
                row = {header: "" for header in HEADERS}
                row.update(
                    {
                        "lead_id": next_id(company_name, existing_ids),
                        "company_name": company_name,
                        "segment": segment,
                        "subtype": profile.get("label", profile_key),
                        "city_region": geo,
                        "website_url": url,
                        "email": email,
                        "email_type": email_type(email),
                        "email_confidence": "high",
                        "email_source_url": email_source_url,
                        "source": f"Public search result with public email ({profile_key})",
                        "source_url": url,
                        "notes": (
                            f"ICP profile: {profile_key}. Geography type: {geo_type}. Discovered via query: {query}. "
                            f"Required signals: {', '.join(required_hits[:5])}. "
                            f"Positive signals: {', '.join(positive_hits[:8])}. "
                            f"Result title: {result.get('title', '')}"
                        ),
                        "status": "ready_to_review",
                        "last_researched_at": TODAY,
                    }
                )
                row["fit_score"], row["priority"] = score_row(row, positive_hits)
                rows.append(row)
                existing_ids.add(row["lead_id"])
                existing_domains.add(domain)
                existing_emails.add(email.lower())
                existing_names.add(normalize(company_name))
                added += 1
                print(f"ADD profile={profile_key} {added}: {company_name} | {email} | {url}", flush=True)
                if args.checkpoint:
                    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)

            print(
                f"QUERY profile={profile_key} searched={searched} considered={considered} added={added}: {query}",
                flush=True,
            )
            time.sleep(args.sleep)

    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    print(f"Added {added} email-backed rows. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
