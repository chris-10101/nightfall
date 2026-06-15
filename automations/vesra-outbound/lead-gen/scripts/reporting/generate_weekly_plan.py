from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse

from weekly_reporter import (
    DEFAULT_RECIPIENT,
    friday_for_week,
    generate_plan_markdown,
    parse_week_start,
    save_and_optionally_send,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Sunday lead-gen weekly plan.")
    parser.add_argument("--week-start", help="Sunday date for the plan week, in YYYY-MM-DD format.")
    parser.add_argument("--output", help="Optional markdown output path.")
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT, help="Report email recipient.")
    parser.add_argument("--subject", help="Email subject. Defaults to the plan week.")
    parser.add_argument("--send", action="store_true", help="Send the plan by SMTP. Omit for dry-run.")
    args = parser.parse_args()

    week_start = parse_week_start(args.week_start)
    week_end = friday_for_week(week_start)
    markdown = generate_plan_markdown(week_start)
    subject = args.subject or f"Vesra weekly lead-gen plan: {week_start.isoformat()} to {week_end.isoformat()}"
    save_and_optionally_send(
        kind="plan",
        markdown=markdown,
        output=args.output,
        week_start=week_start,
        send=args.send,
        recipient=args.recipient,
        subject=subject,
    )


if __name__ == "__main__":
    main()
