from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import InvoiceStatus
from app.services.invoice_service import create_invoice, post_invoice, void_invoice
from app.services.shared import InvalidStateTransition, PostingError
from tests.conftest import _get_account, _get_tax_code, make_customer, make_item


@pytest.fixture()
def customer(db):
    return make_customer(db)


@pytest.fixture()
def sr(db):
    return _get_tax_code(db, "SR")


@pytest.fixture()
def zr(db):
    return _get_tax_code(db, "ZR")


@pytest.fixture()
def sales_account(db):
    return _get_account(db, "4000")


def _line(description, qty, unit_price, tax_code_id, income_account_id):
    return {
        "description": description,
        "qty": Decimal(str(qty)),
        "unit_price": Decimal(str(unit_price)),
        "tax_code_id": tax_code_id,
        "income_account_id": income_account_id,
    }


class TestCreateInvoice:
    def test_creates_draft(self, db, customer, sr, sales_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Service", 10, "100.0000", sr.id, sales_account)],
        )
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.number == "INV-0001"
        assert inv.subtotal == Decimal("1000.00")
        assert inv.tax_total == Decimal("90.00")
        assert inv.total == Decimal("1090.00")
        assert len(inv.lines) == 1

    def test_mixed_tax_codes(self, db, customer, sr, zr, sales_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[
                _line("Taxable", 10, "150.0000", sr.id, sales_account),
                _line("Zero-rated", 2, "80.0000", zr.id, sales_account),
            ],
        )
        assert inv.subtotal == Decimal("1660.00")
        assert inv.tax_total == Decimal("135.00")
        assert inv.total == Decimal("1795.00")


class TestPostInvoice:
    def test_post_creates_balanced_je(self, db, customer, sr, sales_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Service", 10, "100.0000", sr.id, sales_account)],
        )
        posted = post_invoice(db, inv)
        assert posted.status == InvoiceStatus.POSTED
        assert posted.journal_entry_id is not None

        from app.models import JournalEntry

        entry = db.get(JournalEntry, posted.journal_entry_id)
        total_dr = sum(l.debit for l in entry.lines)
        total_cr = sum(l.credit for l in entry.lines)
        assert total_dr == total_cr == posted.total

        dr_accounts = {l.account_id for l in entry.lines if l.debit > 0}
        cr_accounts = {l.account_id for l in entry.lines if l.credit > 0}
        ar_id = _get_account(db, "1200")
        gst_output_id = _get_account(db, "2100")
        assert ar_id in dr_accounts
        assert sales_account in cr_accounts
        assert gst_output_id in cr_accounts

    def test_post_non_draft_raises(self, db, customer, sr, sales_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Service", 1, "100.0000", sr.id, sales_account)],
        )
        post_invoice(db, inv)
        with pytest.raises(InvalidStateTransition):
            post_invoice(db, inv)


class TestVoidInvoice:
    def test_void_creates_reversing_entry(self, db, customer, sr, sales_account):
        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Service", 1, "100.0000", sr.id, sales_account)],
        )
        post_invoice(db, inv)
        voided = void_invoice(db, inv)
        assert voided.status == InvoiceStatus.VOID

    def test_void_with_payment_raises(self, db, customer, sr, sales_account):
        from app.models import PaymentMethod
        from app.services.payment_service import create_payment

        inv = create_invoice(
            db,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[_line("Service", 1, "100.0000", sr.id, sales_account)],
        )
        post_invoice(db, inv)
        bank = _get_account(db, "1100")
        create_payment(
            db,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank,
            amount=inv.total,
            allocations=[{"invoice_id": inv.id, "amount": inv.total}],
        )
        with pytest.raises(PostingError, match="has allocations"):
            void_invoice(db, inv)
