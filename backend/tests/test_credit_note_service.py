from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import CreditNoteStatus, InvoiceStatus
from app.services.credit_note_service import (
    allocate_credit_note,
    create_credit_note,
    post_credit_note,
    void_credit_note,
)
from app.services.invoice_service import create_invoice, post_invoice
from app.services.shared import AllocationError, InvalidStateTransition, PostingError
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


def _cn_line(description, qty, unit_price, tax_code_id, income_account_id):
    return {
        "description": description,
        "qty": Decimal(str(qty)),
        "unit_price": Decimal(str(unit_price)),
        "tax_code_id": tax_code_id,
        "income_account_id": income_account_id,
    }


def _make_posted_invoice(db, customer, sr, sales_account, amount="500.0000"):
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


class TestPostCreditNote:
    def test_creates_correct_je(self, db, customer, sr, sales_account):
        cn = create_credit_note(
            db,
            customer_id=customer.id,
            cn_date=date.today(),
            lines_data=[_cn_line("Return", 1, "100.0000", sr.id, sales_account)],
        )
        posted = post_credit_note(db, cn)
        assert posted.status == CreditNoteStatus.POSTED

        from app.models import JournalEntry

        entry = db.get(JournalEntry, posted.journal_entry_id)
        total_dr = sum(l.debit for l in entry.lines)
        total_cr = sum(l.credit for l in entry.lines)
        assert total_dr == total_cr == posted.total

        dr_accounts = {l.account_id for l in entry.lines if l.debit > 0}
        cr_accounts = {l.account_id for l in entry.lines if l.credit > 0}
        ar_id = _get_account(db, "1200")
        assert ar_id in cr_accounts
        assert sales_account in dr_accounts


class TestAllocateCreditNote:
    def test_reduces_outstanding(self, db, customer, sr, sales_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        cn = create_credit_note(
            db,
            customer_id=customer.id,
            cn_date=date.today(),
            lines_data=[_cn_line("Discount", 1, "50.0000", sr.id, sales_account)],
        )
        post_credit_note(db, cn)
        allocate_credit_note(
            db, cn, [{"invoice_id": inv.id, "amount": cn.total}]
        )
        assert inv.status == InvoiceStatus.PARTIALLY_PAID

    def test_exceeds_outstanding_raises(self, db, customer, sr, sales_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account, amount="10.0000")
        cn = create_credit_note(
            db,
            customer_id=customer.id,
            cn_date=date.today(),
            lines_data=[_cn_line("Big credit", 1, "999.0000", sr.id, sales_account)],
        )
        post_credit_note(db, cn)
        with pytest.raises(AllocationError, match="exceeds outstanding"):
            allocate_credit_note(
                db, cn, [{"invoice_id": inv.id, "amount": cn.total}]
            )


class TestVoidCreditNote:
    def test_void_with_allocations_raises(self, db, customer, sr, sales_account):
        inv = _make_posted_invoice(db, customer, sr, sales_account)
        cn = create_credit_note(
            db,
            customer_id=customer.id,
            cn_date=date.today(),
            lines_data=[_cn_line("Return", 1, "50.0000", sr.id, sales_account)],
        )
        post_credit_note(db, cn)
        allocate_credit_note(
            db, cn, [{"invoice_id": inv.id, "amount": cn.total}]
        )
        with pytest.raises(PostingError, match="has allocations"):
            void_credit_note(db, cn)

    def test_void_unallocated(self, db, customer, sr, sales_account):
        cn = create_credit_note(
            db,
            customer_id=customer.id,
            cn_date=date.today(),
            lines_data=[_cn_line("Return", 1, "100.0000", sr.id, sales_account)],
        )
        post_credit_note(db, cn)
        voided = void_credit_note(db, cn)
        assert voided.status == CreditNoteStatus.VOID
