import os
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from core.csv_store import append_csv_atomic, read_csv, write_csv_atomic


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
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
