# Nightfall Outbound

Reusable outbound automation infrastructure.

This folder is the canonical structure for outbound systems. It owns the shared
runtime code, deployment units, tenant configuration, campaign definitions, and
Vesra production automation.

## Layout

```text
automations/outbound/
  core/                  # Shared design notes and future shared library code
  lead-gen/              # Current outbound runtime engine and tests
  tools/                 # Global tool registry and tenant tool runner
  deploy/systemd/        # Live Vesra service/timer units
  systemd/               # Generic tenant systemd template units
  tenants/
    vesra/
      tenant.json
      config/
      kb/
      campaigns/
        hr_consultancy_partner/
        franchise/
```

## Adding a New Business

Create:

```text
automations/outbound/tenants/<tenant_id>/
  tenant.json
  config/
  kb/
  campaigns/
```

Each campaign should contain:

```text
icp.json
discovery.json
sequence.json
safety.json
```

Tenant tools should run from `automations/outbound` unless a tenant has a
specific working directory.

## Adding a New ICP for Vesra

Create:

```text
automations/outbound/tenants/vesra/campaigns/<campaign_id>/
```

Then add the campaign id to `tenants/vesra/tenant.json`.

## Tool Runner

Use:

```bash
python3 automations/outbound/tools/run_tenant_tool.py --tenant vesra orchestrate --rebuild-queue --summary
```

For Vesra, this delegates to the stable runtime under
`automations/outbound/lead-gen`. New tenants can use the same interface.

## Agentic Orchestration

Vesra's daily orchestrator uses:

```bash
python3 lead-gen/scripts/orchestration/run_agentic_orchestrator.py --rebuild-queue --execute-safe-tools --summary
```

It refreshes lifecycle state, chooses a registered tool per contact, records the
reasoning trail, and executes only capped non-email/non-review tools. Email
sending remains behind the approved-send worker and `VESRA_AUTO_SEND_ENABLED`.

## Deployment

The GitHub Actions workflow deploys the whole repository to `/opt/nightfall`.
Changes under this folder are included in the deploy trigger.

Vesra production units live in `deploy/systemd/`. Generic tenant templates live
in `systemd/` for later multi-tenant service rollout.
