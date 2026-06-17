import unittest
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from outreach.build_campaign_queue import choose_campaign_variant, selected_outreach_config
from outreach.send_outreach_smtp import materialize_sequence_row


OUTREACH = {
    "subject": "A subject",
    "body_template": "A body",
    "variants": [
        {"id": "a", "subject": "A subject", "body_template": "A body"},
        {"id": "b", "subject": "B subject", "body_template": "B body"},
        {"id": "c", "subject": "C subject", "body_template": "C body"},
    ],
}


class CampaignVariantsTest(unittest.TestCase):
    def test_existing_campaign_variant_is_preserved(self) -> None:
        row = {"company_name": "Acme HR", "website_url": "https://acmehr.example"}
        variant = choose_campaign_variant(row, {"campaign_variant": "b"}, OUTREACH)
        self.assertEqual(variant, "b")

    def test_new_campaign_variant_is_valid_and_stable(self) -> None:
        row = {"company_name": "Acme HR", "website_url": "https://acmehr.example"}
        first = choose_campaign_variant(row, {}, OUTREACH)
        second = choose_campaign_variant(row, {}, OUTREACH)
        self.assertIn(first, {"a", "b", "c"})
        self.assertEqual(first, second)

    def test_selected_outreach_config_matches_variant(self) -> None:
        selected = selected_outreach_config(OUTREACH, "c")
        self.assertEqual(selected["subject"], "C subject")
        self.assertEqual(selected["body_template"], "C body")

    def test_follow_up_materializes_from_assigned_variant(self) -> None:
        row = {
            "icp_profile": "hr_consultancy_partner",
            "campaign_variant": "b",
            "send_count": "1",
            "decision_maker_name": "Sarah Bradley",
            "company_name": "The HR Dept Bradford",
            "personalisation": "supports SMEs",
            "city_region": "Bradford",
            "subject": "Old subject",
            "draft_body": "Old body",
        }
        materialized = materialize_sequence_row(row)
        self.assertEqual(materialized["subject"], "Re: Revenue without additional consulting hours")
        self.assertIn("Most HR consultancies grow", materialized["draft_body"])
        self.assertEqual(materialized["campaign_step"], "4")


if __name__ == "__main__":
    unittest.main()
