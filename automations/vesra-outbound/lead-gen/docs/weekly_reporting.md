# Weekly Lead-Gen Planning and Reporting

The weekly reporting scripts generate markdown from the existing lead-gen CSVs
and config files. They do not send email unless `--send` is passed.

Generated files are saved under:

```text
lead-gen/reports/weekly/
```

## Sunday Weekly Plan

Generate the plan for the current week:

```bash
python lead-gen/scripts/reporting/generate_weekly_plan.py
```

Generate a plan for a specific Sunday-starting week:

```bash
python lead-gen/scripts/reporting/generate_weekly_plan.py --week-start 2026-06-14
```

Write to a custom path:

```bash
python lead-gen/scripts/reporting/generate_weekly_plan.py --output /tmp/vesra_weekly_plan.md
```

Email the plan after saving it:

```bash
python lead-gen/scripts/reporting/generate_weekly_plan.py --send --recipient chris@vesra.io
```

## Friday Weekly Report

Generate the report for the current week:

```bash
python lead-gen/scripts/reporting/generate_weekly_report.py
```

Generate a report for a specific Sunday-starting week:

```bash
python lead-gen/scripts/reporting/generate_weekly_report.py --week-start 2026-06-14
```

Email the report after saving it:

```bash
python lead-gen/scripts/reporting/generate_weekly_report.py --send --recipient chris@vesra.io
```

## Email Requirements

Email uses the existing SMTP settings in `lead-gen/config/outbound_config.json`
or falls back to `lead-gen/config/outbound_config.example.json`.

Set the configured SMTP credential environment variables before using `--send`.
For the current config these are:

```bash
export VESRA_SMTP_USERNAME="..."
export VESRA_SMTP_APP_PASSWORD="..."
```

The default recipient is `chris@vesra.io`. Override it with `--recipient`.

## Source Data

The scripts read:

- `lead-gen/config/outbound_config.json`
- `lead-gen/config/icp_profiles.json`
- `lead-gen/data/prospects.csv`
- `lead-gen/data/campaign_queue.csv`
- `lead-gen/data/suppression.csv`
- `lead-gen/outreach/batches/batch_YYYY-MM-DD.csv`

They summarize active ICPs, prospect totals, email-backed prospects, ready queue
volume, batch activity, sends, replies, bounces, and suppressions for the
Sunday-to-Friday reporting window.

## Codex Automations

Two Codex cron automations are active:

- `vesra-weekly-outbound-plan`: Sundays at 18:00 Europe/London.
- `vesra-weekly-outbound-report`: Fridays at 16:00 Europe/London.

Both run from:

```text
/Users/chrissmith/Desktop/Nightfall/vesra
```

The Sunday automation runs the weekly plan script with `--send`.
The Friday automation runs the weekly report script with `--send`.

If SMTP environment variables are unavailable, the automation falls back to
generating the markdown report without sending email and reports the missing
SMTP configuration.
