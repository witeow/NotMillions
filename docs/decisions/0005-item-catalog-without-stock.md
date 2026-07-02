# 0005. Item catalog without stock tracking

Date: 2026-07-03
Status: Accepted

## Context

Invoice lines could be free text (simplest) or reference a product catalog (how Millions works — item codes make repeat billing fast). Full inventory tracking is deferred (ADR 0001), but most invoices bill the same things repeatedly.

## Decision

A simple `items` table: code, description, default unit price, default tax code, income account, unit of measure. Document lines reference an item optionally (`item_id` nullable) and may override price and description freely. No quantity-on-hand, no stock movements, no costing.

## Consequences

- Repeat invoicing is fast; one-off lines still work as free text.
- Line data is denormalized by design: the line stores its own description/price/tax at the time of billing, so later item edits never rewrite history.
- If inventory arrives later, `items` grows stock fields and movement tables; existing references remain valid.
