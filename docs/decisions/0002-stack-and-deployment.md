# 0002. Stack and self-hosted deployment

Date: 2026-07-03
Status: Accepted

## Context

The developer is a data engineer: strong Python/Java and PostgreSQL, no frontend experience but wants to learn it. The product promise mirrors the original software's appeal — one-time install on your own hardware, no subscription — and the target machine is a home-lab TrueNAS box.

## Decision

- Backend: Python with SQLAlchemy 2.0 + Alembic on PostgreSQL 16; FastAPI for the API layer (next phase).
- Frontend: React + TypeScript (planned) — chosen deliberately as the learning investment, being the most transferable frontend stack.
- Deployment: Docker Compose on the home server. No Kubernetes, managed databases, or cloud-native patterns — solo-dev, single-tenant simplicity is a feature.

## Consequences

- Plays to existing strengths on the backend so the learning budget is spent on the frontend.
- Architecture must stay runnable as a couple of containers and one volume; anything requiring cloud services is out.
- Frontend work should be paced as teaching material (explain React concepts as they appear), not assumed knowledge.
