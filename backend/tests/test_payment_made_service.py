from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import BillStatus, JournalEntry, PaymentMadeStatus, PaymentMethod
from app.services.bill_service import create_bill, post_bill
from app.services.payment_made_service import create_payment_made, void_payment_made
from app.services.shared import AllocationError
from tests.conftest import _get_account, _get_tax_code, make_supplier


@pytest.fixture()
def supplier(db):
    return make_supplier(db)


@pytest.fixture()
def tx(db):
    return _get_tax_code(db, "TX")


@pytest.fixture()
def materials_account(db):
    return _get_account(db, "5000")


@pytest.fixture()
def bank_account(db):
    return _get_account(db, "1100")


def _make_posted_bill(db, supplier, tx, materials_account, amount="100.0000"):
    bill = create_bill(
        db,
        supplier_id=supplier.id,
        bill_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        lines_data=[{
            "description": "Materials",
            "qty": Decimal("1"),
            "unit_price": Decimal(amount),
            "tax_code_id": tx.id,
            "expense_account_id": materials_account,
        }],
    )
    post_bill(db, bill)
    return bill


class TestCreatePaymentMade:
    def test_full_allocation_marks_paid(self, db, supplier, tx, materials_account, bank_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        pmt = create_payment_made(
            db,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=bill.total,
            allocations=[{"bill_id": bill.id, "amount": bill.total}],
            reference="PayNow ref 12345",
        )
        assert pmt.status == PaymentMadeStatus.POSTED
        assert pmt.number == "PMT-0001"
        assert pmt.reference == "PayNow ref 12345"
        assert bill.status == BillStatus.PAID

    def test_partial_allocation(self, db, supplier, tx, materials_account, bank_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        create_payment_made(
            db,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.BANK_TRANSFER,
            bank_account_id=bank_account,
            amount=Decimal("50.00"),
            allocations=[{"bill_id": bill.id, "amount": Decimal("50.00")}],
        )
        assert bill.status == BillStatus.PARTIALLY_PAID

    def test_je_debits_ap_credits_bank(self, db, supplier, tx, materials_account, bank_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        pmt = create_payment_made(
            db,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=bill.total,
            allocations=[{"bill_id": bill.id, "amount": bill.total}],
        )
        entry = db.get(JournalEntry, pmt.journal_entry_id)
        dr_line = [l for l in entry.lines if l.debit > 0][0]
        cr_line = [l for l in entry.lines if l.credit > 0][0]
        ap_id = _get_account(db, "2000")
        assert dr_line.account_id == ap_id
        assert cr_line.account_id == bank_account

    def test_cross_supplier_raises(self, db, tx, materials_account, bank_account):
        sup1 = make_supplier(db, code="SUP-A", name="A")
        sup2 = make_supplier(db, code="SUP-B", name="B")
        bill = _make_posted_bill(db, sup1, tx, materials_account)
        with pytest.raises(AllocationError, match="different supplier"):
            create_payment_made(
                db,
                supplier_id=sup2.id,
                payment_date=date.today(),
                method=PaymentMethod.CASH,
                bank_account_id=bank_account,
                amount=bill.total,
                allocations=[{"bill_id": bill.id, "amount": bill.total}],
            )


class TestVoidPaymentMade:
    def test_void_reverts_bill_status(self, db, supplier, tx, materials_account, bank_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        pmt = create_payment_made(
            db,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=bill.total,
            allocations=[{"bill_id": bill.id, "amount": bill.total}],
        )
        assert bill.status == BillStatus.PAID
        void_payment_made(db, pmt)
        assert pmt.status == PaymentMadeStatus.VOID
        assert bill.status == BillStatus.POSTED
