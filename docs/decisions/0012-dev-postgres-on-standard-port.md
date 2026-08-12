# 0012. Dev Postgres on standard port 5432

Date: 2026-08-12
Status: Accepted
Supersedes: 0011

## Context

ADR 0011 mapped the dev container to host port 5433 to avoid a conflict with a local PostgreSQL on the original development machine (Windows). The current development machine (macOS / OrbStack) has no local Postgres, so the non-standard port added friction with no benefit.

## Decision

Map the dev container back to the standard host port **5432**. The default `DATABASE_URL` in `app/core/config.py` and `.env.example` uses 5432.

## Consequences

- Standard port — no special port to remember when connecting DB clients.
- If a machine already runs Postgres on 5432, override the host mapping in `docker-compose.yml` and set `DATABASE_URL` in `backend/.env`.
