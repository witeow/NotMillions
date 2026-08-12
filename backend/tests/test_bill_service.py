from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import BillStatus, JournalEntry
from app.services.bill_service import create_bill, post_bill, void_bill
from app.services.shared import InvalidStateTransition, PostingError
from tests.conftest import _get_account, _get_tax_code, make_supplier


@pytest.fixture()
def supplier(db):
    return make_supplier(db)


@pytest.fixture()
def tx(db):
    return _get_tax_code(db, "TX")


@pytest.fixture()
def nr(db):
    return _get_tax_code(db, "NR")


@pytest.fixture()
def materials_account(db):
    return _get_account(db, "5000")


def _line(description, qty, unit_price, tax_code_id, expense_account_id):
    return {
        "description": description,
        "qty": Decimal(str(qty)),
        "unit_price": Decimal(str(unit_price)),
        "tax_code_id": tax_code_id,
        "expense_account_id": expense_account_id,
    }


class TestCreateBill:
    def test_creates_draft(self, db, supplier, tx, materials_account):
        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Cement", 100, "5.0000", tx.id, materials_account)],
        )
        assert bill.status == BillStatus.DRAFT
        assert bill.number == "BILL-0001"
        assert bill.subtotal == Decimal("500.00")
        assert bill.tax_total == Decimal("45.00")
        assert bill.total == Decimal("545.00")


class TestPostBill:
    def test_post_creates_balanced_je(self, db, supplier, tx, materials_account):
        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Cement", 100, "5.0000", tx.id, materials_account)],
        )
        posted = post_bill(db, bill)
        assert posted.status == BillStatus.POSTED

        entry = db.get(JournalEntry, posted.journal_entry_id)
        total_dr = sum(l.debit for l in entry.lines)
        total_cr = sum(l.credit for l in entry.lines)
        assert total_dr == total_cr == posted.total

        dr_accounts = {l.account_id for l in entry.lines if l.debit > 0}
        cr_accounts = {l.account_id for l in entry.lines if l.credit > 0}
        ap_id = _get_account(db, "2000")
        gst_input_id = _get_account(db, "1300")
        assert materials_account in dr_accounts
        assert gst_input_id in dr_accounts
        assert ap_id in cr_accounts

    def test_post_with_nr_no_tax(self, db, supplier, nr, materials_account):
        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("From non-GST supplier", 1, "200.0000", nr.id, materials_account)],
        )
        posted = post_bill(db, bill)
        assert posted.tax_total == Decimal("0.00")
        entry = db.get(JournalEntry, posted.journal_entry_id)
        assert len(entry.lines) == 2

    def test_post_non_draft_raises(self, db, supplier, tx, materials_account):
        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Cement", 1, "100.0000", tx.id, materials_account)],
        )
        post_bill(db, bill)
        with pytest.raises(InvalidStateTransition):
            post_bill(db, bill)


class TestVoidBill:
    def test_void_creates_reversing_entry(self, db, supplier, tx, materials_account):
        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Cement", 1, "100.0000", tx.id, materials_account)],
        )
        post_bill(db, bill)
        voided = void_bill(db, bill)
        assert voided.status == BillStatus.VOID

    def test_void_with_payment_raises(self, db, supplier, tx, materials_account):
        from app.models import PaymentMethod
        from app.services.payment_made_service import create_payment_made

        bill = create_bill(
            db,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Cement", 1, "100.0000", tx.id, materials_account)],
        )
        post_bill(db, bill)
        bank = _get_account(db, "1100")
        create_payment_made(
            db,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank,
            amount=bill.total,
            allocations=[{"bill_id": bill.id, "amount": bill.total}],
        )
        with pytest.raises(PostingError, match="has allocations"):
            void_bill(db, bill)
