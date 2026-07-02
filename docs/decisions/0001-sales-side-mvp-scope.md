# 0001. Sales-side MVP scope

Date: 2026-07-03
Status: Accepted

## Context

NotMillions mimics "Millions" and similar SG/MY on-prem accounting packages (AutoCount, SQL Account, UBS), which span sales, purchases, inventory, banking, and payroll. This is a solo side project — building all of that at once guarantees finishing none of it. The immediate real-world use case (invoicing customers and tracking who owes what) is the sales cycle.

## Decision

Build the sales side only, end to end, before anything else: customers, quotation → invoice, payments received, credit notes, GL auto-posting, AR aging, customer statements, basic P&L and balance sheet.

Explicitly deferred: purchases/AP, inventory/stock, bank reconciliation, payroll, multi-currency, LHDN e-invoice compliance.

## Consequences

- One complete, usable workflow instead of five half-finished ones; the GL foundation is shared, so later modules (AP mirrors AR) slot into the same journal.
- The chart of accounts is seeded minimal (no purchase/inventory accounts yet); expect additions when AP arrives.
- Reports that need the expense side (full P&L) will be revenue-heavy until purchases exist.
