from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    JournalEntry,
    JournalLine,
    JournalSourceType,
    next_document_number,
)

CENT = Decimal("0.01")


class PostingError(Exception):
    pass


class InvalidStateTransition(PostingError):
    pass


class AllocationError(PostingError):
    pass


class BalanceError(PostingError):
    pass


def compute_line_total(
    qty: Decimal, unit_price: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (subtotal, tax_amount, line_total) rounded to cents."""
    subtotal = (qty * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
    tax_amount = (subtotal * tax_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return subtotal, tax_amount, subtotal + tax_amount


def recompute_document_totals(
    lines: list,
) -> tuple[Decimal, Decimal, Decimal]:
    """Sum line-level amounts into document totals.

    Each line must have `line_total` and `tax_amount` attributes, and a
    subtotal derivable as `line_total - tax_amount`.
    """
    subtotal = sum((ln.line_total - ln.tax_amount) for ln in lines)
    tax_total = sum(ln.tax_amount for ln in lines)
    return subtotal, tax_total, subtotal + tax_total


def assert_balanced(lines: list[JournalLine]) -> None:
    total_dr = sum(ln.debit for ln in lines)
    total_cr = sum(ln.credit for ln in lines)
    if total_dr != total_cr:
        raise BalanceError(
            f"Journal entry is unbalanced: DR {total_dr} != CR {total_cr}"
        )


def get_account(session: Session, code: str) -> Account:
    account = session.scalar(select(Account).where(Account.code == code))
    if account is None:
        raise PostingError(f"System account {code!r} not found — run seed first")
    return account


def create_journal_entry(
    session: Session,
    *,
    date,
    memo: str,
    source_type: JournalSourceType,
    source_id: int | None,
    lines_data: list[dict],
) -> JournalEntry:
    """Build a balanced JournalEntry with lines and persist it.

    lines_data: list of dicts with keys account_id, debit, credit.
    """
    lines = [JournalLine(**ld) for ld in lines_data]
    assert_balanced(lines)

    entry = JournalEntry(
        entry_no=next_document_number(session, "JOURNAL"),
        date=date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        lines=lines,
    )
    session.add(entry)
    session.flush()
    return entry


def create_reversing_entry(
    session: Session,
    original: JournalEntry,
    *,
    memo: str | None = None,
) -> JournalEntry:
    """Create a new entry that reverses the original (debits↔credits)."""
    lines_data = []
    for ln in original.lines:
        lines_data.append(
            {"account_id": ln.account_id, "debit": ln.credit, "credit": ln.debit}
        )
    return create_journal_entry(
        session,
        date=original.date,
        memo=memo or f"Reversal of {original.entry_no}",
        source_type=original.source_type,
        source_id=original.source_id,
        lines_data=lines_data,
    )
