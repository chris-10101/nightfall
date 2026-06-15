from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
from pathlib import Path

from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"


FIXES_BY_WEBSITE = {
    "https://hybrid-hr.co.uk/": {
        "lead_id": "hybrid-hr-01",
        "company_name": "Hybrid HR",
        "decision_maker_name": "Daniel",
        "decision_maker_role": "HR Consultant / Employment Lawyer",
    }
}


def main() -> None:
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    existing_ids = {row["lead_id"] for row in rows}
    changed = 0
    for row in rows:
        fix = FIXES_BY_WEBSITE.get(row.get("website_url", ""))
        if not fix:
            continue
        for field, value in fix.items():
            if field == "lead_id" and value in existing_ids and row[field] != value:
                continue
            if row.get(field) != value:
                if field == "lead_id":
                    existing_ids.discard(row[field])
                    existing_ids.add(value)
                row[field] = value
                changed += 1

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Applied {changed} known data quality fixes.")


if __name__ == "__main__":
    main()
