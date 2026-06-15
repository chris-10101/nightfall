# Vesra Test Campaign Runbook

This test sends a four-message sequence to one inbox over three hours.

## Setup

1. Copy config files:

```bash
cp lead-gen/config/outbound_config.example.json lead-gen/config/outbound_config.json
cp lead-gen/config/test_campaign_config.example.json lead-gen/config/test_campaign_config.json
```

2. Keep `from_email` as the placeholder/test sender until the new outbound domain is ready.

3. Set test-only environment variables:

```bash
export VESRA_TEST_RECIPIENT="your-other-email@example.com"
export VESRA_SMTP_USERNAME="your-google-login"
export VESRA_SMTP_APP_PASSWORD="your-google-app-password"
```

4. In `lead-gen/config/outbound_config.json`, set:

```json
"review_required_before_send": false
```

Only do that after the test recipient and sender are correct.

## Dry-Run

Initialise and dry-run the first due email:

```bash
python lead-gen/scripts/outreach/run_test_campaign.py --init
```

## Actual Send

Send the first due message:

```bash
python lead-gen/scripts/outreach/run_test_campaign.py --send
```

Run the same command roughly every hour for the next three hours. Each run sends at most one due message by default.

## Scheduled Test

Use an automation every 30 minutes for the next few hours to run:

```bash
python lead-gen/scripts/outreach/run_test_campaign.py --send
```

The script will only send if a step is due and still pending.

## State

The state file is:

```text
lead-gen/tests/test_campaign_state.csv
```

Statuses:

- `pending`
- `sent`

If an SMTP error happens, `last_error` is populated.
