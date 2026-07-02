# 0004. Single-company schema

Date: 2026-07-03
Status: Accepted

## Context

The original Millions supports multiple companies. Supporting that here would put a `company_id` foreign key on every table and a filter on every query, forever, for a deployment that serves one business.

## Decision

One company per installation. Company details live in a single-row `company_settings` table, enforced by `CHECK (id = 1)` (plus a valid financial-year month check). No `company_id` anywhere. A second company is a second Docker Compose stack with its own database — consistent with the self-hosted model (ADR 0002).

## Consequences

- Every query, model, and report stays simpler; no tenant-leak class of bug.
- The seed script and any future settings UI address the row as `id = 1`.
- If true multi-company inside one database is ever demanded, it's a large migration — accepted risk, judged unlikely for this deployment model.
