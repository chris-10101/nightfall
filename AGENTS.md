# Nightfall Agent Notes

This repository contains reusable automation systems. Keep project-specific runtime data, secrets, and generated files out of Git.

## Vesra Outbound Deployment

The Vesra outbound automation lives at:

```text
automations/vesra-outbound/
```

Production runs on the DigitalOcean droplet:

```text
178.62.21.99
```

Use GitHub Actions for normal deploys. Do not manually copy edited source files to the server unless recovering from a broken deploy.

### GitHub Actions Deploy

Workflow:

```text
.github/workflows/deploy-vesra-outbound.yml
```

It runs automatically when changes are pushed to `main` under:

```text
.github/workflows/deploy-vesra-outbound.yml
automations/vesra-outbound/**
```

It can also be run manually from GitHub Actions with `workflow_dispatch`.

Required repository secrets:

```text
NIGHTFALL_DROPLET_HOST
NIGHTFALL_DROPLET_USER
NIGHTFALL_DROPLET_SSH_KEY
```

Expected values:

```text
NIGHTFALL_DROPLET_HOST=178.62.21.99
NIGHTFALL_DROPLET_USER=root
NIGHTFALL_DROPLET_SSH_KEY=<private key for the droplet deploy key>
```

The workflow syncs the repository to:

```text
/opt/nightfall/
```

So the deployed Vesra code path is:

```text
/opt/nightfall/automations/vesra-outbound
```

### Production Runtime Files

Live data and secrets are stored outside the Git checkout:

```text
/var/lib/vesra/lead-gen-data      # live CSV data/state
/var/lib/vesra/reports            # generated reports
/var/lib/vesra/outreach-batches   # generated outreach batches
/etc/vesra/config                 # production config
/etc/vesra/outbound.env           # secrets and runtime env
```

The production env file should include:

```text
VESRA_LEAD_GEN_DATA_DIR=/var/lib/vesra/lead-gen-data
VESRA_LEAD_GEN_CONFIG_DIR=/etc/vesra/config
VESRA_LEAD_GEN_REPORT_DIR=/var/lib/vesra/reports
VESRA_LEAD_GEN_BATCH_DIR=/var/lib/vesra/outreach-batches
VESRA_UNSUBSCRIBE_SECRET=<secret>
VESRA_MAILGUN_WEBHOOK_TOKEN=<secret>
VESRA_SMTP_USERNAME=<mailgun smtp username>
VESRA_SMTP_APP_PASSWORD=<mailgun smtp password>
PYTHONDONTWRITEBYTECODE=1
```

Do not commit prospect CSVs, campaign queues, suppression lists, SMTP credentials, Mailgun tokens, Hunter keys, or generated campaign batches.

### Deploy Checks

The workflow runs these checks locally in GitHub Actions and again on the droplet before restarting the webhook:

```bash
python3 lead-gen/tests/test_unsubscribe_flow.py
python3 -m compileall -q lead-gen/scripts lead-gen/tests
python3 lead-gen/scripts/maintenance/validate_icp_profiles.py
```

After syncing, it restarts:

```text
vesra-outbound-webhook.service
```

and verifies:

```bash
systemctl is-active vesra-outbound-webhook.service
curl -fsS http://127.0.0.1:8088/health
```

Useful manual checks:

```bash
ssh -i ~/.ssh/vesra_digitalocean -o IdentitiesOnly=yes root@178.62.21.99
systemctl status vesra-outbound-webhook.service --no-pager -l
journalctl -u vesra-outbound-webhook.service -n 40 --no-pager
curl -fsS http://127.0.0.1:8088/health
curl -fsS http://178.62.21.99/health
curl -fsS https://www.getvesra.co.uk/health
```

### Public Webhook URLs

Use the `www` hostname for outbound unsubscribe links:

```text
https://www.getvesra.co.uk/unsubscribe
```

The root hostname `getvesra.co.uk` has previously had DNS inconsistency, while `www.getvesra.co.uk` has resolved and served correctly through Caddy.

### Production Safety Rules

- Never send production prospect emails without explicit user approval.
- Test campaigns must use user-controlled inboxes only.
- Keep the live campaign queue empty unless a real send has been approved.
- Unsubscribe handling must be automatic and must suppress future sends.
- Do not automate LinkedIn login, connection requests, or messaging.
- Preserve runtime CSV state on the droplet; Git deploys should update code only.
