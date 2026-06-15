# Outbound Core

Shared outbound engine code belongs here.

The current stable runtime lives under `automations/outbound/lead-gen` so the
production jobs are self-contained in the canonical outbound tree. Future
changes should move reusable Python modules here while keeping command wrappers
stable for existing services and agent tools.

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
