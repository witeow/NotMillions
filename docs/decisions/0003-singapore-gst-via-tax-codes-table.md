# 0003. Singapore GST via a tax-codes table

Date: 2026-07-03
Status: Accepted

## Context

The target business is in Singapore, so GST is the only tax regime the MVP must handle. But GST rates change (7% → 8% in 2023 → 9% in 2024), and hardcoding "9%" into invoice math would turn every future rate change into a code change and redeployment.

## Decision

Model Singapore GST only — no multi-country abstraction — but keep all tax knowledge in the `tax_codes` table: code, name, rate, and the GL account the collected tax posts to. Seeded codes: SR (standard-rated 9%), ZR (zero-rated 0%), ES (exempt). Each document line references a tax code; nothing in application logic knows a rate.

## Consequences

- A rate change is an UPDATE (or a new code) — no schema or code change.
- Line math must always read the rate from the referenced tax code; any literal `9` in tax logic is a bug.
- Malaysia SST support, if ever needed, means new rows and GST-report changes, not a remodel.
