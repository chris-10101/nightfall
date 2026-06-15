# Nightfall

Automation systems and operational scripts.

## Automations

- `automations/outbound/` - reusable outbound automation structure for global tools, tenant configs, campaign configs, and systemd templates.
- `automations/vesra-outbound/` - Vesra outbound lead generation, enrichment, campaign queueing, unsubscribe/reply webhook, and weekly reporting.

`automations/outbound/` is the canonical structure for new businesses and new
ICPs. `automations/vesra-outbound/` remains the current production-compatible
implementation for Vesra while the shared engine is extracted.

Runtime data and secrets are intentionally not stored in this repository. Production CSV state should live on the server under `/var/lib/vesra/lead-gen-data`, and secrets should live in `/etc/vesra/outbound.env`.

GitHub Actions deploys use repo-level Nightfall secrets:

```text
NIGHTFALL_DROPLET_HOST
NIGHTFALL_DROPLET_USER
NIGHTFALL_DROPLET_SSH_KEY
```
