from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"

BAD_DOMAINS = {
    "acorninsure.co.uk",
    "aim-group.org.uk",
    "alpha.org",
    "bark.com",
    "brighthr.com",
    "britannica.com",
    "core.ac.uk",
    "dictionary.cambridge.org",
    "doodle.com",
    "doodlelearning.com",
    "en.m.wikipedia.org",
    "en.wikipedia.org",
    "find-hr.co.uk",
    "hrmagazine.co.uk",
    "hrconsultancy.uk",
    "lincolnshirelive.co.uk",
    "merriam-webster.com",
    "riverisland.com",
    "thefreedictionary.com",
    "visitcambridge.org",
    "wikipedia.org",
    "yell.com",
    "youtube.com",
    "zestcarrental.com",
}

BAD_EMAILS = {
    "example@mysite.com",
    "user@domain.com",
}

BAD_EMAIL_DOMAINS = {
    "domain.com",
    "open.ac.uk",
}

NOT_FIT_COMPANY_NAMES = {
    "peninsula hr (manchester hq)": "Excluded from ICP: large HR provider with its own technology/software offer.",
}


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def root_domain(url: str) -> str:
    parts = host(url).split(".")
    if len(parts) <= 2:
        return host(url)
    if parts[-2] in {"co", "org"} and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def read_rows() -> list[dict[str, str]]:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[dict[str, str]]) -> None:
    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} | {addition}"


def is_bad_email(email: str) -> bool:
    email = email.strip().lower()
    if not email or "@" not in email:
        return False
    local_part, domain = email.split("@", 1)
    email_domain = domain
    if email in BAD_EMAILS or email_domain in BAD_EMAIL_DOMAINS:
        return True
    if len(local_part) >= 24 and re.fullmatch(r"[a-f0-9]+", local_part) and domain == "face2facehr.com":
        return True
    return False


def main() -> None:
    rows = read_rows()
    changed = 0
    for row in rows:
        company_name = row.get("company_name", "").strip().lower()
        if company_name in NOT_FIT_COMPANY_NAMES:
            row["status"] = "not_fit"
            row["priority"] = "park"
            row["notes"] = append_note(row.get("notes", ""), NOT_FIT_COMPANY_NAMES[company_name])
            changed += 1

        email = row.get("email", "").strip().lower()
        if is_bad_email(email):
            row["notes"] = append_note(row.get("notes", ""), f"Removed bad email enrichment: {row.get('email', '')}")
            row["email"] = ""
            row["email_type"] = ""
            row["email_confidence"] = ""
            row["email_source_url"] = ""
            changed += 1

        website_url = row.get("website_url", "")
        if not website_url:
            continue
        website_host = host(website_url)
        website_root = root_domain(website_url)
        if website_host not in BAD_DOMAINS and website_root not in BAD_DOMAINS:
            continue
        row["notes"] = append_note(row.get("notes", ""), f"Removed bad website enrichment: {website_url}")
        row["website_url"] = ""
        if row.get("source_url") == website_url:
            row["source_url"] = ""
        changed += 1
    write_rows(rows)
    print(f"Cleared {changed} bad website enrichments.")


if __name__ == "__main__":
    main()
