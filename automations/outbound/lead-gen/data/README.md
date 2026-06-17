# Runtime Data

Live state files are intentionally not committed.

Production should use MySQL-backed storage by setting:

```text
NIGHTFALL_STORAGE_BACKEND=database
DATABASE_URL=<mysql+pymysql connection string>
```

CSV files are now treated as local development, import, export, and backup
artifacts. If CSV storage is used temporarily, store it outside the Git
checkout, for example:

```text
/var/lib/vesra/lead-gen-data/prospects.csv
/var/lib/vesra/lead-gen-data/campaign_queue.csv
/var/lib/vesra/lead-gen-data/suppression.csv
/var/lib/vesra/lead-gen-data/reply_events.csv
```

See `lead-gen/docs/database_storage.md` for database initialisation and
migration commands.
