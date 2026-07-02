# 0009. Row-locked document sequences

Date: 2026-07-03
Status: Accepted

## Context

Document numbers (INV-0001, QT-0001, …) must be gapless-looking, per-type, and unique. Postgres `SERIAL` can't be shared across formatting rules, and naive read-increment-write races under concurrent requests.

## Decision

A `document_sequences` table (doc type, prefix, next number, padding) and one helper — `next_document_number()` in `app/models/sequence.py` — that reads the row with `SELECT … FOR UPDATE`, formats the number, and increments. It must be called inside the same transaction that saves the document.

## Consequences

- Concurrent posting can't issue duplicates; the unique constraint on each document's `number` is the backstop.
- A rolled-back transaction returns its number to the pool (the increment rolls back too), so gaps stay rare.
- The lock serializes number issuance per document type — irrelevant at this scale, worth knowing if throughput ever matters.
