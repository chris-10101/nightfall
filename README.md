# Nightfall

Automation systems and operational scripts.

## Automations

- `automations/vesra-outbound/` - Vesra outbound lead generation, enrichment, campaign queueing, unsubscribe/reply webhook, and weekly reporting.

Runtime data and secrets are intentionally not stored in this repository. Production CSV state should live on the server under `/var/lib/vesra/lead-gen-data`, and secrets should live in `/etc/vesra/outbound.env`.

GitHub Actions deploys use repo-level Nightfall secrets:

```text
NIGHTFALL_DROPLET_HOST
NIGHTFALL_DROPLET_USER
NIGHTFALL_DROPLET_SSH_KEY
```
