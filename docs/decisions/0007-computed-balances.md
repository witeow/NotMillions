# 0007. Balances computed, never stored

Date: 2026-07-03
Status: Accepted

## Context

An invoice's paid/outstanding amount could be stored as a column (fast to read, but a second copy of the truth that drifts the moment an update is missed) or derived on demand from the payments and credit notes applied to it.

## Decision

No stored balance columns anywhere. An invoice's settled amount is the sum of its `payment_allocations` and `credit_note_allocations` rows; outstanding = total − that sum. Allocation amounts carry `CHECK (amount > 0)` since these rows are load-bearing accounting data. A payment's unallocated remainder is on-account customer credit, shown in statements.

## Consequences

- The books cannot drift: there is exactly one source of truth for what's been paid.
- AR aging and statements are aggregate queries over allocations — trivial at this deployment's data volumes (thousands of invoices, not millions).
- Invoice status (`PARTIALLY_PAID`/`PAID`) is the one denormalized echo of this data; the posting service must update it whenever allocations change.
