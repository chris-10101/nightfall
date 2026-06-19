import unittest
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from enrichment.enrich_public_web import best_email, is_valid_business_email
from discovery import discover_email_backed_icp
from discovery.discover_email_backed_icp import (
    blocked_url,
    brand_match_score,
    email_matches_website,
    franchiseinfo_profile_urls,
    has_franchise_site_signal,
    hr_dept_licensee_urls,
    is_generic_company_name,
    name_from_franchiseinfo_title,
    name_from_hr_dept_title,
)


class BrokenPipeStdout:
    def write(self, value: str) -> int:
        raise BrokenPipeError()

    def flush(self) -> None:
        raise BrokenPipeError()


class EmailValidationTest(unittest.TestCase):
    def test_rejects_free_personal_email_domains(self) -> None:
        self.assertFalse(is_valid_business_email("owner@gmail.com"))
        self.assertFalse(is_valid_business_email("owner@outlook.com"))
        self.assertFalse(is_valid_business_email("owner@yahoo.co.uk"))

    def test_rejects_hash_like_email_local_parts(self) -> None:
        self.assertFalse(is_valid_business_email("22286b56dbaf4d27aa4f1bed2e2eed06@hrdept.co.uk"))

    def test_best_email_prefers_valid_business_domain(self) -> None:
        self.assertEqual(
            best_email({"owner@gmail.com", "hello@acme-hr.co.uk"}),
            "hello@acme-hr.co.uk",
        )

    def test_discovery_requires_email_domain_to_match_website_domain(self) -> None:
        self.assertTrue(email_matches_website("hello@acme-hr.co.uk", "https://www.acme-hr.co.uk/contact"))
        self.assertTrue(email_matches_website("hello@mail.acme-hr.co.uk", "https://acme-hr.co.uk"))
        self.assertFalse(email_matches_website("micah@micahrich.com", "http://www.cmlpeoplesolutions.com"))

    def test_discovery_blocks_low_intent_result_urls_and_generic_names(self) -> None:
        self.assertTrue(blocked_url("https://example.com/resource/blogs/what-is-hr/"))
        self.assertTrue(blocked_url("https://example.com/news/hr-consultancy-guide/"))
        self.assertFalse(blocked_url("https://example.com/contact"))
        self.assertTrue(is_generic_company_name("HR 101"))
        self.assertTrue(is_generic_company_name("HR Consultant"))
        self.assertFalse(is_generic_company_name("Acme HR Ltd"))

    def test_discovery_emit_ignores_broken_pipe(self) -> None:
        original_stdout = sys.stdout
        original_output_available = discover_email_backed_icp.OUTPUT_AVAILABLE
        try:
            discover_email_backed_icp.OUTPUT_AVAILABLE = True
            sys.stdout = BrokenPipeStdout()
            discover_email_backed_icp.emit("progress line")
            discover_email_backed_icp.emit("suppressed line")
            self.assertFalse(discover_email_backed_icp.OUTPUT_AVAILABLE)
        finally:
            sys.stdout = original_stdout
            discover_email_backed_icp.OUTPUT_AVAILABLE = original_output_available

    def test_hr_dept_licensee_sitemap_filters_to_location_roots(self) -> None:
        original_fetch_text = discover_email_backed_icp.fetch_text
        xml = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://www.hrdept.co.uk/leeds-south</loc></url>
          <url><loc>https://www.hrdept.co.uk/leeds-south/providing-hr-support-to-leeds-businesses</loc></url>
          <url><loc>https://www.hrdept.co.uk/contact-us</loc></url>
        </urlset>
        """
        try:
            discover_email_backed_icp.fetch_text = lambda url, timeout: xml
            self.assertEqual(hr_dept_licensee_urls(5), ["https://www.hrdept.co.uk/leeds-south"])
        finally:
            discover_email_backed_icp.fetch_text = original_fetch_text

    def test_franchiseinfo_profile_urls_extracts_unique_profile_pages(self) -> None:
        original_fetch_text = discover_email_backed_icp.fetch_text
        original_categories = discover_email_backed_icp.FRANCHISEINFO_CATEGORY_URLS
        html = """
        <a href="https://www.franchiseinfo.co.uk/franchise/bluebird-care/">Bluebird</a>
        <a href="https://www.franchiseinfo.co.uk/franchise/bluebird-care/request-information/">Request</a>
        <a href="/franchise/caremark/">Caremark</a>
        <a href="https://www.franchiseinfo.co.uk/franchise/bluebird-care/">Duplicate</a>
        """
        try:
            discover_email_backed_icp.FRANCHISEINFO_CATEGORY_URLS = ["https://www.franchiseinfo.co.uk/full-franchise-directory/care-franchises/"]
            discover_email_backed_icp.fetch_text = lambda url, timeout: html
            self.assertEqual(
                franchiseinfo_profile_urls(5),
                [
                    "https://www.franchiseinfo.co.uk/franchise/bluebird-care/",
                    "https://www.franchiseinfo.co.uk/franchise/caremark/",
                ],
            )
        finally:
            discover_email_backed_icp.fetch_text = original_fetch_text
            discover_email_backed_icp.FRANCHISEINFO_CATEGORY_URLS = original_categories

    def test_source_name_and_franchise_quality_helpers(self) -> None:
        self.assertEqual(
            name_from_hr_dept_title("Leeds South | HR Dept", "https://www.hrdept.co.uk/leeds-south"),
            "The HR Dept Leeds South",
        )
        self.assertEqual(
            name_from_franchiseinfo_title("Bluebird Care Franchise | FranchiseInfo", "https://example.com"),
            "Bluebird Care Franchise",
        )
        self.assertTrue(has_franchise_site_signal("We support franchisees across our UK network."))
        self.assertGreaterEqual(
            brand_match_score("Bluebird Care", "https://www.bluebirdcare.co.uk/franchise", "Bluebird Care franchise"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
