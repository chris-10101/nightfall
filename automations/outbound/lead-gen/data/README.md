# Runtime Data

Live CSV files are intentionally not committed.

Production data should be stored outside the Git checkout, for example:

```text
/var/lib/vesra/lead-gen-data/prospects.csv
/var/lib/vesra/lead-gen-data/campaign_queue.csv
/var/lib/vesra/lead-gen-data/suppression.csv
/var/lib/vesra/lead-gen-data/reply_events.csv
```
