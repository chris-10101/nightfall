import unittest
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from enrichment.enrich_public_web import best_email, is_valid_business_email


class EmailValidationTest(unittest.TestCase):
    def test_rejects_free_personal_email_domains(self) -> None:
        self.assertFalse(is_valid_business_email("owner@gmail.com"))
        self.assertFalse(is_valid_business_email("owner@outlook.com"))
        self.assertFalse(is_valid_business_email("owner@yahoo.co.uk"))

    def test_best_email_prefers_valid_business_domain(self) -> None:
        self.assertEqual(
            best_email({"owner@gmail.com", "hello@acme-hr.co.uk"}),
            "hello@acme-hr.co.uk",
        )


if __name__ == "__main__":
    unittest.main()
