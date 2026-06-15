# Vesra Campaign Sending Conditions

This document defines the bounded outbound eligibility rules implemented in
`lead-gen/scripts/core/eligibility_rules.py`. The module is intended to be reused by
queue building, batch preparation, and send-time guards, but it does not perform
file I/O and does not modify the CSV workflow by itself.

## Eligibility Contract

Every outbound prospect row should be evaluated before it is selected for email.
Callers pass a row dictionary and optional in-memory context such as suppression
keys, duplicate keys, the current time, and sequence limits. The result is a
dictionary with:

- `eligible`: boolean send eligibility.
- `reasons`: structured reason dictionaries with `code`, `severity`, and
  `message`.
- `dedupe_keys`: normalized keys for email, domain, company, and company/domain.

A row is ineligible if any returned reason has `severity=block`.

## Required Prospect Fit

Eligible rows must:

- Have a syntactically valid `email`.
- Be in an active ICP segment from `lead-gen/config/icp_profiles.json`.
- Have the required evidence signal for that ICP profile.
- Avoid profile-specific exclusion terms from that ICP profile.
- Not look like a recruitment, staffing, talent acquisition, or executive search
  business.
- Not carry blocked statuses such as `not_fit`, `do_not_contact`, `suppressed`,
  `unsubscribed`, or `opted_out` in known status fields.
- Have public evidence through `email_source_url`, `website_url`, `source_url`,
  LinkedIn source fields, or another configured evidence URL.

## Email Quality Rules

The rules block:

- Placeholder or no-reply style addresses such as `noreply@`, `test@`, or
  `example.com` domains.
- Guessed or pattern-inferred emails where row fields contain markers such as
  `guessed`, `inferred`, `pattern`, `permutation`, or `predicted`.
- Free personal email domains such as Gmail, Outlook, Hotmail, iCloud, Yahoo, or
  Protonmail unless `email_source_url` is a public URL and the row has business
  contact evidence through company or decision-maker fields.

Generic business inboxes are not blocked solely because they are generic. They
still need public source evidence and must not be placeholders.

## Suppression And Stop Conditions

The module checks both row-level flags and caller-supplied suppression keys.
Suppression keys can include normalized email, email domain, company key, or
company/domain key.

Outbound must stop when a row has:

- `last_reply_at`.
- Reply or campaign status values indicating a reply, opt-out, not interested,
  do-not-contact, or out-of-office state.
- Bounce fields such as `bounced_at`, `bounce_status`, `delivery_status`, or
  `smtp_status`.

## Duplicate Helpers

`dedupe_keys(row)` returns normalized helper keys:

- `email`: lower-cased email address.
- `domain`: email domain.
- `company`: normalized company name with common suffixes removed.
- `company_domain`: normalized company plus website or email domain.

Callers can pass `seen_email_keys`, `seen_company_domain_keys`, and
`seen_company_keys` into `evaluate_prospect`. Duplicate email and
company/domain matches are blocking. Duplicate company names are warnings by
default so a reviewer can decide whether multi-location records are legitimate.

## Timing And Sequence Rules

The module includes reusable helpers for timing gates:

- `is_uk_working_hours(...)` and `check_uk_working_hours(...)` enforce a
  weekday UK send window, defaulting to 09:00 to 17:00 Europe/London.
- `follow_up_spacing_ok(...)` and `check_follow_up_spacing(...)` enforce a
  minimum gap after `last_outbound_at`, `contacted_at`, or `sent_at`, defaulting
  to three days. If `follow_up_at` is present, that timestamp is the due date.
- `within_sequence_cap(...)` and `check_sequence_cap(...)` cap sequence sends,
  defaulting to a maximum of three outbound steps.

Send-time integrations should call `evaluate_prospect(...,
require_send_window=True)` or separately call `check_uk_working_hours` immediately
before sending. Queue and draft preparation can omit the current send-window
check if they are preparing future work.

## Implementation Expectations

- Keep the rules pure and stdlib-only.
- Do not add CSV, network, SMTP, or Gmail logic to the rules module.
- Treat the returned reason codes as audit data. Preserve them when rejecting
  rows in future queue or send integrations.
- Prefer adding new rule functions instead of embedding campaign compliance
  logic directly inside queue builders or send scripts.
- Keep sender-side volume, authentication, and manual review controls documented
  in `lead-gen/docs/daily_outbound_pipeline.md`; this document covers row-level
  eligibility and timing gates.
