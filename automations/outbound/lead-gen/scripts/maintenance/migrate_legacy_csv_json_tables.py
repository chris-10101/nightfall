from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from core import db_store


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy nightfall_csv_* JSON tables into real per-dataset tables."
    )
    parser.add_argument(
        "--drop-legacy",
        action="store_true",
        help="Drop nightfall_csv_rows and nightfall_csv_headers after successful migration.",
    )
    args = parser.parse_args()

    migrated = db_store.migrate_legacy_tables(drop_legacy=args.drop_legacy)
    if not migrated:
        print("No legacy CSV JSON datasets found to migrate.")
        return
    for dataset, count in migrated:
        print(f"MIGRATED: {dataset} ({count} rows)")
    print(f"Migrated {len(migrated)} datasets into real tables.")
    if args.drop_legacy:
        print("Dropped legacy nightfall_csv_* tables.")


if __name__ == "__main__":
    main()
