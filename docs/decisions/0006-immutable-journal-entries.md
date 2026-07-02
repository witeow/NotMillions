# 0006. Immutable double-entry journal

Date: 2026-07-03
Status: Accepted

## Context

The general ledger is the source of truth for every report. If journal entries can be edited or deleted, the books can silently stop reconciling and history becomes unauditable.

## Decision

Every posted document writes a balanced `JournalEntry` with `JournalLine` rows:

- Invoice: DR Accounts Receivable / CR income per line / CR GST Output Tax
- Payment: DR bank or cash / CR Accounts Receivable
- Credit note: DR income + DR GST Output Tax / CR Accounts Receivable

Entries are never edited or deleted. Voiding a document posts a reversing entry. The journal tables have **no delete cascades** — a deletion attempt fails loudly on the foreign key. The DB enforces what it cheaply can (each line single-sided and non-negative via check constraints); debits = credits per entry is enforced by the posting service and tests, since SQL can't express a cross-row sum constraint cleanly.

## Consequences

- The ledger is append-only and auditable; any balance can be re-derived at any date.
- Corrections cost an extra entry rather than an edit — the standard accounting trade.
- The posting service (next phase) is the single choke point where balance must be asserted; nothing else may write journal rows.
