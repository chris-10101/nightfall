import unittest
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from enrichment.enrich_public_web import best_email, is_valid_business_email
from discovery.discover_email_backed_icp import email_matches_website


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

    def test_discovery_requires_email_domain_to_match_website_domain(self) -> None:
        self.assertTrue(email_matches_website("hello@acme-hr.co.uk", "https://www.acme-hr.co.uk/contact"))
        self.assertTrue(email_matches_website("hello@mail.acme-hr.co.uk", "https://acme-hr.co.uk"))
        self.assertFalse(email_matches_website("micah@micahrich.com", "http://www.cmlpeoplesolutions.com"))


if __name__ == "__main__":
    unittest.main()
