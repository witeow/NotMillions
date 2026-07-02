# 0011. Dev Postgres on host port 5433

Date: 2026-07-03
Status: Accepted

## Context

The dev database container originally mapped 5432:5432. The development machine already runs a native Windows PostgreSQL service on 5432, which accepted the connections first — producing confusing "password authentication failed" errors while the container sat healthy and unreachable. (Docker Desktop bound the port anyway, so both listened.)

## Decision

Map the dev container to host port **5433** (`docker-compose.yml`); the default `DATABASE_URL` in `app/core/config.py` and `.env.example` uses 5433. The local 5432 Postgres is left untouched.

## Consequences

- No conflict with pre-existing local Postgres installs — a common situation, hence documented rather than treated as machine-specific.
- Anyone wiring up a DB client must remember 5433 for this project.
- Inside the compose network (future FastAPI container) the port is still 5432; only the host mapping differs.
