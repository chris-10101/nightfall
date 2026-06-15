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

## Production Runtime

Recommended server paths:

```text
/opt/nightfall/automations/vesra-outbound      # deployed code
/var/lib/vesra/lead-gen-data                   # live CSV data/state
/etc/vesra/outbound.env                        # secrets and API keys
```

Do not commit live prospect data, campaign queues, suppressions, SMTP credentials, Mailgun tokens, Hunter keys, or generated batch files.
