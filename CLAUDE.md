# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NotMillions is a self-hosted SME accounting app inspired by "Millions" (SG/MY on-prem accounting software). Current scope covers **both sales (AR) and purchases (AP)**: customers, suppliers, quotation→invoice, bills, payments received/made, credit notes, debit notes, GL auto-posting. Inventory, bank reconciliation, payroll, multi-currency, and LHDN e-invoicing are deliberately deferred.

Deployment target is a home-lab Docker Compose stack (TrueNAS), single company, Singapore GST. Keep architecture solo-dev simple — no cloud-native patterns.

Decision rationale lives in `docs/decisions/` (ADRs) — read the relevant record before changing core design; supersede with a new ADR rather than editing old ones.

## Starting a session

The repo is the only shared memory between sessions (local machine, web, phone). Before doing anything:

1. Read `docs/ROADMAP.md` — the Status block says what's done and what's next; recent `git log --oneline -15` fills in the details.
2. Check `docs/decisions/` for any design area you're about to touch.
3. When a phase or significant chunk of work completes, update the Status block in `docs/ROADMAP.md` in the same commit series — the next session depends on it.

Workflow expectations (the user has confirmed these): plan mode for non-trivial work, run `/code-review medium` over new code before committing, fix findings first, split work into logical commits.

## Commands

Backend uses **uv** (not pip/venv directly). All backend commands run from `backend/`:

```
docker compose up -d              # from repo root: dev Postgres 16 on host port 5432
uv sync --all-extras              # install deps + test extras into .venv
uv run alembic upgrade head       # apply migrations
uv run alembic revision --autogenerate -m "..."   # new migration (review before applying)
uv run python -m app.seed         # idempotent: chart of accounts, tax codes, sequences, company row
uv run pytest                     # run test suite (45 tests)
uv run python scripts/smoke_test.py   # end-to-end AR + AP smoke test
```

The dev container maps to the standard port **5432**. `DATABASE_URL` (env or `backend/.env`, see `.env.example`) uses 5432. If your machine already runs a local PostgreSQL on 5432, change the host mapping in `docker-compose.yml` and `DATABASE_URL` accordingly.

## Architecture

Double-entry accounting core with both AR and AP. The invariants that matter:

- **Every posted business document produces a balanced `JournalEntry`** (`journal_entries` + `journal_lines`). Posting rules:
  - Invoice: DR Accounts Receivable (1200) / CR income per line / CR GST Output Tax (2100)
  - Payment received: DR bank/cash / CR AR
  - Credit note: DR income + DR GST Output / CR AR
  - Bill: DR expense per line / DR GST Input Tax (1300) / CR Accounts Payable (2000)
  - Payment made: DR AP / CR bank/cash
  - Debit note: DR AP / CR expense + CR GST Input
- **Journal entries are never deleted or edited** — voiding a document creates a reversing entry.
- **Balances are computed, never stored.** Outstanding amounts are derived from allocations; there is no `amount_paid` column (prevents drift).
- **Debits = credits is enforced in the service layer**, not the DB. The DB only guarantees each journal line is single-sided and non-negative (check constraints).
- **Document numbers** (INV-0001 etc.) come from `next_document_number()` in `app/models/sequence.py`, which row-locks `document_sequences` (`SELECT … FOR UPDATE`) — always call it inside the same transaction that saves the document.
- **System accounts** (`accounts.is_system`, e.g. AR, AP, GST accounts) are posting targets the app depends on; they must not be deletable/re-typeable from any future UI.

### Service layer

Business logic lives in `app/services/`, one module per document type plus `shared.py` for common helpers. All posting, status transitions, and allocations go through these services — routes should never create journal entries directly.

- `shared.py`: `compute_line_total()`, `assert_balanced()`, `create_journal_entry()`, `create_reversing_entry()`, custom exceptions (`PostingError`, `InvalidStateTransition`, `AllocationError`, `BalanceError`)
- AR: `invoice_service.py`, `payment_service.py`, `credit_note_service.py`
- AP: `bill_service.py`, `payment_made_service.py`, `debit_note_service.py`

### Tax codes

Output tax (sales): SR (9%), ZR, ES — post to GST Output Tax (2100).
Input tax (purchases): TX (9%), BL, NR — post to GST Input Tax (1300).
Follows IRAS convention for GST F5 reporting.

### Conventions

- SQLAlchemy 2.0 style (`Mapped[]`/`mapped_column`). Money columns use the shared constants in `app/models/base.py`: `MONEY` Numeric(12,2), `UNIT_PRICE` Numeric(12,4), `QUANTITY` Numeric(12,3). Line math rounds half-up to cents per line.
- Enums are Python `(str, enum.Enum)` classes stored as strings (`sa.Enum(..., native_enum=False)`) — never Postgres native enums (migration pain).
- Constraint names come from the naming convention on `Base.metadata` (`app/core/db.py`) — don't name constraints ad hoc.
- **Every new model must be imported in `app/models/__init__.py`**, otherwise Alembic autogenerate silently misses its table.
- Tax codes live in the `tax_codes` table — GST rate changes are data edits, never hardcoded in logic.
