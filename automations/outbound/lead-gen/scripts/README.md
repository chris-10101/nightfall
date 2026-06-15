# Lead Gen Scripts

Scripts are grouped by workflow stage.

- `core/` - shared CSV, ICP, and eligibility logic.
- `discovery/` - ICP-aware prospect discovery.
- `enrichment/` - website, decision-maker, Companies House, and cleanup enrichment.
- `imports/` - one-off/import source loaders.
- `outreach/` - queue building, batch preparation, sending, suppression, unsubscribe, and test campaigns.
- `maintenance/` - validators and manual filtering tools.
- `legacy/` - old one-off seed scripts kept for reference, not daily automation.

Daily automation should use:

```bash
python lead-gen/scripts/discovery/discover_email_backed_icp.py --max-new 20 --checkpoint
python lead-gen/scripts/enrichment/enrich_public_web.py --limit 25 --max-pages 2 --only-missing-email
python lead-gen/scripts/outreach/build_campaign_queue.py
python lead-gen/scripts/outreach/prepare_outreach_batch.py --limit 10
```
