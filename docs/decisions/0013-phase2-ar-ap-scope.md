# 0013. Phase 2 expanded to include AP (purchases)

Date: 2026-08-12
Status: Accepted
Supersedes: 0001 (scope section only — purchases/AP is no longer deferred)

## Context

The original scope (ADR 0001) deferred purchases/AP to focus on the sales-side MVP. However, the business — a small Singapore construction company — needs to track both sides: invoicing clients (progress claims, variation orders) and recording supplier costs (materials, subcontractor costs, worker wages/levy, office expenses). Tracking only one side would not produce useful financials.

## Decision

Expand Phase 2 to cover both AR and AP. The AP side mirrors the AR design:

| AR (Sales) | AP (Purchases) |
|---|---|
| Customer | Supplier |
| Invoice | Bill |
| Payment (received) | PaymentMade (outgoing) |
| CreditNote | DebitNote |

**Naming**: "Bill" (not "PurchaseInvoice") follows the convention in QuickBooks/Xero/Millions. "PaymentMade" parallels "Payment" (received).

**Tax codes**: Separate input tax codes per IRAS convention — TX (standard-rated input, 9%), BL (blocked input, 0%), NR (not registered, 0%) — each pointing to the GST Input Tax account (1300). This keeps the tax_code model unchanged and makes GST F5 reporting straightforward later.

**Chart of accounts**: 5000-series for direct costs (materials, subcontractor, equipment), 6000-series for operating expenses (wages, CPF, levy, office). This separation enables gross profit calculation in Phase 3.

## Consequences

- Phase 2 is larger but delivers a complete double-entry picture (both sides of the business).
- The posting service covers 6 document types instead of 3, but shares helpers (balanced JE creation, reversals, line total computation).
- GST F5 reporting (Phase 3) can aggregate by tax code direction — SR/ZR/ES for output, TX/BL/NR for input.
