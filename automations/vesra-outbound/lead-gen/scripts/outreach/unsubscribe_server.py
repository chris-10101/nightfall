from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
from email import policy
from email.parser import BytesParser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from outreach.suppression import add_suppression, record_reply
from outreach.unsubscribe_tokens import DEFAULT_SECRET_ENV, verify_token


MAX_BODY_BYTES = 5_000_000


class UnsubscribeHandler(BaseHTTPRequestHandler):
    server_version = "VesraUnsubscribe/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.respond_json({"ok": True})
            return
        if parsed.path != "/unsubscribe":
            self.respond_not_found()
            return
        query = parse_qs(parsed.query)
        token = first(query, "token")
        self.process_unsubscribe_token(token, response_format="html")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/unsubscribe":
            fields = self.parse_post_fields()
            query = parse_qs(parsed.query)
            token = fields.get("token") or first(query, "token")
            self.process_unsubscribe_token(token, response_format="json")
            return
        if parsed.path != "/mailgun/inbound":
            self.respond_not_found()
            return
        fields = self.parse_post_fields()
        if self.server.webhook_token:
            supplied = fields.get("webhook_token") or first(parse_qs(parsed.query), "token")
            if supplied != self.server.webhook_token:
                self.respond_json({"ok": False, "error": "unauthorized"}, status=401)
                return
        sender = fields.get("sender") or fields.get("from") or fields.get("From") or ""
        recipient = fields.get("recipient") or fields.get("to") or fields.get("To") or ""
        subject = fields.get("subject") or fields.get("Subject") or ""
        body = (
            fields.get("stripped-text")
            or fields.get("body-plain")
            or fields.get("text")
            or fields.get("body")
            or ""
        )
        message_id = fields.get("Message-Id") or fields.get("message-id") or fields.get("Message-ID") or ""
        classification = record_reply(
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            message_id=message_id,
        )
        self.respond_json({"ok": True, "classification": classification})

    def process_unsubscribe_token(self, token: str, response_format: str) -> None:
        if not token:
            self.respond_unsubscribe_error("Missing unsubscribe token.", response_format, status=400)
            return
        try:
            payload = verify_token(token, self.server.secret)
            add_suppression(
                email=payload.get("email", ""),
                domain=payload.get("company_domain", ""),
                company_name=payload.get("company_name", ""),
                reason="unsubscribe",
                source="unsubscribe_link",
                source_message_id=payload.get("lead_id", ""),
            )
        except Exception as exc:
            self.respond_unsubscribe_error(f"Could not process unsubscribe: {str(exc)}", response_format, status=400)
            return
        message = "You have been unsubscribed. No further Vesra partner campaign emails will be sent."
        if response_format == "json":
            self.respond_json({"ok": True, "message": message})
        else:
            self.respond_html(message)

    def parse_post_fields(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length > MAX_BODY_BYTES:
            raise ValueError("Request body too large.")
        raw_body = self.rfile.read(content_length)
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("application/json"):
            return {str(key): str(value or "") for key, value in json.loads(raw_body.decode("utf-8")).items()}
        if content_type.startswith("application/x-www-form-urlencoded"):
            return {key: values[0] for key, values in parse_qs(raw_body.decode("utf-8")).items()}
        if content_type.startswith("multipart/form-data"):
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + raw_body
            )
            fields: dict[str, str] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                value = part.get_content()
                fields[str(name)] = value if isinstance(value, str) else str(value)
            return fields
        return {"body": raw_body.decode("utf-8", errors="replace")}

    def respond_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, message: str, status: int = 200) -> None:
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Vesra unsubscribe</title></head>"
            f"<body><p>{escape(message)}</p></body></html>"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_not_found(self) -> None:
        self.respond_json({"ok": False, "error": "not_found"}, status=404)

    def respond_unsubscribe_error(self, message: str, response_format: str, status: int) -> None:
        if response_format == "json":
            self.respond_json({"ok": False, "error": message}, status=status)
        else:
            self.respond_html(message, status=status)

    def log_message(self, format: str, *args) -> None:
        return


def first(values: dict[str, list[str]], key: str) -> str:
    items = values.get(key) or []
    return items[0] if items else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Vesra unsubscribe/reply webhook server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--secret-env", default=DEFAULT_SECRET_ENV)
    parser.add_argument("--webhook-token-env", default="VESRA_MAILGUN_WEBHOOK_TOKEN")
    args = parser.parse_args()

    secret = os.environ.get(args.secret_env, "")
    if not secret:
        raise SystemExit(f"Missing {args.secret_env}. Set it before running the unsubscribe server.")
    server = ThreadingHTTPServer((args.host, args.port), UnsubscribeHandler)
    server.secret = secret
    server.webhook_token = os.environ.get(args.webhook_token_env, "")
    print(f"Listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
