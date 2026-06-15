# Vesra Outbound Automation

This automation handles Vesra partner lead generation, enrichment, outreach queueing, unsubscribe/reply handling, and weekly reporting.

Source code lives in `lead-gen/scripts`. Runtime CSV state is excluded from Git and should be stored separately on the deployment server.

## Local Checks

```bash
python3.11 lead-gen/tests/test_unsubscribe_flow.py
python3.11 -m compileall -q lead-gen/scripts lead-gen/tests
python3.11 lead-gen/scripts/maintenance/validate_icp_profiles.py
```

Use Python 3.10 or newer. The system Python on older macOS releases may be 3.9,
which is too old for this codebase.

Production also needs `openpyxl` because shared import headers are loaded by
the discovery scripts. On Ubuntu this is installed with:

```bash
apt-get install -y python3-openpyxl
```

Install `sentry-sdk` as well when production error reporting is enabled:

```bash
apt-get install -y python3-sentry-sdk
```

## Production Runtime

Recommended server paths:

```text
/opt/nightfall/automations/vesra-outbound      # deployed code
/var/lib/vesra/lead-gen-data                   # live CSV data/state
/var/lib/vesra/test-campaign                   # internal test campaign state
/etc/vesra/outbound.env                        # secrets and API keys
```

Set these environment variables for production services and scheduled jobs:

```text
VESRA_LEAD_GEN_DATA_DIR=/var/lib/vesra/lead-gen-data
VESRA_LEAD_GEN_CONFIG_DIR=/etc/vesra/config
VESRA_LEAD_GEN_REPORT_DIR=/var/lib/vesra/reports
VESRA_LEAD_GEN_BATCH_DIR=/var/lib/vesra/outreach-batches
VESRA_LEAD_GEN_TEST_DIR=/var/lib/vesra/test-campaign
SENTRY_DSN=<sentry project dsn>
SENTRY_ENVIRONMENT=production
```

Do not commit live prospect data, campaign queues, suppressions, SMTP credentials, Mailgun tokens, Hunter keys, or generated batch files.

## Server Automations

Systemd units live in `deploy/systemd/`.

Production schedule:

```text
vesra-daily-discovery.timer   Mon-Fri 07:30 Europe/London
vesra-daily-enrichment.timer  Mon-Fri 08:45 Europe/London
```

Discovery adds email-backed rows for both active ICPs, capped by environment
limits. Enrichment runs deterministic enrichment and rebuilds the campaign
queue. These jobs do not send production emails.
