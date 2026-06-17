from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json

from core import db_store
from core.paths import data_dir


def datasets() -> list[tuple[str, list[str]]]:
    _, text = db_store.load_sqlalchemy()
    with db_store.connection() as conn:
        rows = conn.execute(
            text(f"SELECT dataset, headers_json FROM {db_store.HEADER_TABLE} ORDER BY dataset ASC")
        )
        return [(row.dataset, json.loads(row.headers_json)) for row in rows]


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export database-backed outbound state to CSV files.")
    parser.add_argument("--output-dir", type=Path, default=data_dir())
    args = parser.parse_args()

    exported = 0
    for dataset, headers in datasets():
        path = args.output_dir / f"{dataset}.csv"
        rows = db_store.read_rows(path)
        write_csv(path, rows, headers)
        exported += 1
        print(f"EXPORTED: {path} ({len(rows)} rows)")

    print(f"Exported {exported} database datasets.")


if __name__ == "__main__":
    main()
