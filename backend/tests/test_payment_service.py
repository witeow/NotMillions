from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import InvoiceStatus, PaymentMethod, PaymentStatus
from app.services.invoice_service import create_invoice, post_invoice
from app.services.payment_service import create_payment, void_payment
from app.services.shared import AllocationError, InvalidStateTransition
from tests.conftest import _get_account, _get_tax_code, make_customer


@pytest.fixture()
def customer(db):
    return make_customer(db)


@pytest.fixture()
def sr(db):
    return _get_tax_code(db, "SR")


@pytest.fixture()
def sales_account(db):
    return _get_account(db, "4000")


@pytest.fixture()
def bank_account(db):
    return _get_account(db, "1100")


def _make_posted_invoice(db, customer, sr, sales_account, amount="100.0000"):
    inv = create_invoice(
        db,
        customer_id=customer.id,
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        lines_data=[{
            "description": "Service",
            "qty": Decimal("1"),
            "unit_price": Decimal(amount),
            "tax_code_id": sr.id,
            "income_account_id": sales_account,
        }],
    )
    post_invoice(db, inv)
    return inv


class TestCreatePayment:
    def test_full_allocation_marks_paid(self, db, customer, sr, sales_account, bank_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        pmt = create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=inv.total,
            allocations=[{"invoice_id": inv.id, "amount": inv.total}],
        )
        assert pmt.status == PaymentStatus.POSTED
        assert pmt.number == "RCT-0001"
        assert inv.status == InvoiceStatus.PAID

    def test_partial_allocation(self, db, customer, sr, sales_account, bank_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        partial = Decimal("50.00")
        create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.BANK_TRANSFER,
            bank_account_id=bank_account,
            amount=partial,
            allocations=[{"invoice_id": inv.id, "amount": partial}],
        )
        assert inv.status == InvoiceStatus.PARTIALLY_PAID

    def test_unallocated_on_account(self, db, customer, bank_account):
        pmt = create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.CASH,
            bank_account_id=bank_account,
            amount=Decimal("500.00"),
        )
        assert pmt.status == PaymentStatus.POSTED
        assert len(pmt.allocations) == 0

    def test_allocation_exceeds_outstanding(self, db, customer, sr, sales_account, bank_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        with pytest.raises(AllocationError, match="exceeds outstanding"):
            create_payment(
                db,
                customer_id=customer.id,
                payment_date=date.today(),
                method=PaymentMethod.CASH,
                bank_account_id=bank_account,
                amount=Decimal("99999.00"),
                allocations=[{"invoice_id": inv.id, "amount": Decimal("99999.00")}],
            )

    def test_cross_customer_raises(self, db, sr, sales_account, bank_account):
        cust1 = make_customer(db, code="CUST-A", name="A")
        cust2 = make_customer(db, code="CUST-B", name="B")
        inv = _make_posted_invoice(db, cust1, sr, sales_account)
        with pytest.raises(AllocationError, match="different customer"):
            create_payment(
                db,
                customer_id=cust2.id,
                payment_date=date.today(),
                method=PaymentMethod.CASH,
                bank_account_id=bank_account,
                amount=inv.total,
                allocations=[{"invoice_id": inv.id, "amount": inv.total}],
            )

    def test_against_draft_raises(self, db, customer, sr, sales_account, bank_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[{
                "description": "Service",
                "qty": Decimal("1"),
                "unit_price": Decimal("100.0000"),
                "tax_code_id": sr.id,
                "income_account_id": sales_account,
            }],
        )
        with pytest.raises(AllocationError, match="DRAFT"):
            create_payment(
                db,
                customer_id=customer.id,
                payment_date=date.today(),
                method=PaymentMethod.CASH,
                bank_account_id=bank_account,
                amount=inv.total,
                allocations=[{"invoice_id": inv.id, "amount": inv.total}],
            )

    def test_je_debits_bank_credits_ar(self, db, customer, sr, sales_account, bank_account):
        from app.models import JournalEntry

        inv = _make_posted_invoice(db, customer, sr, sales_account)
        pmt = create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=inv.total,
            allocations=[{"invoice_id": inv.id, "amount": inv.total}],
        )
        entry = db.get(JournalEntry, pmt.journal_entry_id)
        dr_line = [l for l in entry.lines if l.debit > 0][0]
        cr_line = [l for l in entry.lines if l.credit > 0][0]
        assert dr_line.account_id == bank_account
        assert cr_line.account_id == _get_account(db, "1200")


class TestVoidPayment:
    def test_void_reverts_invoice_status(self, db, customer, sr, sales_account, bank_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        pmt = create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank_account,
            amount=inv.total,
            allocations=[{"invoice_id": inv.id, "amount": inv.total}],
        )
        assert inv.status == InvoiceStatus.PAID
        void_payment(db, pmt)
        assert pmt.status == PaymentStatus.VOID
        assert inv.status == InvoiceStatus.POSTED
