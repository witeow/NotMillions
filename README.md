# NotMillions

A simple, self-hosted accounting app for small businesses, inspired by [Millions](https://www.millions.sg/) and similar Singapore/Malaysia on-premise accounting software (AutoCount, SQL Account, UBS). One-time install on your own hardware, no subscription.

> Side project status: early days. The database foundation works; the API and UI are still to come.

## Scope (sales-side MVP)

- Customers and a simple item/service catalog (no stock tracking)
- Quotations → invoices, payments received, credit notes
- Automatic double-entry posting to a general ledger
- Singapore GST (standard-rated 9%, zero-rated, exempt) via configurable tax codes
- Planned reports: AR aging, customer statements, P&L, balance sheet

Deliberately out of scope for now: purchases/AP, inventory, bank reconciliation, payroll, multi-currency, LHDN e-invoicing.

## Stack

- **Backend:** Python / SQLAlchemy 2.0 / Alembic / PostgreSQL 16 (FastAPI planned)
- **Frontend:** React + TypeScript (planned)
- **Deployment:** Docker Compose, aimed at home-lab servers (e.g. TrueNAS)

## Getting started (development)

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Python 3.10+.

```bash
# 1. Start the dev database (host port 5433, to avoid clashing with a local Postgres)
docker compose up -d

# 2. Install backend dependencies
cd backend
uv sync

# 3. Create the schema and seed base data (chart of accounts, GST tax codes, sequences)
uv run alembic upgrade head
uv run python -m app.seed

# 4. Optional: end-to-end smoke test — creates a sample invoice and a balanced journal entry
uv run python scripts/smoke_test.py
```

Configuration is via environment variables or `backend/.env` — see [backend/.env.example](backend/.env.example).

## Repository layout

```
docker-compose.yml     dev PostgreSQL
docs/decisions/        architecture decision records (the "why" behind the design)
backend/
  app/core/            settings, engine/session, declarative base
  app/models/          SQLAlchemy models (documents, GL, sequences)
  app/seed.py          idempotent seed data
  alembic/             migrations
  scripts/             smoke test
```

## Accounting design in one paragraph

Every posted document (invoice, payment, credit note) writes a balanced journal entry against a small seeded chart of accounts; entries are never edited or deleted — corrections post reversing entries. Amounts owed are always computed from payment/credit-note allocations rather than stored, so the books can't drift. Document numbers (INV-0001, …) are issued from a row-locked sequence table.
