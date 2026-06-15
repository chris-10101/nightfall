import csv
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from core.csv_store import write_csv_atomic
from outreach import send_outreach_smtp, suppression
from outreach.unsubscribe_server import UnsubscribeHandler
from outreach.unsubscribe_tokens import unsubscribe_url


SECRET = "test-secret"


class UnsubscribeFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.queue_path = self.data_dir / "campaign_queue.csv"
        self.prospects_path = self.data_dir / "prospects.csv"
        self.suppression_path = self.data_dir / "suppression.csv"
        self.reply_events_path = self.data_dir / "reply_events.csv"

        self.original_paths = (
            suppression.QUEUE_PATH,
            suppression.PROSPECTS_PATH,
            suppression.SUPPRESSION_PATH,
            suppression.REPLY_EVENTS_PATH,
        )
        suppression.QUEUE_PATH = self.queue_path
        suppression.PROSPECTS_PATH = self.prospects_path
        suppression.SUPPRESSION_PATH = self.suppression_path
        suppression.REPLY_EVENTS_PATH = self.reply_events_path

        queue_headers = [
            "lead_id",
            "campaign_name",
            "company_name",
            "company_domain",
            "email",
            "draft_body",
            "subject",
            "campaign_status",
            "last_reply_at",
            "reply_status",
            "next_action",
            "eligibility_status",
            "eligibility_reasons",
        ]
        prospects_headers = ["lead_id", "company_name", "company_domain", "email", "status", "notes"]
        self.rows = [
            self.row("lead-get", "GET Example", "get.example", "person@get.example"),
            self.row("lead-post", "POST Example", "post.example", "person@post.example"),
            self.row("lead-reply", "Reply Example", "reply.example", "person@reply.example"),
        ]
        write_csv_atomic(self.queue_path, self.rows, queue_headers)
        write_csv_atomic(
            self.prospects_path,
            [
                {
                    "lead_id": row["lead_id"],
                    "company_name": row["company_name"],
                    "company_domain": row["company_domain"],
                    "email": row["email"],
                    "status": "active",
                    "notes": "",
                }
                for row in self.rows
            ],
            prospects_headers,
        )
        with self.suppression_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=["email", "domain", "company_name", "reason", "added_at"])
            writer.writeheader()

        os.environ["VESRA_UNSUBSCRIBE_SECRET"] = SECRET
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), UnsubscribeHandler)
        self.server.secret = SECRET
        self.server.webhook_token = "webhook-token"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        (
            suppression.QUEUE_PATH,
            suppression.PROSPECTS_PATH,
            suppression.SUPPRESSION_PATH,
            suppression.REPLY_EVENTS_PATH,
        ) = self.original_paths
        os.environ.pop("VESRA_UNSUBSCRIBE_SECRET", None)
        self.tmp.cleanup()

    def row(self, lead_id: str, company_name: str, domain: str, email: str) -> dict[str, str]:
        return {
            "lead_id": lead_id,
            "campaign_name": "test_campaign",
            "company_name": company_name,
            "company_domain": domain,
            "email": email,
            "draft_body": "Hi,\n\nTest body.",
            "subject": "Test subject",
            "campaign_status": "sent",
            "last_reply_at": "",
            "reply_status": "",
            "next_action": "monitor_reply",
            "eligibility_status": "eligible",
            "eligibility_reasons": "",
        }

    def config(self) -> dict[str, str]:
        return {
            "sender_name": "Chris Smith",
            "from_email": "chris@getvesra.co.uk",
            "reply_to": "chris@getvesra.co.uk",
            "unsubscribe_mailto": "chris@getvesra.co.uk",
            "unsubscribe_base_url": f"{self.base_url}/unsubscribe",
            "unsubscribe_secret_env": "VESRA_UNSUBSCRIBE_SECRET",
            "unsubscribe_subject": "Unsubscribe",
            "unsubscribe_text": "If this is not relevant, reply unsubscribe and I will not contact you again.",
        }

    def read_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8-sig") as csv_file:
            return list(csv.DictReader(csv_file))

    def test_link_post_reply_and_email_headers(self) -> None:
        config = self.config()
        message = send_outreach_smtp.build_message(config, self.rows[0])
        self.assertIn("List-Unsubscribe-Post", message)
        self.assertTrue(message["List-Unsubscribe"].startswith(f"<{self.base_url}/unsubscribe?token="))
        plain_body = message.get_body(("plain",)).get_content()
        html_body = message.get_body(("html",)).get_content()
        self.assertIn(f"Unsubscribe: {self.base_url}/unsubscribe?token=", plain_body)
        self.assertIn(">unsubscribe here</a>", html_body)
        self.assertIn(f'href="{self.base_url}/unsubscribe?token=', html_body)

        get_url = unsubscribe_url(config, self.rows[0])
        with urlopen(get_url, timeout=5) as response:
            self.assertEqual(response.status, 200)

        post_url = unsubscribe_url(config, self.rows[1])
        request = Request(post_url, data=b"", method="POST")
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)

        inbound_body = urlencode(
            {
                "sender": self.rows[2]["email"],
                "recipient": "chris@getvesra.co.uk",
                "subject": "Re: Test subject",
                "stripped-text": "unsubscribe please",
                "message-id": "reply-message-id",
            }
        ).encode("utf-8")
        inbound = Request(
            f"{self.base_url}/mailgun/inbound?token=webhook-token",
            data=inbound_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(inbound, timeout=5) as response:
            self.assertEqual(response.status, 200)

        suppressions = self.read_rows(self.suppression_path)
        self.assertEqual(len(suppressions), 3)
        self.assertEqual(
            set(suppressions[0].keys()),
            set(suppression.SUPPRESSION_HEADERS),
        )
        self.assertEqual({row["reason"] for row in suppressions}, {"unsubscribe"})

        queue = self.read_rows(self.queue_path)
        self.assertTrue(all(row["campaign_status"] == "stopped" for row in queue))
        self.assertTrue(all(row["next_action"] == "suppressed" for row in queue))
        self.assertTrue(all(row["reply_status"] == "unsubscribed" for row in queue[:2]))
        self.assertEqual(queue[2]["reply_status"], "unsubscribe")

        prospects = self.read_rows(self.prospects_path)
        self.assertTrue(all(row["status"] == "do_not_contact" for row in prospects))

        replies = self.read_rows(self.reply_events_path)
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["classification"], "unsubscribe")
        self.assertEqual(replies[0]["matched_lead_id"], "lead-reply")


if __name__ == "__main__":
    unittest.main()
