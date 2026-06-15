# Vesra Partner Outreach Monitor

## Purpose

Monitor replies and unsubscribe requests for Vesra partner outreach, update local tracking files, and stop follow-ups automatically. Do not send replies automatically.

## Files

- `lead-gen/data/prospects.csv`: master prospect list.
- `lead-gen/data/campaign_queue.csv`: outbound queue and campaign state.
- `lead-gen/data/suppression.csv`: opt-outs, not-fit contacts, and blocked domains.
- `lead-gen/docs/outreach_templates.md`: first-touch and follow-up templates.

## Automated Capture

Reply and unsubscribe handling is automated through the local webhook server:

```bash
export VESRA_UNSUBSCRIBE_SECRET="generate-a-long-random-secret"
export VESRA_MAILGUN_WEBHOOK_TOKEN="generate-another-random-secret"
python lead-gen/scripts/outreach/unsubscribe_server.py --host 127.0.0.1 --port 8088
```

Public endpoints expected by Mailgun and outbound emails:

- `GET /unsubscribe?token=...` verifies a signed token, adds the recipient to suppression, and stops follow-ups.
- `POST /unsubscribe?token=...` handles mail-client one-click unsubscribe requests from the `List-Unsubscribe-Post` header.
- `POST /mailgun/inbound?token=...` receives Mailgun inbound route posts, classifies replies, updates campaign state, and suppresses unsubscribe/not-interested replies.

For production this server must be reachable at the configured public URLs:

```text
https://getvesra.co.uk/unsubscribe
https://getvesra.co.uk/mailgun/inbound?token=...
```

Mailgun EU route should forward `.*@getvesra.co.uk` to the webhook URL. If Chris also wants every raw reply in Gmail, add `forward("chris@vesra.io")` as a second action before `stop()`.

## Gmail Search Scope Fallback

If webhook capture is unavailable, search for likely replies using:

- `to:chris@getvesra.co.uk newer_than:30d ("Vesra" OR "partner programme" OR "partner program") -from:chris@getvesra.co.uk`
- replies from any email address present in `lead-gen/data/campaign_queue.csv`

## Reply Classification

- `positive`: asks for more detail, wants a call, asks how it works, asks for pricing/partner terms.
- `not_interested`: says no, not relevant, remove, unsubscribe, no thanks.
- `referral`: suggests another person or asks to contact a colleague.
- `question`: asks a substantive question before deciding.
- `out_of_office`: automatic absence reply.
- `unclear`: response needs manual judgement.

## Required Actions

For every new reply, `lead-gen/scripts/outreach/suppression.py` should:

1. Update `lead-gen/data/campaign_queue.csv`:
   - `last_reply_at`
   - `reply_status`
   - `campaign_status`
   - `next_action`
2. Update `lead-gen/data/prospects.csv`:
   - set `status` to `replied`, `not_fit`, or `do_not_contact` where appropriate
   - preserve existing research fields
3. If the reply opts out or says no:
   - append the email/company to `lead-gen/data/suppression.csv`
4. If a response is useful:
   - create a Gmail draft reply in-thread for Chris to review
   - do not send it automatically

## Draft Response Rules

- Keep replies short and direct.
- Match the respondent's tone.
- If positive, suggest a 15-minute call and ask for two suitable times.
- If they ask what Vesra does, explain briefly and ask whether a partner model would be useful to explore.
- If they ask for terms, say Chris can share the proposed partner structure on a short call.
- If not interested, acknowledge and confirm no further follow-up.
