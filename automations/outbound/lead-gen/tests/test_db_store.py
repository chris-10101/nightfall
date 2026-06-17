import os
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from core.csv_store import append_csv_atomic, read_csv, write_csv_atomic
from core import db_store


class DatabaseStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            self.skipTest("SQLAlchemy is not installed.")
        self.tmp = tempfile.TemporaryDirectory()
        self.original_backend = os.environ.get("NIGHTFALL_STORAGE_BACKEND")
        self.original_url = os.environ.get("DATABASE_URL")
        os.environ["NIGHTFALL_STORAGE_BACKEND"] = "database"
        os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{Path(self.tmp.name) / 'state.sqlite3'}"

    def tearDown(self) -> None:
        if self.original_backend is None:
            os.environ.pop("NIGHTFALL_STORAGE_BACKEND", None)
        else:
            os.environ["NIGHTFALL_STORAGE_BACKEND"] = self.original_backend
        if self.original_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.original_url
        self.tmp.cleanup()

    def test_read_write_append_uses_database_backend(self) -> None:
        path = Path(self.tmp.name) / "prospects.csv"
        headers = ["lead_id", "company_name", "email"]
        write_csv_atomic(
            path,
            [{"lead_id": "lead-1", "company_name": "Acme HR", "email": "sarah@example.com"}],
            headers,
        )
        append_csv_atomic(
            path,
            {"lead_id": "lead-2", "company_name": "Beta HR", "email": "helen@example.com"},
            headers,
        )
        rows = read_csv(path)
        self.assertEqual([row["lead_id"] for row in rows], ["lead-1", "lead-2"])
        self.assertEqual([row["organisation_id"] for row in rows], ["1", "1"])
        self.assertFalse(path.exists())

        with db_store.connection() as conn:
            self.assertTrue(db_store.table_exists(conn, "organisations"))
            self.assertTrue(db_store.table_exists(conn, "prospects"))
            self.assertIn("company_name", db_store.user_columns(conn, "prospects"))
            self.assertIn("organisation_id", db_store.user_columns(conn, "prospects"))
            self.assertFalse(any(column.startswith("_") for column in db_store.current_columns(conn, "prospects")))
            self.assertFalse(db_store.table_exists(conn, db_store.LEGACY_ROW_TABLE))

    def test_migrates_legacy_json_tables_to_real_tables(self) -> None:
        create_engine, _, text = db_store.load_sqlalchemy()
        engine = create_engine(os.environ["DATABASE_URL"], future=True)
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE nightfall_csv_headers (
                  dataset VARCHAR(191) PRIMARY KEY,
                  headers_json TEXT NOT NULL,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE nightfall_csv_rows (
                  dataset VARCHAR(191) NOT NULL,
                  row_key VARCHAR(191) NOT NULL,
                  row_index INTEGER NOT NULL,
                  data_json TEXT NOT NULL,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (dataset, row_key)
                )
            """))
            conn.execute(
                text("INSERT INTO nightfall_csv_headers (dataset, headers_json) VALUES (:dataset, :headers)"),
                {"dataset": "campaign_queue", "headers": '["lead_id", "email"]'},
            )
            conn.execute(
                text("""
                    INSERT INTO nightfall_csv_rows (dataset, row_key, row_index, data_json)
                    VALUES (:dataset, :row_key, :row_index, :data_json)
                """),
                {
                    "dataset": "campaign_queue",
                    "row_key": "lead-1",
                    "row_index": 0,
                    "data_json": '{"lead_id": "lead-1", "email": "test@example.com"}',
                },
            )

        migrated = db_store.migrate_legacy_tables(drop_legacy=True)
        self.assertEqual(migrated, [("campaign_queue", 1)])
        rows = read_csv(Path(self.tmp.name) / "campaign_queue.csv")
        self.assertEqual(
            rows,
            [{"lead_id": "lead-1", "email": "test@example.com", "organisation_id": "1"}],
        )
        with db_store.connection() as conn:
            self.assertTrue(db_store.table_exists(conn, "campaign_queue"))
            self.assertFalse(any(column.startswith("_") for column in db_store.current_columns(conn, "campaign_queue")))
            self.assertFalse(db_store.table_exists(conn, db_store.LEGACY_ROW_TABLE))

    def test_migrates_existing_underscore_internal_columns(self) -> None:
        create_engine, _, text = db_store.load_sqlalchemy()
        engine = create_engine(os.environ["DATABASE_URL"], future=True)
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE prospects (
                  _nightfall_row_key VARCHAR(191) NOT NULL PRIMARY KEY,
                  _nightfall_row_index INTEGER NOT NULL,
                  _nightfall_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  lead_id TEXT NOT NULL
                )
            """))
            conn.execute(
                text("""
                    INSERT INTO prospects (_nightfall_row_key, _nightfall_row_index, lead_id)
                    VALUES ('lead-1', 0, 'lead-1')
                """),
            )

        migrated = db_store.migrate_current_tables()
        self.assertIn("prospects", migrated)
        with db_store.connection() as conn:
            columns = db_store.current_columns(conn, "prospects")
            self.assertIn("nightfall_row_key", columns)
            self.assertIn("nightfall_row_index", columns)
            self.assertIn("nightfall_updated_at", columns)
            self.assertIn("organisation_id", columns)
            self.assertFalse(any(column.startswith("_") for column in columns))


if __name__ == "__main__":
    unittest.main()
