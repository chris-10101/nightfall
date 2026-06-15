# Daily Vesra Outbound Pipeline

## Active Campaign ICPs

Active ICPs are configured in `lead-gen/config/icp_profiles.json`.

Currently active:

- HR consultancy partners.
- Franchise/franchisor partners.

Each ICP has its own active segments, required signals, exclusion terms, campaign
name, and outreach copy. Do not add rows to the queue just because they have an
email; they must pass the relevant ICP profile and the shared eligibility rules.

## Recommended Sender Setup

Use `chris@vesra.io` as the visible sender only after it is fully authenticated:

- SPF includes the sending provider.
- DKIM is enabled for `vesra.io`.
- DMARC exists and is not overly strict until sending is proven.
- The alias is verified in the Google account if using Gmail/Google SMTP.

Best option for your current setup:

1. Keep `chris@vesra.io` as a verified "send mail as" alias in the Google account.
2. Use Google SMTP with the Maple/Google account credentials and `From: Chris Smith <chris@vesra.io>`.
3. Keep reply-to as `chris@vesra.io`.
4. Use low daily volume until deliverability is proven.

The Gmail connector is still useful for reply monitoring and draft replies, but the current connector tool does not expose a sender alias field. If the email must come from `chris@vesra.io`, SMTP or a dedicated Gmail API sender is safer.

## Daily Jobs

### 1. Discover

Adds new partner-fit prospects for each active ICP profile. The default daily
automation target is 20 new email-backed contacts total across all active ICPs:

```bash
python lead-gen/scripts/discovery/discover_email_backed_icp.py --max-new 20 --checkpoint
```

Run one ICP at a time when testing a new market or when you want a fixed daily
allocation per ICP:

```bash
python lead-gen/scripts/discovery/discover_email_backed_icp.py --profile hr_consultancy_partner --max-new 10 --checkpoint
python lead-gen/scripts/discovery/discover_email_backed_icp.py --profile franchise --max-new 10 --checkpoint
```

This script only adds rows when it finds a public email and the row passes the
profile's required signals and exclusion checks. Legacy discovery scripts are
kept for manual research, but they can create non-contactable rows and should
not be the default daily automation.

Geography is configured per ICP as separate `cities`, `regions`, and
`countries` in `lead-gen/config/icp_profiles.json`. `city_region` stores the
specific geography value used, and notes record whether it came from a city,
region, or country search.

### 2. Enrich

Runs deterministic enrichments:

```bash
python lead-gen/scripts/enrichment/enrich_decision_makers.py
python lead-gen/scripts/enrichment/enrich_public_web.py --limit 25 --max-pages 2 --only-missing-email
```

Paid enrichment such as Hunter should only run after a row has passed its ICP
profile and still lacks a public email.

### 3. Build Queue

```bash
python lead-gen/scripts/outreach/build_campaign_queue.py
```

This applies the campaign eligibility rules from `lead-gen/scripts/core/eligibility_rules.py`.
Rows are blocked before queueing if they are suppressed, outside the active ICP
profiles, duplicated by email/company/domain, missing source evidence, missing
profile evidence, matching profile exclusions, guessed/placeholder emails,
replied, bounced, or over sequence limits.

### 4. Prepare Daily Batch

```bash
python lead-gen/scripts/outreach/prepare_outreach_batch.py --limit 10
```

The batch step rechecks eligibility, suppression, duplicate emails, and the
per-domain batch limit before writing a review CSV.

### 5. Review

Review the generated batch under:

```text
lead-gen/outreach/batches/
```

### 6. Send

Dry-run first:

```bash
python lead-gen/scripts/outreach/send_outreach_smtp.py lead-gen/outreach/batches/batch_YYYY-MM-DD.csv
```

Actual send requires:

```bash
export VESRA_SMTP_USERNAME="your-google-login"
export VESRA_SMTP_APP_PASSWORD="your-google-app-password"
```

Then set `review_required_before_send` to `false` in `lead-gen/config/outbound_config.json` and run:

```bash
python lead-gen/scripts/outreach/send_outreach_smtp.py lead-gen/outreach/batches/batch_YYYY-MM-DD.csv --send
```

The send script performs the final hard gate before SMTP. It blocks unsafe or
stale batch rows, enforces `daily_send_limit`, `per_domain_daily_limit`, UK
weekday send windows, reply/bounce stops, source evidence, and suppression.
It also adds an unsubscribe reply instruction, a visible unsubscribe link, and
`List-Unsubscribe` headers to each message.

When `VESRA_UNSUBSCRIBE_SECRET` is set, the sender also adds a signed one-click
unsubscribe URL from `unsubscribe_base_url`. The unsubscribe endpoint accepts
both browser `GET` requests and mail-client one-click `POST` requests, writes to
`suppression.csv`, and stops follow-ups automatically.

### 7. Monitor Replies

Preferred: Mailgun EU inbound route posts replies to:

```text
https://getvesra.co.uk/mailgun/inbound?token=...
```

The local webhook server is:

```bash
export VESRA_UNSUBSCRIBE_SECRET="generate-a-long-random-secret"
export VESRA_MAILGUN_WEBHOOK_TOKEN="generate-another-random-secret"
python lead-gen/scripts/outreach/unsubscribe_server.py --host 127.0.0.1 --port 8088
```

Fallback: Gmail connector or IMAP monitor can be added if we decide to use mailbox polling instead.

## Safety Rules

- Do not send more than 10-20/day until deliverability is proven.
- Start with reviewed drafts only; no automatic sending.
- Do not send to rows with mismatched decision-maker name and named email.
- Do not email suppressed contacts.
- Do not send more than once to the same email, company, or company domain in a campaign.
- Send only during the configured UK weekday window, default `09:30-16:00`.
- Do not send guessed, placeholder, or unsourced emails.
- Stop follow-ups immediately on any reply, unsubscribe, not-interested response, or bounce.
- Do not run follow-up sends unless Mailgun inbound monitoring or an equivalent reply monitor is active.
- Keep a public source URL/evidence URL for every queued email.
- Create draft replies from the KB, but require review before send.
- Keep LinkedIn actions manual.
