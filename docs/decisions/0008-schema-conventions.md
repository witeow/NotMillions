# 0008. Schema conventions

Date: 2026-07-03
Status: Accepted

## Context

A schema this interconnected needs uniform conventions, and two classes of subtle bug surfaced while building it: Alembic autogenerate silently skips models that aren't imported, and a column named `date` shadows `datetime.date` in its class namespace — which silently broke SQLAlchemy's nullable inference for a later `Mapped[date | None]` annotation (caught in review before the first commit).

## Decision

- Money: `Numeric(12,2)`; unit prices `Numeric(12,4)`; quantities `Numeric(12,3)` — via the shared constants in `app/models/base.py`. All arithmetic in `Decimal`, rounded half-up to cents per line. Float money is a bug.
- Enums: Python `(str, enum.Enum)` stored as strings (`sa.Enum(..., native_enum=False)`). Postgres native enums are banned (ALTER TYPE migration pain). No `StrEnum` — Python floor is 3.10.
- Constraint names come from the naming convention on `Base.metadata` (`app/core/db.py`); never name constraints ad hoc.
- Every model must be imported in `app/models/__init__.py` or autogenerate misses its table.
- Date columns are annotated `Mapped[datetime.date]` (module-qualified) — never a bare `date`, because document models have a `date` column that shadows it.
- Migrations are reviewed by hand after autogenerate, and `alembic check` (empty diff) gates every commit that touches models.

## Consequences

- The date-shadowing and missing-import failure modes are documented and mechanically checkable.
- New contributors (or future Claude sessions) follow one style; deviations are review findings, not debates.
