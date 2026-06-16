# Nightfall Agent Notes

This repository contains reusable automation systems. Keep project-specific runtime data, secrets, and generated files out of Git.

## Outbound Structure

Canonical reusable outbound structure:

```text
automations/outbound/
  core/
  lead-gen/
  deploy/systemd/
  tools/
  systemd/
  tenants/
```

Use `automations/outbound/tenants/<tenant_id>/` for new businesses and
`automations/outbound/tenants/<tenant_id>/campaigns/<campaign_id>/` for new
ICPs/campaigns.

Vesra production runs from `automations/outbound/`. Do not recreate the old
compatibility folder; it has been extracted into the canonical outbound tree.

## Vesra Outbound Deployment

The Vesra outbound automation lives at:

```text
automations/outbound/
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
automations/outbound/**
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
/opt/nightfall/automations/outbound
```

### Production Runtime Files

Live data and secrets are stored outside the Git checkout:

```text
/var/lib/vesra/lead-gen-data      # live CSV data/state
/var/lib/vesra/reports            # generated reports
/var/lib/vesra/outreach-batches   # generated outreach batches
/var/lib/vesra/test-campaign      # internal test campaign state
/var/lib/vesra/orchestration-runs # contact lifecycle run summaries
/etc/vesra/config                 # production config
/etc/vesra/outbound.env           # secrets and runtime env
```

The production env file should include:

```text
VESRA_LEAD_GEN_DATA_DIR=/var/lib/vesra/lead-gen-data
VESRA_LEAD_GEN_CONFIG_DIR=/etc/vesra/config
VESRA_LEAD_GEN_REPORT_DIR=/var/lib/vesra/reports
VESRA_LEAD_GEN_BATCH_DIR=/var/lib/vesra/outreach-batches
VESRA_LEAD_GEN_TEST_DIR=/var/lib/vesra/test-campaign
VESRA_LEAD_GEN_ORCHESTRATION_DIR=/var/lib/vesra/orchestration-runs
VESRA_LEAD_GEN_KB_DIR=/opt/nightfall/automations/outbound/lead-gen/docs
VESRA_TEST_RECIPIENT=<internal test recipient>
VESRA_AUTO_SEND_ENABLED=false
VESRA_AGENT_SEND_LIMIT=5
VESRA_UNSUBSCRIBE_SECRET=<secret>
VESRA_MAILGUN_WEBHOOK_TOKEN=<secret>
VESRA_SMTP_USERNAME=<mailgun smtp username>
VESRA_SMTP_APP_PASSWORD=<mailgun smtp password>
SENTRY_DSN=<sentry project dsn>
SENTRY_ENVIRONMENT=production
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

### Daily Data Automations

Systemd units for daily data work are stored in:

```text
automations/outbound/deploy/systemd/
```

Installed production units:

```text
vesra-daily-discovery.service
vesra-daily-discovery.timer
vesra-daily-enrichment.service
vesra-daily-enrichment.timer
vesra-daily-orchestrator.service
vesra-daily-orchestrator.timer
vesra-agent-send-approved.service
vesra-agent-send-approved.timer
```

Schedule:

```text
vesra-daily-discovery.timer   Mon-Fri 07:30 Europe/London
vesra-daily-enrichment.timer  Mon-Fri 08:45 Europe/London
vesra-daily-orchestrator.timer Mon-Fri 09:15 Europe/London
vesra-agent-send-approved.timer Mon-Fri 10:15 Europe/London
```

Discovery runs both active ICPs with separate caps:

```text
hr_consultancy_partner  default 10 new email-backed rows/day
franchise               default 10 new email-backed rows/day
```

Enrichment runs deterministic enrichment. The orchestrator owns the contact
lifecycle, rebuilds `campaign_queue.csv`, writes lifecycle columns back to
`prospects.csv` and `campaign_queue.csv`, and stores a JSON run summary under
`/var/lib/vesra/orchestration-runs`.

The daily orchestrator runs `lead-gen/scripts/orchestration/run_agentic_orchestrator.py`.
It first refreshes deterministic lifecycle state, then plans each contact's next
step, selects a registered tool, records reasoning into the CSVs and
`agent_events.csv`, and writes JSON summaries under
`/var/lib/vesra/orchestration-runs`.

Agentic tool execution is capped by `VESRA_AGENTIC_MAX_TOOL_RUNS` and limited to
non-email, non-review tools. The orchestrator must not send production email
directly.

The approved-send worker is installed but guarded. It sends only rows whose
`campaign_status` is `approved_to_send` or `follow_up_approved`, only when
`VESRA_AUTO_SEND_ENABLED=true`, and only after the SMTP sender re-runs the
normal safety gates. With `VESRA_AUTO_SEND_ENABLED=false`, the timer is a
clean no-op.

Agent tools are registered in:

```text
lead-gen/config/agent_tools.json
```

The executor may only run registered tools and allowed arguments. Tool run logs
are stored under `/var/lib/vesra/orchestration-runs/tool-runs`.

Sentry is optional and controlled by `SENTRY_DSN`. Keep the DSN in
`/etc/vesra/outbound.env`, never in Git. The Sentry setup deliberately uses
`send_default_pii=false` and redacts common email/body fields before sending
events.

Optional runtime limits in `/etc/vesra/outbound.env`:

```text
VESRA_DAILY_DISCOVERY_HR_LIMIT=10
VESRA_DAILY_DISCOVERY_FRANCHISE_LIMIT=10
VESRA_DAILY_DISCOVERY_MAX_PAGES=2
VESRA_DAILY_ENRICH_LIMIT=50
VESRA_DAILY_ENRICH_MAX_PAGES=2
VESRA_AGENTIC_MAX_CONTACTS=500
VESRA_AGENTIC_MAX_TOOL_RUNS=3
```

Useful checks:

```bash
systemctl list-timers --all 'vesra-daily-*' --no-pager
systemctl status vesra-daily-discovery.service --no-pager -l
systemctl status vesra-daily-enrichment.service --no-pager -l
systemctl status vesra-daily-orchestrator.service --no-pager -l
systemctl status vesra-agent-send-approved.service --no-pager -l
journalctl -u vesra-daily-discovery.service -n 80 --no-pager
journalctl -u vesra-daily-enrichment.service -n 80 --no-pager
journalctl -u vesra-daily-orchestrator.service -n 80 --no-pager
journalctl -u vesra-agent-send-approved.service -n 80 --no-pager
tail -n 80 /var/log/vesra/daily-discovery.log
tail -n 80 /var/log/vesra/daily-enrichment.log
tail -n 80 /var/log/vesra/daily-orchestrator.log
tail -n 80 /var/log/vesra/agent-send-approved.log
```

### Production Safety Rules

- Never send production prospect emails without explicit user approval.
- Test campaigns must use user-controlled inboxes only.
- Keep the live campaign queue empty unless a real send has been approved.
- Unsubscribe handling must be automatic and must suppress future sends.
- Do not automate LinkedIn login, connection requests, or messaging.
- Preserve runtime CSV state on the droplet; Git deploys should update code only.
