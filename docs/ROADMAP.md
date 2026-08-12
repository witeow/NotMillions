# Roadmap

The build order for NotMillions. **This file is the hand-off between working sessions** — any session (local, web, or phone) should read it first to know where the project stands, and update the Status block when a phase advances.

## Status

- **Last updated:** 2026-08-12
- **Done:** Phase 1, Phase 2a (posting services + tests for both AR and AP — 45 tests passing)
- **Next up:** Phase 2b — FastAPI routes (CRUD + document lifecycle endpoints, Swagger UI as interim UI)
- **Environment quick-start:** `docker compose up -d` (repo root), then from `backend/`: `uv sync --all-extras`, `uv run alembic upgrade head`, `uv run python -m app.seed`. Sanity check: `uv run pytest` and `uv run python scripts/smoke_test.py`.

## Phase 1 — Data foundation ✅ (2026-07-03)

SQLAlchemy 2.0 models for 16 tables (documents, allocations, double-entry ledger, sequences), Alembic initial migration, idempotent seed (SG chart of accounts, GST tax codes SR/ZR/ES, document sequences, company row), end-to-end smoke test posting a balanced journal entry. Design rationale: `docs/decisions/` (11 ADRs).

## Phase 2a — Posting services + tests ✅ (2026-08-12)

Scope expanded from sales-only to both AR and AP (ADR 0013). Includes:

- **AP models**: Supplier, Bill/BillLine, PaymentMade/PaymentMadeAllocation, DebitNote/DebitNoteLine/DebitNoteAllocation (8 new tables). Item gained `expense_account_id`.
- **Expanded seed**: AP account (2000), GST Input Tax (1300), expense accounts (5000–6300 for construction: materials, subcontractor, equipment, wages, CPF, levy, office), input tax codes (TX/BL/NR per IRAS), AP document sequences.
- **Service layer** (`app/services/`): shared helpers (balanced JE creation, reversals, line totals), then per-document services for invoice, payment, credit note (AR) and bill, payment made, debit note (AP). All posting rules, status transitions, and allocation validations.
- **45 pytest tests** covering every posting rule, allocation constraint, status transition, and void/reversal path.

## Phase 2b — FastAPI routes (next)

CRUD for customers/suppliers/items/tax codes/accounts, document endpoints (create draft, edit draft, post, void, allocate) for all 6 document types, wired through the service layer only. Swagger UI (`/docs`) serves as the interim UI.

## Phase 3 — Reports

All queries over the ledger + allocations (no new write paths): AR aging, AP aging, customer/supplier statements, trial balance, P&L (with gross profit from 5000s vs 6000s split), balance sheet. GST F5 summary (output tax SR/ZR/ES vs input tax TX/BL/NR by period).

## Phase 4 — Frontend (learning track)

React + TypeScript, built deliberately as a learning exercise (explain concepts as they come up). Screens in value order: invoice entry, bill entry, customer/supplier lists, payment entry with allocation, dashboards last.

## Phase 5 — Deployment

Docker Compose bundle for TrueNAS: backend container + Postgres + volume, `.env`-driven secrets, backup/restore procedure for the database. The "one-time install" promise made real.

## Deferred

Inventory, bank reconciliation, payroll, multi-currency, LHDN e-invoicing. Revisit only after Phases 2–5 hold up in real use.
