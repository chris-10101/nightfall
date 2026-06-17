from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db_store


def main() -> None:
    migrated = db_store.migrate_current_tables()
    with db_store.connection() as conn:
        tables = sorted(db_store.inspector(conn).get_table_names())
        print("tables: " + ", ".join(tables))
        print(
            "organisation: "
            + str(db_store.default_organisation_id())
            + " "
            + db_store.default_organisation_name()
        )
        for dataset in migrated:
            columns = db_store.current_columns(conn, dataset)
            print(f"MIGRATED: {dataset} ({', '.join(columns)})")


if __name__ == "__main__":
    main()
