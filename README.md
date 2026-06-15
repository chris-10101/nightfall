# Nightfall

Automation systems and operational scripts.

## Automations

- `automations/outbound/` - reusable outbound automation structure, Vesra outbound runtime, global tools, tenant configs, campaign configs, and systemd units.

`automations/outbound/` is the canonical structure for new businesses, new ICPs,
and the current Vesra production automation.

Runtime data and secrets are intentionally not stored in this repository. Production CSV state should live on the server under `/var/lib/vesra/lead-gen-data`, and secrets should live in `/etc/vesra/outbound.env`.

GitHub Actions deploys use repo-level Nightfall secrets:

```text
NIGHTFALL_DROPLET_HOST
NIGHTFALL_DROPLET_USER
NIGHTFALL_DROPLET_SSH_KEY
```
