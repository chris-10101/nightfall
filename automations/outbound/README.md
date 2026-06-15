# Nightfall Outbound

Reusable outbound automation infrastructure.

This folder is the canonical structure for outbound systems. Existing Vesra
production jobs still run through `automations/vesra-outbound` for compatibility,
but new businesses and ICPs should be added here.

## Layout

```text
automations/outbound/
  core/                  # Shared design notes and future shared library code
  tools/                 # Global tool registry and tenant tool runner
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

The tenant can initially point at a compatibility automation path, then later
move to fully shared tools.

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

For Vesra, this delegates to the existing stable automation under
`automations/vesra-outbound`. New tenants can use the same interface.

## Deployment

The GitHub Actions workflow deploys the whole repository to `/opt/nightfall`.
Changes under this folder are included in the deploy trigger.

Generic systemd units live in `systemd/`, but Vesra production still uses the
existing `vesra-*` units until a separate cutover.
