# 0010. uv for dependency management

Date: 2026-07-03
Status: Accepted

## Context

The backend needs reproducible Python environments. The initial setup used plain `python -m venv` + pip; the developer prefers uv (faster, single tool for venv + lock + run, modern default).

## Decision

uv manages everything: `uv sync` creates `backend/.venv` and installs from `pyproject.toml` (the app itself as an editable package via the setuptools build backend), `uv.lock` is committed, and all tooling runs through `uv run …` from `backend/`.

## Consequences

- One-command setup and exact reproducibility across machines (dev box → TrueNAS).
- Commands in docs assume `uv run`; contributors don't activate the venv manually.
- uv must be installed on any machine touching the backend (standalone installer, no Python needed to bootstrap).
