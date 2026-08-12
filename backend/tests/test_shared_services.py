from decimal import Decimal

import pytest

from app.models import JournalLine, JournalSourceType
from app.services.shared import (
    BalanceError,
    assert_balanced,
    compute_line_total,
    create_journal_entry,
    create_reversing_entry,
    get_account,
    recompute_document_totals,
)


class TestComputeLineTotal:
    def test_basic(self):
        sub, tax, total = compute_line_total(
            Decimal("10"), Decimal("100.0000"), Decimal("9.00")
        )
        assert sub == Decimal("1000.00")
        assert tax == Decimal("90.00")
        assert total == Decimal("1090.00")

    def test_zero_rate(self):
        sub, tax, total = compute_line_total(
            Decimal("5"), Decimal("200.0000"), Decimal("0.00")
        )
        assert sub == Decimal("1000.00")
        assert tax == Decimal("0.00")
        assert total == Decimal("1000.00")

    def test_rounding_half_up(self):
        sub, tax, total = compute_line_total(
            Decimal("1"), Decimal("10.0050"), Decimal("9.00")
        )
        assert sub == Decimal("10.01")
        assert tax == Decimal("0.90")
        assert total == Decimal("10.91")

    def test_fractional_qty(self):
        sub, tax, total = compute_line_total(
            Decimal("2.5"), Decimal("33.3333"), Decimal("9.00")
        )
        assert sub == Decimal("83.33")
        assert tax == Decimal("7.50")
        assert total == Decimal("90.83")


class TestRecomputeDocumentTotals:
    def test_sums_lines(self):
        class FakeLine:
            def __init__(self, line_total, tax_amount):
                self.line_total = line_total
                self.tax_amount = tax_amount

        lines = [
            FakeLine(Decimal("109.00"), Decimal("9.00")),
            FakeLine(Decimal("200.00"), Decimal("0.00")),
        ]
        sub, tax, total = recompute_document_totals(lines)
        assert sub == Decimal("300.00")
        assert tax == Decimal("9.00")
        assert total == Decimal("309.00")


class TestAssertBalanced:
    def test_balanced_passes(self):
        lines = [
            JournalLine(account_id=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLine(account_id=2, debit=Decimal("0.00"), credit=Decimal("100.00")),
        ]
        assert_balanced(lines)

    def test_unbalanced_raises(self):
        lines = [
            JournalLine(account_id=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLine(account_id=2, debit=Decimal("0.00"), credit=Decimal("50.00")),
        ]
        with pytest.raises(BalanceError):
            assert_balanced(lines)


class TestCreateJournalEntry:
    def test_creates_balanced_entry(self, db):
        ar = get_account(db, "1200")
        sales = get_account(db, "4000")
        entry = create_journal_entry(
            db,
            date="2026-01-15",
            memo="Test entry",
            source_type=JournalSourceType.MANUAL,
            source_id=None,
            lines_data=[
                {"account_id": ar.id, "debit": Decimal("100.00"), "credit": Decimal("0.00")},
                {"account_id": sales.id, "debit": Decimal("0.00"), "credit": Decimal("100.00")},
            ],
        )
        assert entry.entry_no == "JE-0001"
        assert len(entry.lines) == 2

    def test_unbalanced_raises(self, db):
        ar = get_account(db, "1200")
        with pytest.raises(BalanceError):
            create_journal_entry(
                db,
                date="2026-01-15",
                memo="Bad entry",
                source_type=JournalSourceType.MANUAL,
                source_id=None,
                lines_data=[
                    {"account_id": ar.id, "debit": Decimal("100.00"), "credit": Decimal("0.00")},
                ],
            )


class TestCreateReversingEntry:
    def test_reverses_debits_and_credits(self, db):
        ar = get_account(db, "1200")
        sales = get_account(db, "4000")
        original = create_journal_entry(
            db,
            date="2026-01-15",
            memo="Original",
            source_type=JournalSourceType.MANUAL,
            source_id=None,
            lines_data=[
                {"account_id": ar.id, "debit": Decimal("500.00"), "credit": Decimal("0.00")},
                {"account_id": sales.id, "debit": Decimal("0.00"), "credit": Decimal("500.00")},
            ],
        )
        reversal = create_reversing_entry(db, original)
        assert reversal.entry_no == "JE-0002"
        assert reversal.memo == f"Reversal of {original.entry_no}"
        dr_line = [l for l in reversal.lines if l.debit > 0][0]
        cr_line = [l for l in reversal.lines if l.credit > 0][0]
        assert dr_line.account_id == sales.id
        assert dr_line.debit == Decimal("500.00")
        assert cr_line.account_id == ar.id
        assert cr_line.credit == Decimal("500.00")
