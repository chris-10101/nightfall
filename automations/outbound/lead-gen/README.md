# Vesra Lead Gen System

Current active campaigns are controlled by `config/icp_profiles.json`.

Active ICPs currently include HR consultancies and franchise/franchisor partners.
Accountancies, employment law firms, recruitment agencies, and general
professional services firms are not part of the active campaign unless a future
ICP profile explicitly enables them.

## Folder Layout

- `config/` - sender, ICP, and test campaign configuration examples.
- `data/` - local development/export state. Production state should live in MySQL.
- `docs/` - ICP, outreach templates, partner KB, monitor spec, and daily pipeline notes.
- `tests/` - test campaign runbook and state file.
- `outreach/batches/` - reviewed outreach batches ready for dry-run or sending.

## Key Files

- `data/prospects.csv` - local/export copy of source-backed prospect state.
- `data/campaign_queue.csv` - local/export copy of contactable outbound queue state.
- `data/suppression.csv` - local/export copy of opt-outs, no-thanks, and blocked contacts/domains.
- `data/reply_events.csv` - local/export copy of reply and unsubscribe event logs.
- `config/outbound_config.example.json` - sender/SMTP config template.
- `config/test_campaign_config.example.json` - four-step test campaign template.
- `docs/vesra_partner_kb.md` - source content for dynamic replies and campaign language.
- `docs/data_sources.md` - source quality notes for curated, sitemap, search, and Companies House rows.

## Common Commands

Build the outbound queue from the current CSVs:

```bash
python lead-gen/scripts/outreach/build_campaign_queue.py
```

Production database mode:

```bash
export NIGHTFALL_STORAGE_BACKEND=database
export DATABASE_URL="<mysql+pymysql connection string>"
python lead-gen/scripts/maintenance/init_database.py
python lead-gen/scripts/maintenance/import_csv_state_to_database.py --data-dir /var/lib/vesra/lead-gen-data
```

Prepare a reviewed batch:

```bash
python lead-gen/scripts/outreach/prepare_outreach_batch.py --limit 10
```

Dry-run a batch:

```bash
python lead-gen/scripts/outreach/send_outreach_smtp.py lead-gen/outreach/batches/batch_YYYY-MM-DD.csv
```

Run the unsubscribe/reply webhook server:

```bash
export VESRA_UNSUBSCRIBE_SECRET="generate-a-long-random-secret"
export VESRA_MAILGUN_WEBHOOK_TOKEN="generate-another-random-secret"
python lead-gen/scripts/outreach/unsubscribe_server.py --host 127.0.0.1 --port 8088
```

Initialise the test campaign:

```bash
python lead-gen/scripts/outreach/run_test_campaign.py --init
```

Run due test campaign step in dry-run mode:

```bash
python lead-gen/scripts/outreach/run_test_campaign.py
```
