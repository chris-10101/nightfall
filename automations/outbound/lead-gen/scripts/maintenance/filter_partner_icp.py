from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
from datetime import datetime, timezone
from pathlib import Path

from core.icp_profiles import is_active_segment, profile_exclusion_hits, profile_required_signal


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def backup_csv(path: Path, stamp: str) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = ARCHIVE_DIR / f"{path.stem}.pre_active_icp_filter_{stamp}.csv"
    rows, headers = read_csv(path)
    write_csv(backup_path, rows, headers)
    return backup_path


def is_active_partner_icp(row: dict[str, str]) -> tuple[bool, str]:
    subtype = row.get("subtype", "").strip().lower()
    company_name = row.get("company_name", "").strip().lower()
    notes = row.get("notes", "").strip().lower()
    headcount = row.get("estimated_headcount", "").strip().lower()
    combined = " ".join([subtype, company_name, notes])

    if not is_active_segment(row.get("segment", "")):
        return False, "not_active_segment"
    exclusions = profile_exclusion_hits(row)
    if exclusions:
        return False, "profile_exclusion:" + ",".join(exclusions)
    if not profile_required_signal(row):
        return False, "missing_profile_required_signal"
    if "recruit" in combined:
        return False, "recruitment_not_partner_icp"
    if "software platform" in combined or "hr software vendor" in combined:
        return False, "has_or_sells_own_software"
    if headcount in {"1", "solo", "sole trader"}:
        return False, "solo_consultant"
    if "outsourced hr" in subtype or "sme hr support" in subtype or "retained" in combined:
        return True, "matches_active_partner_icp"
    if "hr consulting" in subtype or "hr consultant" in company_name:
        return True, "probable_hr_partner_icp_needs_review"
    if "franchise" in combined or "franchisor" in combined or "franchisee" in combined:
        return True, "matches_franchise_partner_icp"
    return False, "insufficient_active_icp_evidence"


def is_queue_active_partner(row: dict[str, str]) -> tuple[bool, str]:
    company_name = row.get("company_name", "").strip().lower()
    if not is_active_segment(row.get("segment", "")):
        return False, "not_active_segment"
    exclusions = profile_exclusion_hits(row)
    if exclusions:
        return False, "profile_exclusion:" + ",".join(exclusions)
    if "recruit" in company_name:
        return False, "recruitment_not_partner_icp"
    return True, "matches_active_partner_queue"


def filter_file(path: Path, stamp: str) -> tuple[int, int, Path, Path]:
    rows, headers = read_csv(path)
    backup_path = backup_csv(path, stamp)
    kept = []
    removed = []

    for row in rows:
        keep, reason = is_queue_active_partner(row) if path == QUEUE_PATH else is_active_partner_icp(row)
        if keep:
            kept.append(row)
        else:
            removed_row = dict(row)
            removed_row["removal_reason"] = reason
            removed.append(removed_row)

    removed_path = ARCHIVE_DIR / f"{path.stem}.removed_by_active_icp_filter_{stamp}.csv"
    removed_headers = headers + ["removal_reason"]
    write_csv(removed_path, removed, removed_headers)
    write_csv(path, kept, headers)
    return len(kept), len(removed), backup_path, removed_path


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for path in (PROSPECTS_PATH, QUEUE_PATH):
        kept, removed, backup_path, removed_path = filter_file(path, stamp)
        print(f"{path}: kept={kept} removed={removed}")
        print(f"backup={backup_path}")
        print(f"removed={removed_path}")


if __name__ == "__main__":
    main()
