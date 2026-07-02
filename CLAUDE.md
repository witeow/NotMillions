# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NotMillions is a self-hosted SME accounting app inspired by "Millions" (SG/MY on-prem accounting software). Current scope is the **sales side only**: customers, quotation→invoice, payments received, credit notes, GL auto-posting, AR reporting. Purchases/AP, inventory, banking reconciliation, payroll, multi-currency, and LHDN e-invoicing are deliberately deferred.

Deployment target is a home-lab Docker Compose stack (TrueNAS), single company, Singapore GST. Keep architecture solo-dev simple — no cloud-native patterns.

Decision rationale lives in `docs/decisions/` (ADRs) — read the relevant record before changing core design; supersede with a new ADR rather than editing old ones.

## Starting a session

The repo is the only shared memory between sessions (local machine, web, phone). Before doing anything:

1. Read `docs/ROADMAP.md` — the Status block says what's done and what's next; recent `git log --oneline -15` fills in the details.
2. Check `docs/decisions/` for any design area you're about to touch.
3. When a phase or significant chunk of work completes, update the Status block in `docs/ROADMAP.md` in the same commit series — the next session depends on it.

Workflow expectations (the user has confirmed these): plan mode for non-trivial work, run the `code-reviewer` agent over new code before committing, fix findings first, split work into logical commits.

## Commands

Backend uses **uv** (not pip/venv directly). All backend commands run from `backend/`:

```
docker compose up -d              # from repo root: dev Postgres 16 on host port 5433
uv sync                           # install deps + editable app package into .venv
uv run alembic upgrade head       # apply migrations
uv run alembic revision --autogenerate -m "..."   # new migration (review before applying)
uv run python -m app.seed         # idempotent: chart of accounts, tax codes, sequences, company row
uv run python scripts/smoke_test.py   # end-to-end schema check (invoice + balanced JE)
```

Port gotcha: this machine runs a local PostgreSQL on 5432, so the dev container maps to **5433**. `DATABASE_URL` (env or `backend/.env`, see `.env.example`) must use 5433.

There is no test suite, linter, or FastAPI app yet (routes are the next phase).

## Architecture

Double-entry accounting core. The invariants that matter:

- **Every posted business document produces a balanced `JournalEntry`** (`journal_entries` + `journal_lines`). Posting rules:
  - Invoice: DR Accounts Receivable (1200) total / CR income account per line / CR GST Output Tax (2100)
  - Payment: DR bank/cash account / CR AR
  - Credit note: DR income + DR GST / CR AR
- **Journal entries are never deleted or edited** — voiding a document creates a reversing entry.
- **Balances are computed, never stored.** An invoice's paid/outstanding amount is derived from `payment_allocations` + `credit_note_allocations`; there is no `amount_paid` column by design (prevents drift).
- **Debits = credits is enforced in the service layer**, not the DB. The DB only guarantees each journal line is single-sided and non-negative (check constraints).
- **Document numbers** (INV-0001 etc.) come from `next_document_number()` in `app/models/sequence.py`, which row-locks `document_sequences` (`SELECT … FOR UPDATE`) — always call it inside the same transaction that saves the document.
- **System accounts** (`accounts.is_system`, e.g. AR control, GST output) are posting targets the app depends on; they must not be deletable/re-typeable from any future UI.

### Conventions

- SQLAlchemy 2.0 style (`Mapped[]`/`mapped_column`). Money columns use the shared constants in `app/models/base.py`: `MONEY` Numeric(12,2), `UNIT_PRICE` Numeric(12,4), `QUANTITY` Numeric(12,3). Line math rounds half-up to cents per line (see `scripts/smoke_test.py`).
- Enums are Python `(str, enum.Enum)` classes stored as strings (`sa.Enum(..., native_enum=False)`) — never Postgres native enums (migration pain). Note: Python is 3.10, so no `StrEnum`.
- Constraint names come from the naming convention on `Base.metadata` (`app/core/db.py`) — don't name constraints ad hoc.
- **Every new model must be imported in `app/models/__init__.py`**, otherwise Alembic autogenerate silently misses its table.
- Tax codes (SR 9%, ZR, ES) live in the `tax_codes` table — GST rate changes are data edits, never hardcoded in logic.
