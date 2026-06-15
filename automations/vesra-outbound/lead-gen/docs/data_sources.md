# Vesra Lead Data Sources

## Active Source Mix

The active prospect CSV contains HR consultancy prospects from several public-source channels.

Current source types:

- Original curated HR consultancy spreadsheet.
- Curated public search results.
- Public HR consultancy network sitemaps.
- Bing RSS public search results.
- Companies House public company search.

## Source Quality Notes

### Outreach-Ready Rows

Rows with public business emails can enter the outbound queue after suppression checks and review.

These rows usually have:

- Website URL.
- Email address.
- Email source URL where available.
- Decision maker or company LinkedIn where available.
- `status` of `ready_to_review` or `enriched`.

### Research-Needed Rows

Companies House rows are real UK company records, but they do not include websites, decision makers, emails, client model, or software-platform evidence.

These rows are intentionally marked:

- `status`: `research_needed`
- `priority`: `low`
- `fit_score`: `45`

Do not send outreach to these rows until enrichment confirms:

- Active HR consultancy / outsourced HR fit.
- Website.
- Decision maker or suitable business contact.
- Public business email.
- No obvious own HR software platform.

## Expansion Scripts

Public web discovery:

```bash
python lead-gen/scripts/discovery/discover_hr_consultancies.py --target-total 500
```

Network location import:

```bash
python lead-gen/scripts/imports/import_network_locations.py
```

Companies House research import:

```bash
python lead-gen/scripts/imports/import_companies_house_hr.py --target-total 500
```

After imports, rebuild the generated queue:

```bash
python lead-gen/scripts/outreach/build_campaign_queue.py
```
