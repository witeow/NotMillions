from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import BillStatus, DebitNoteStatus, JournalEntry
from app.services.bill_service import create_bill, post_bill
from app.services.debit_note_service import (
    allocate_debit_note,
    create_debit_note,
    post_debit_note,
    void_debit_note,
)
from app.services.shared import AllocationError, PostingError
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


def _dn_line(description, qty, unit_price, tax_code_id, expense_account_id):
    return {
        "description": description,
        "qty": Decimal(str(qty)),
        "unit_price": Decimal(str(unit_price)),
        "tax_code_id": tax_code_id,
        "expense_account_id": expense_account_id,
    }


def _make_posted_bill(db, supplier, tx, materials_account, amount="500.0000"):
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


class TestPostDebitNote:
    def test_creates_correct_je(self, db, supplier, tx, materials_account):
        dn = create_debit_note(
            db,
            supplier_id=supplier.id,
            dn_date=date.today(),
            lines_data=[_dn_line("Return cement", 10, "5.0000", tx.id, materials_account)],
        )
        posted = post_debit_note(db, dn)
        assert posted.status == DebitNoteStatus.POSTED

        entry = db.get(JournalEntry, posted.journal_entry_id)
        total_dr = sum(l.debit for l in entry.lines)
        total_cr = sum(l.credit for l in entry.lines)
        assert total_dr == total_cr == posted.total

        dr_accounts = {l.account_id for l in entry.lines if l.debit > 0}
        cr_accounts = {l.account_id for l in entry.lines if l.credit > 0}
        ap_id = _get_account(db, "2000")
        assert ap_id in dr_accounts
        assert materials_account in cr_accounts


class TestAllocateDebitNote:
    def test_reduces_outstanding(self, db, supplier, tx, materials_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        dn = create_debit_note(
            db,
            supplier_id=supplier.id,
            dn_date=date.today(),
            lines_data=[_dn_line("Return", 1, "50.0000", tx.id, materials_account)],
        )
        post_debit_note(db, dn)
        allocate_debit_note(db, dn, [{"bill_id": bill.id, "amount": dn.total}])
        assert bill.status == BillStatus.PARTIALLY_PAID

    def test_exceeds_outstanding_raises(self, db, supplier, tx, materials_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account, amount="10.0000")
        dn = create_debit_note(
            db,
            supplier_id=supplier.id,
            dn_date=date.today(),
            lines_data=[_dn_line("Big return", 1, "999.0000", tx.id, materials_account)],
        )
        post_debit_note(db, dn)
        with pytest.raises(AllocationError, match="exceeds outstanding"):
            allocate_debit_note(db, dn, [{"bill_id": bill.id, "amount": dn.total}])


class TestVoidDebitNote:
    def test_void_with_allocations_raises(self, db, supplier, tx, materials_account):
        bill = _make_posted_bill(db, supplier, tx, materials_account)
        dn = create_debit_note(
            db,
            supplier_id=supplier.id,
            dn_date=date.today(),
            lines_data=[_dn_line("Return", 1, "50.0000", tx.id, materials_account)],
        )
        post_debit_note(db, dn)
        allocate_debit_note(db, dn, [{"bill_id": bill.id, "amount": dn.total}])
        with pytest.raises(PostingError, match="has allocations"):
            void_debit_note(db, dn)

    def test_void_unallocated(self, db, supplier, tx, materials_account):
        dn = create_debit_note(
            db,
            supplier_id=supplier.id,
            dn_date=date.today(),
            lines_data=[_dn_line("Return", 1, "100.0000", tx.id, materials_account)],
        )
        post_debit_note(db, dn)
        voided = void_debit_note(db, dn)
        assert voided.status == DebitNoteStatus.VOID
