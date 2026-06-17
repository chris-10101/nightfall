# Database Storage

Production outbound state can run from MySQL instead of local CSV files.

## Runtime Env

Set these values in the production environment file, not in Git:

```text
NIGHTFALL_STORAGE_BACKEND=database
DATABASE_URL=<mysql+pymysql connection string>
```

`VESRA_STORAGE_BACKEND=database` is also supported for backwards-compatible
tenant-specific configuration, but `NIGHTFALL_STORAGE_BACKEND` is preferred.

Do not commit `DATABASE_URL`. It contains database credentials.

## Storage Model

The first database-backed implementation stores the existing CSV-shaped runtime
datasets in MySQL tables:

- `nightfall_csv_headers`
- `nightfall_csv_rows`

This keeps the existing discovery, enrichment, queue, suppression, reply, and
agent scripts working while moving production state out of local files.

The database datasets correspond to the previous CSV names:

- `prospects`
- `campaign_queue`
- `suppression`
- `reply_events`
- `agent_events`
- generated batch datasets

## Initialisation

From `automations/outbound`:

```bash
.venv/bin/python lead-gen/scripts/maintenance/init_database.py
```

## Import Existing CSV State

Before switching production to database mode, import the current runtime CSVs:

```bash
.venv/bin/python lead-gen/scripts/maintenance/import_csv_state_to_database.py \
  --data-dir /var/lib/vesra/lead-gen-data
```

Then set:

```text
NIGHTFALL_STORAGE_BACKEND=database
```

and restart the services.

## Export for Review or Backup

To export database state back to CSV files:

```bash
.venv/bin/python lead-gen/scripts/maintenance/export_database_state_to_csv.py \
  --output-dir /var/lib/vesra/lead-gen-data-export
```

These exports are review/backup artifacts only. The database remains the source
of truth when `NIGHTFALL_STORAGE_BACKEND=database`.
