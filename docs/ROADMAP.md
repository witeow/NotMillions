# Roadmap

The build order for NotMillions. **This file is the hand-off between working sessions** — any session (local, web, or phone) should read it first to know where the project stands, and update the Status block when a phase advances.

## Status

- **Last updated:** 2026-07-03
- **Done:** Phase 1 — full sales-side schema, verified migration, seed, smoke test (see below)
- **Next up:** Phase 2 — posting service, then FastAPI routes
- **Environment quick-start:** `docker compose up -d` (repo root), then from `backend/`: `uv sync`, `uv run alembic upgrade head`, `uv run python -m app.seed`. Sanity check: `uv run python scripts/smoke_test.py` and `uv run alembic check`.

## Phase 1 — Data foundation ✅ (2026-07-03)

SQLAlchemy 2.0 models for 16 tables (documents, allocations, double-entry ledger, sequences), Alembic initial migration, idempotent seed (SG chart of accounts, GST tax codes SR/ZR/ES, document sequences, company row), end-to-end smoke test posting a balanced journal entry. Design rationale: `docs/decisions/` (11 ADRs).

## Phase 2 — Posting service + API (next)

The business-logic layer, then HTTP on top:

1. **Posting service** — the single choke point that writes journal rows:
   - Invoice posting (DR AR / CR income per line / CR GST output), payment posting (DR bank / CR AR), credit-note posting (DR income + GST / CR AR)
   - Debits = credits asserted on every entry; document numbers via the row-locked sequence helper, inside the saving transaction
   - Status transitions (DRAFT→POSTED→PARTIALLY_PAID→PAID; VOID posts a reversing entry, never deletes)
   - Allocation rules: sum of a payment's allocations ≤ payment amount; allocations only against POSTED invoices of the same customer
   - Tests for every rule above (first real test suite; pytest)
2. **FastAPI routes** — CRUD for customers/items/tax codes, document endpoints (create draft, edit draft, post, void, allocate), wired through the service layer only. Swagger UI (`/docs`) serves as the interim UI for demoing.

## Phase 3 — Reports

All queries over the ledger + allocations (no new write paths): AR aging, customer statements, trial balance, P&L, balance sheet. GST summary (output tax by period) to help with F5 filing.

## Phase 4 — Frontend (learning track)

React + TypeScript, built deliberately as a learning exercise (explain concepts as they come up). Screens in value order: invoice entry, customer list + statement view, payment entry with allocation, dashboards last.

## Phase 5 — Deployment

Docker Compose bundle for TrueNAS: backend container + Postgres + volume, `.env`-driven secrets, backup/restore procedure for the database. The "one-time install" promise made real.

## Deferred (per ADR 0001)

Purchases/AP, inventory, bank reconciliation, payroll, multi-currency, LHDN e-invoicing. Revisit only after Phases 2–5 hold up in real use.
