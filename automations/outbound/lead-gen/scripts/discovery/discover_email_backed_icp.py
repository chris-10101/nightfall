from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import re
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from core.csv_store import read_csv, write_csv_atomic
from discovery.discover_hr_consultancies import fetch_rss, root_domain
from enrichment.enrich_public_web import best_email, candidate_pages, email_type, emails_from_links, fetch, parse_page
from core.icp_profiles import active_profiles, normalize
from core.monitoring import init_sentry
from core.paths import data_dir
from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = data_dir() / "prospects.csv"
TODAY = date.today().isoformat()
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HRI_DIRECTORY_SITEMAP_URL = "https://hrindependents.co.uk/directory-listing-sitemap.xml"
HR_DEPT_LICENSEE_SITEMAP_URL = "https://www.hrdept.co.uk/sitemaps-1-section-licensees-1-sitemap.xml"
OUTPUT_AVAILABLE = True

BLOCKED_DOMAIN_PARTS = {
    "192.com",
    "approvedbusiness",
    "autodesk",
    "autotrader",
    "bbc.co.uk",
    "bizseek",
    "businessmagnet",
    "cambridge.org",
    "checkcompany",
    "companieshouse",
    "cylex",
    "dictionary",
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
    "merriam-webster",
    "opencorporates",
    "pearson",
    "reviews",
    "thebfa",
    "trustpilot",
    "twitter",
    "wikipedia",
    "x.com",
    "yell",
    "youtube",
}

EXTERNAL_LINK_BLOCKLIST = {
    "businessfranchise.com",
    "facebook.com",
    "franchiseinfo.co.uk",
    "hrindependents.co.uk",
    "hrdept.co.uk",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
}

BLOCKED_RESULT_PATH_PARTS = {
    "/article",
    "/blog",
    "/case-stud",
    "/events",
    "/guide",
    "/insight",
    "/news",
    "/post",
    "/resource",
    "/whitepaper",
}

GENERIC_COMPANY_NAMES = {
    "hr",
    "hr 101",
    "hr advice",
    "hr consultant",
    "hr consultancy",
    "hr consulting",
    "hr services",
    "hr support",
    "human resources",
    "outsourced hr",
    "retained hr support",
}


class NullOutput:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


def emit(message: str) -> None:
    global OUTPUT_AVAILABLE
    if not OUTPUT_AVAILABLE:
        return
    try:
        print(message, flush=True)
    except BrokenPipeError:
        OUTPUT_AVAILABLE = False
        sys.stdout = NullOutput()


class LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "a" and attrs_dict.get("href"):
            self.links.append(attrs_dict["href"] or "")

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)
        if self.in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    @property
    def title(self) -> str:
        return " ".join(" ".join(self.title_parts).split())

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


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


def email_root_domain(email: str) -> str:
    if "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1].strip().lower().removeprefix("www.")
    return root_domain(f"https://{domain}")


def email_matches_website(email: str, website_url: str) -> bool:
    email_domain = email_root_domain(email)
    website_domain = root_domain(website_url)
    return bool(email_domain and website_domain and email_domain == website_domain)


def blocked_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    if parsed.path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
        return True
    normalized_path = parsed.path.lower().rstrip("/")
    if any(part in normalized_path for part in BLOCKED_RESULT_PATH_PARTS):
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


def is_generic_company_name(company_name: str) -> bool:
    normalized = normalize(company_name)
    if normalized in GENERIC_COMPANY_NAMES:
        return True
    if normalized.startswith(("what is ", "how to ", "guide to ", "introduction to ")):
        return True
    return False


def name_from_hri_title(title: str, fallback_url: str) -> str:
    title = re.sub(r"\bHRi\b", " ", title, flags=re.I)
    title = re.sub(r"\bAccredited HR (?:& People )?(?:Consultant|Consultancy)? Directory\b", " ", title, flags=re.I)
    title = re.sub(r"\bHR & People (?:Consultant|Consultancy)? Directory\b", " ", title, flags=re.I)
    title = re.sub(r"\bHR & People Direct(?:ory)?\b", " ", title, flags=re.I)
    title = re.sub(r"\s+[|-]\s+.*$", "", title)
    title = re.sub(r"\s+", " ", title).strip(" -|:,.")
    if len(title) >= 3:
        return title[:90]
    return name_from_title(title, fallback_url)


def name_from_hr_dept_title(title: str, fallback_url: str) -> str:
    title = re.sub(r"\s*\|\s*HR Dept\s*$", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -|:,.")
    if len(title) >= 3:
        return f"The HR Dept {title}"[:90]
    path = urlparse(fallback_url).path.strip("/").split("/", 1)[0]
    return f"The HR Dept {path.replace('-', ' ').title()}"[:90]


def name_from_franchiseinfo_title(title: str, fallback_url: str) -> str:
    title = re.sub(r"\s*\|\s*.*$", "", title).strip(" -|:,.")
    if len(title) >= 3:
        return title[:90]
    path = urlparse(fallback_url).path.strip("/").split("/")[-1]
    return path.replace("-", " ").title()[:90]


def fetch_text(url: str, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "VesraLeadResearch/1.0 (+directory-backed lead research)",
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(1_000_000).decode("utf-8", errors="replace")


def sitemap_locs(url: str, timeout: int) -> list[str]:
    xml_text = fetch_text(url, timeout)
    root = ElementTree.fromstring(xml_text)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [item.text or "" for item in root.findall(".//s:loc", namespace)]


def hri_listing_urls(timeout: int) -> list[str]:
    urls = sitemap_locs(HRI_DIRECTORY_SITEMAP_URL, timeout)
    return [url for url in urls if "/directory-listing/" in url]


def hr_dept_licensee_urls(timeout: int) -> list[str]:
    urls = sitemap_locs(HR_DEPT_LICENSEE_SITEMAP_URL, timeout)
    licensee_urls: list[str] = []
    for url in urls:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if len(path_parts) != 1:
            continue
        if path_parts[0] in {"contact-us", "find-your-local-office", "about-us", "services"}:
            continue
        licensee_urls.append(url)
    return licensee_urls


FRANCHISEINFO_CATEGORY_URLS = [
    "https://www.franchiseinfo.co.uk/full-franchise-directory/care-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/children-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/cleaning-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/education-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/fitness-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/food-drink-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/home-improvement-franchises/",
    "https://www.franchiseinfo.co.uk/full-franchise-directory/property-franchises/",
]

FRANCHISEINFO_SITEMAP_URLS = [
    "https://www.franchiseinfo.co.uk/franchise-sitemap.xml",
    "https://www.franchiseinfo.co.uk/franchise-sitemap2.xml",
]


def site_home_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/"


def add_franchise_profile_url(profile_urls: list[str], seen: set[str], url: str) -> None:
    absolute = url.split("?", 1)[0].rstrip("/") + "/"
    if not re.match(r"https://www\.franchiseinfo\.co\.uk/franchise/[^/]+/$", absolute):
        return
    if absolute.endswith("/request-information/"):
        return
    if absolute in seen:
        return
    seen.add(absolute)
    profile_urls.append(absolute)


def franchiseinfo_profile_urls(timeout: int) -> list[str]:
    profile_urls: list[str] = []
    seen: set[str] = set()
    for sitemap_url in FRANCHISEINFO_SITEMAP_URLS:
        try:
            for loc in sitemap_locs(sitemap_url, timeout):
                add_franchise_profile_url(profile_urls, seen, loc)
        except Exception as exc:
            emit(f"DIRECTORY_SITEMAP_SKIP source=franchiseinfo url={sitemap_url} error={type(exc).__name__}")
            continue
    for category_url in FRANCHISEINFO_CATEGORY_URLS:
        try:
            html = fetch_text(category_url, timeout)
        except Exception as exc:
            emit(f"DIRECTORY_CATEGORY_SKIP source=franchiseinfo url={category_url} error={type(exc).__name__}")
            continue
        parser = LinkAndTitleParser()
        parser.feed(html)
        for href in parser.links:
            add_franchise_profile_url(profile_urls, seen, urljoin(category_url, href))
    return profile_urls


def listing_external_site(listing_url: str, timeout: int) -> tuple[str, str]:
    html = fetch_text(listing_url, timeout)
    parser = LinkAndTitleParser()
    parser.feed(html)
    for href in parser.links:
        absolute = urljoin(listing_url, href).strip()
        if not absolute.startswith(("http://", "https://")):
            continue
        domain = root_domain(absolute)
        if not domain or domain in EXTERNAL_LINK_BLOCKLIST:
            continue
        if blocked_url(absolute):
            continue
        return absolute, parser.title
    return "", parser.title


GENERIC_BRAND_TOKENS = {
    "and",
    "care",
    "children",
    "company",
    "franchise",
    "group",
    "home",
    "limited",
    "ltd",
    "services",
    "the",
    "uk",
}

FRANCHISE_SITE_SIGNALS = [
    "franchise",
    "franchisee",
    "franchisor",
    "franchise opportunities",
    "locations",
    "head office",
    "network",
]

FRANCHISEINFO_SUPPLIER_TITLE_TERMS = {
    "advisor",
    "franchise services",
    "supplier",
}


def brand_tokens(company_name: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[a-z0-9]+", company_name.lower()):
        if len(token) >= 3 and token not in GENERIC_BRAND_TOKENS:
            tokens.append(token)
    return tokens


def brand_match_score(company_name: str, url: str, text: str = "") -> int:
    tokens = brand_tokens(company_name)
    if not tokens:
        return 0
    haystack = normalize(f"{urlparse(url).netloc} {text}")
    return sum(1 for token in tokens if token in haystack)


def brand_domain_match_score(company_name: str, url: str) -> int:
    tokens = brand_tokens(company_name)
    if not tokens:
        return 0
    domain_text = normalize(urlparse(url).netloc)
    return sum(1 for token in tokens if token in domain_text)


def has_franchise_site_signal(text: str) -> bool:
    normalized_text = normalize(text)
    return any(signal in normalized_text for signal in FRANCHISE_SITE_SIGNALS)


def is_franchiseinfo_supplier_profile(title: str) -> bool:
    normalized_title = normalize(title)
    return any(term in normalized_title for term in FRANCHISEINFO_SUPPLIER_TITLE_TERMS)


def resolve_franchise_official_site(company_name: str, timeout: int) -> str:
    tokens = brand_tokens(company_name)
    if not tokens:
        return ""
    queries = [
        f'"{company_name}" "franchise" "contact"',
        f'"{company_name}" "franchise opportunities"',
        f'"{company_name}" official website UK',
    ]
    best_url = ""
    best_score = 0
    for query in queries:
        try:
            results = fetch_rss(query, timeout=timeout)
        except Exception:
            continue
        for result in results[:8]:
            url = result.get("url", "")
            if blocked_url(url):
                continue
            domain = root_domain(url)
            if domain in EXTERNAL_LINK_BLOCKLIST:
                continue
            result_text = f"{result.get('title', '')} {result.get('description', '')}"
            score = brand_match_score(company_name, url, result_text)
            domain_score = brand_domain_match_score(company_name, url)
            if domain_score < 1:
                continue
            if len(tokens) > 1 and score < 2:
                continue
            if len(tokens) == 1 and score < 1:
                continue
            if score > best_score:
                best_url = url
                best_score = score
        if best_url:
            return best_url
    return ""


def append_source_row(
    *,
    rows: list[dict[str, str]],
    existing_ids: set[str],
    existing_domains: set[str],
    existing_emails: set[str],
    existing_names: set[str],
    company_name: str,
    segment: str,
    subtype: str,
    city_region: str,
    website_url: str,
    email: str,
    email_source_url: str,
    source: str,
    source_url: str,
    notes: str,
    positive_hits: list[str],
    allow_shared_domain: bool = False,
) -> None:
    domain = root_domain(website_url)
    row = {header: "" for header in HEADERS}
    row.update(
        {
            "lead_id": next_id(company_name, existing_ids),
            "company_name": company_name,
            "segment": segment,
            "subtype": subtype,
            "city_region": city_region,
            "website_url": website_url,
            "email": email,
            "email_type": email_type(email),
            "email_confidence": "high",
            "email_source_url": email_source_url,
            "source": source,
            "source_url": source_url,
            "notes": notes,
            "status": "ready_to_review",
            "last_researched_at": TODAY,
        }
    )
    row["fit_score"], row["priority"] = score_row(row, positive_hits)
    rows.append(row)
    existing_ids.add(row["lead_id"])
    if not allow_shared_domain:
        existing_domains.add(domain)
    existing_emails.add(email.lower())
    existing_names.add(normalize(company_name))


def add_directory_rows(
    *,
    profile_key: str,
    profile: dict,
    rows: list[dict[str, str]],
    existing_ids: set[str],
    existing_domains: set[str],
    existing_emails: set[str],
    existing_names: set[str],
    max_new: int,
    max_pages: int,
    max_candidates: int,
    timeout: int,
    checkpoint: bool,
) -> int:
    if profile_key != "hr_consultancy_partner" or max_new <= 0:
        return 0

    added = 0
    segment = profile.get("segments", [""])[0]
    try:
        listing_urls = hri_listing_urls(timeout)
    except Exception as exc:
        emit(f"DIRECTORY_SKIP source=hri error={type(exc).__name__}")
        return 0

    for candidate_index, listing_url in enumerate(listing_urls):
        if candidate_index >= max_candidates:
            break
        if added >= max_new:
            break
        try:
            website_url, listing_title = listing_external_site(listing_url, timeout)
        except Exception as exc:
            emit(f"DIRECTORY_LISTING_SKIP source=hri url={listing_url} error={type(exc).__name__}")
            continue
        if not website_url:
            continue

        domain = root_domain(website_url)
        if domain in existing_domains:
            continue

        company_name = name_from_hri_title(listing_title, website_url)
        if normalize(company_name) in existing_names:
            continue

        try:
            page_text, email, email_source_url = fetch_site_context(website_url, max_pages, timeout)
        except Exception as exc:
            emit(f"DIRECTORY_SITE_SKIP source=hri company={company_name!r} error={type(exc).__name__}")
            continue

        if not email or email.lower() in existing_emails:
            continue
        if not email_matches_website(email, website_url):
            emit(
                f"DIRECTORY_EMAIL_SKIP source=hri company={company_name!r} "
                f"email_domain={email_root_domain(email)} website_domain={domain}"
            )
            continue

        combined_text = f"{listing_title} {page_text}"
        exclusion_hits = hits(combined_text, profile.get("exclude_terms", []))
        if exclusion_hits:
            continue
        required_hits = hits(combined_text, profile.get("required_terms_any", []))
        if not required_hits:
            required_hits = ["HR Independents accredited directory listing"]
        positive_hits = hits(combined_text, profile.get("positive_terms", []))

        append_source_row(
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            company_name=company_name,
            segment=segment,
            subtype=profile.get("label", profile_key),
            city_region="UK",
            website_url=website_url,
            email=email,
            email_source_url=email_source_url,
            source=f"HR Independents public directory with public email ({profile_key})",
            source_url=listing_url,
            notes=(
                f"ICP profile: {profile_key}. Source: HR Independents directory listing. "
                f"Required signals: {', '.join(required_hits[:5])}. "
                f"Positive signals: {', '.join(positive_hits[:8])}. "
                f"Listing title: {listing_title}"
            ),
            positive_hits=positive_hits,
        )
        added += 1
        emit(f"DIRECTORY_ADD source=hri profile={profile_key} {added}: {company_name} | {email} | {website_url}")
        if checkpoint:
            write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)

    return added


def add_hr_dept_rows(
    *,
    profile_key: str,
    profile: dict,
    rows: list[dict[str, str]],
    existing_ids: set[str],
    existing_domains: set[str],
    existing_emails: set[str],
    existing_names: set[str],
    existing_source_urls: set[str],
    max_new: int,
    max_pages: int,
    max_candidates: int,
    timeout: int,
    checkpoint: bool,
) -> int:
    if profile_key != "hr_consultancy_partner" or max_new <= 0:
        return 0

    try:
        urls = hr_dept_licensee_urls(timeout)
    except Exception as exc:
        emit(f"DIRECTORY_SKIP source=hrdept error={type(exc).__name__}")
        return 0

    added = 0
    segment = profile.get("segments", [""])[0]
    for candidate_index, url in enumerate(urls):
        if candidate_index >= max_candidates:
            break
        if added >= max_new:
            break
        if url in existing_source_urls:
            continue
        try:
            html = fetch_text(url, timeout)
            parser = LinkAndTitleParser()
            parser.feed(html)
            company_name = name_from_hr_dept_title(parser.title, url)
            page_text, email, email_source_url = fetch_site_context(url, max_pages, timeout)
        except Exception as exc:
            emit(f"DIRECTORY_SITE_SKIP source=hrdept url={url} error={type(exc).__name__}")
            continue
        if not email or email.lower() in existing_emails:
            continue
        if normalize(company_name) in existing_names:
            continue
        combined_text = f"{parser.title} {parser.text} {page_text}"
        required_hits = hits(combined_text, profile.get("required_terms_any", []))
        if not required_hits:
            continue
        positive_hits = hits(combined_text, profile.get("positive_terms", []))
        append_source_row(
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            company_name=company_name,
            segment=segment,
            subtype="HR Dept local licensee",
            city_region=company_name.replace("The HR Dept", "").strip() or "UK",
            website_url=url,
            email=email,
            email_source_url=email_source_url,
            source=f"HR Dept public licensee page with public email ({profile_key})",
            source_url=url,
            notes=(
                f"ICP profile: {profile_key}. Source: HR Dept licensee sitemap. "
                f"Required signals: {', '.join(required_hits[:5])}. "
                f"Positive signals: {', '.join(positive_hits[:8])}."
            ),
            positive_hits=positive_hits,
            allow_shared_domain=True,
        )
        existing_source_urls.add(url)
        added += 1
        emit(f"DIRECTORY_ADD source=hrdept profile={profile_key} {added}: {company_name} | {email} | {url}")
        if checkpoint:
            write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    return added


def add_franchiseinfo_rows(
    *,
    profile_key: str,
    profile: dict,
    rows: list[dict[str, str]],
    existing_ids: set[str],
    existing_domains: set[str],
    existing_emails: set[str],
    existing_names: set[str],
    existing_source_urls: set[str],
    max_new: int,
    max_pages: int,
    max_candidates: int,
    timeout: int,
    checkpoint: bool,
) -> int:
    if profile_key != "franchise" or max_new <= 0:
        return 0

    try:
        profile_urls = franchiseinfo_profile_urls(timeout)
    except Exception as exc:
        emit(f"DIRECTORY_SKIP source=franchiseinfo error={type(exc).__name__}")
        return 0

    added = 0
    segment = profile.get("segments", ["Franchise"])[0]
    for candidate_index, profile_url in enumerate(profile_urls):
        if candidate_index >= max_candidates:
            break
        if added >= max_new:
            break
        if profile_url in existing_source_urls:
            continue
        try:
            profile_html = fetch_text(profile_url, timeout)
            parser = LinkAndTitleParser()
            parser.feed(profile_html)
            if is_franchiseinfo_supplier_profile(parser.title):
                continue
            company_name = name_from_franchiseinfo_title(parser.title, profile_url)
        except Exception as exc:
            emit(f"DIRECTORY_PROFILE_SKIP source=franchiseinfo url={profile_url} error={type(exc).__name__}")
            continue
        if normalize(company_name) in existing_names:
            continue

        official_url = resolve_franchise_official_site(company_name, timeout)
        if not official_url:
            continue
        official_url = site_home_url(official_url)
        domain = root_domain(official_url)
        if domain in existing_domains:
            continue
        try:
            page_text, email, email_source_url = fetch_site_context(official_url, max_pages, timeout)
        except Exception:
            continue
        combined_text = f"{parser.title} {parser.text} {page_text}"
        if not has_franchise_site_signal(combined_text):
            continue
        if brand_match_score(company_name, official_url, combined_text) < min(2, max(1, len(brand_tokens(company_name)))):
            continue
        if not email or email.lower() in existing_emails:
            continue
        if not email_matches_website(email, official_url):
            continue

        positive_hits = hits(combined_text, profile.get("positive_terms", []))
        if not positive_hits:
            positive_hits = ["franchise network"]
        append_source_row(
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            company_name=company_name,
            segment=segment,
            subtype=profile.get("label", profile_key),
            city_region="UK",
            website_url=official_url,
            email=email,
            email_source_url=email_source_url,
            source=f"FranchiseInfo profile resolved to official site with public email ({profile_key})",
            source_url=profile_url,
            notes=(
                f"ICP profile: {profile_key}. Source: FranchiseInfo public profile. "
                f"Official site resolved by brand search. Positive signals: {', '.join(positive_hits[:8])}."
            ),
            positive_hits=positive_hits,
        )
        existing_source_urls.add(profile_url)
        added += 1
        emit(f"DIRECTORY_ADD source=franchiseinfo profile={profile_key} {added}: {company_name} | {email} | {official_url}")
        if checkpoint:
            write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    return added


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
    init_sentry("daily-discovery")
    parser = argparse.ArgumentParser(description="Discover prospects for any active ICP, adding only rows with public emails.")
    parser.add_argument("--profile", action="append", help="ICP profile key to run. Defaults to all active profiles.")
    parser.add_argument("--max-new", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-source-candidates", type=int, default=40)
    parser.add_argument("--max-queries-per-profile", type=int, default=24)
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
    existing_source_urls = {row.get("source_url", "").strip() for row in rows if row.get("source_url")}

    added = 0
    searched = 0
    considered = 0

    for profile_key, profile in profiles.items():
        profile_added = 0
        profile_searched = 0
        segment = profile.get("segments", [""])[0]
        hr_dept_added = add_hr_dept_rows(
            profile_key=profile_key,
            profile=profile,
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            existing_source_urls=existing_source_urls,
            max_new=args.max_new - profile_added,
            max_pages=args.max_pages,
            max_candidates=args.max_source_candidates,
            timeout=args.timeout,
            checkpoint=args.checkpoint,
        )
        profile_added += hr_dept_added
        added += hr_dept_added
        if hr_dept_added:
            emit(f"DIRECTORY_SUMMARY profile={profile_key} source=hrdept added={hr_dept_added}")
        directory_added = add_directory_rows(
            profile_key=profile_key,
            profile=profile,
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            max_new=args.max_new - profile_added,
            max_pages=args.max_pages,
            max_candidates=args.max_source_candidates,
            timeout=args.timeout,
            checkpoint=args.checkpoint,
        )
        profile_added += directory_added
        added += directory_added
        if directory_added:
            emit(f"DIRECTORY_SUMMARY profile={profile_key} source=hri added={directory_added}")
        franchiseinfo_added = add_franchiseinfo_rows(
            profile_key=profile_key,
            profile=profile,
            rows=rows,
            existing_ids=existing_ids,
            existing_domains=existing_domains,
            existing_emails=existing_emails,
            existing_names=existing_names,
            existing_source_urls=existing_source_urls,
            max_new=args.max_new - profile_added,
            max_pages=args.max_pages,
            max_candidates=args.max_source_candidates,
            timeout=args.timeout,
            checkpoint=args.checkpoint,
        )
        profile_added += franchiseinfo_added
        added += franchiseinfo_added
        if franchiseinfo_added:
            emit(f"DIRECTORY_SUMMARY profile={profile_key} source=franchiseinfo added={franchiseinfo_added}")
        for query, geo, geo_type in expand_queries(profile):
            if profile_added >= args.max_new:
                break
            if profile_searched >= args.max_queries_per_profile:
                emit(f"QUERY_LIMIT profile={profile_key} searched={profile_searched} added={profile_added}")
                break
            searched += 1
            profile_searched += 1
            try:
                results = fetch_rss(query, timeout=args.timeout)
            except Exception as exc:
                emit(f"SKIP profile={profile_key} query={query!r} error={type(exc).__name__}")
                time.sleep(args.sleep)
                continue

            for result in results:
                if profile_added >= args.max_new:
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
                if is_generic_company_name(company_name):
                    continue
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
                if not email_matches_website(email, url):
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
                profile_added += 1
                added += 1
                emit(f"ADD profile={profile_key} {added}: {company_name} | {email} | {url}")
                if args.checkpoint:
                    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)

            emit(f"QUERY profile={profile_key} searched={searched} considered={considered} added={added}: {query}")
            time.sleep(args.sleep)

    write_csv_atomic(PROSPECTS_PATH, rows, HEADERS)
    emit(f"Added {added} email-backed rows. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
