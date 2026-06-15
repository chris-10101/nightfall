from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
from pathlib import Path
from urllib.parse import urlparse

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"

BAD_DOMAINS = {
    "adp.com",
    "bbc.co.uk",
    "bbc.com",
    "brighthr.com",
    "cipd.org",
    "coursera.org",
    "history.com",
    "hrmagazine.co.uk",
    "outsourced.co",
    "peoplehr.com",
}


def root_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"co", "org"} and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def main() -> None:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    kept = []
    removed = 0
    for row in rows:
        is_discovered = row.get("source") == "Bing RSS public search result"
        is_bad_domain = root_domain(row.get("website_url", "")) in BAD_DOMAINS
        if is_discovered and is_bad_domain:
            removed += 1
            continue
        kept.append(row)

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(kept)

    print(f"Removed {removed} bad discovery rows. Total rows: {len(kept)}")


if __name__ == "__main__":
    main()
