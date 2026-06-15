# Outbound Core

Shared outbound engine code belongs here.

The current first migration keeps Vesra production running from
`automations/vesra-outbound` and introduces `automations/outbound` as the
canonical tenant/campaign structure. The next extraction step is to move shared
Python modules here and leave compatibility wrappers under `vesra-outbound`.

Core responsibilities:

- CSV state helpers
- tenant-aware path resolution
- eligibility rules
- suppression and unsubscribe handling
- Sentry/monitoring setup
- email formatting
- lifecycle orchestration primitives
- tool execution contracts
- KB retrieval primitives

Business-specific ICPs, sequences, discovery queries, and KB content should
live under `automations/outbound/tenants/<tenant_id>/`.
