from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv

from core import db_store
from core.paths import data_dir


DEFAULT_FILES = [
    "prospects.csv",
    "campaign_queue.csv",
    "suppression.csv",
    "reply_events.csv",
    "agent_events.csv",
]


def read_csv_file(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader), list(reader.fieldnames or [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Import outbound CSV state into the configured database.")
    parser.add_argument("--data-dir", type=Path, default=data_dir())
    parser.add_argument("--file", action="append", dest="files", help="CSV filename to import. Can be repeated.")
    args = parser.parse_args()

    imported = 0
    for filename in args.files or DEFAULT_FILES:
        path = args.data_dir / filename
        rows, headers = read_csv_file(path)
        if not headers:
            print(f"SKIP: {path} does not exist or has no headers.")
            continue
        db_store.write_rows(path, rows, headers)
        imported += 1
        print(f"IMPORTED: {filename} ({len(rows)} rows)")

    print(f"Imported {imported} CSV datasets into database storage.")


if __name__ == "__main__":
    main()
