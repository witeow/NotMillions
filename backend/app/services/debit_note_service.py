from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Bill,
    BillStatus,
    DebitNote,
    DebitNoteAllocation,
    DebitNoteLine,
    DebitNoteStatus,
    JournalSourceType,
    TaxCode,
    next_document_number,
)
from app.services.shared import (
    AllocationError,
    InvalidStateTransition,
    PostingError,
    compute_line_total,
    create_journal_entry,
    create_reversing_entry,
    get_account,
)


def create_debit_note(
    session: Session,
    *,
    supplier_id: int,
    dn_date: date,
    lines_data: list[dict],
    notes: str | None = None,
) -> DebitNote:
    number = next_document_number(session, "DEBIT_NOTE")
    lines = []
    for i, ld in enumerate(lines_data, 1):
        tax_code = session.get(TaxCode, ld["tax_code_id"]) if ld.get("tax_code_id") else None
        rate = tax_code.rate if tax_code else Decimal("0.00")
        subtotal, tax_amount, line_total = compute_line_total(
            ld.get("qty", Decimal("1")), ld["unit_price"], rate
        )
        lines.append(
            DebitNoteLine(
                line_no=i,
                item_id=ld.get("item_id"),
                description=ld["description"],
                qty=ld.get("qty", Decimal("1")),
                unit_price=ld["unit_price"],
                tax_code_id=ld.get("tax_code_id"),
                tax_amount=tax_amount,
                line_total=line_total,
                expense_account_id=ld.get("expense_account_id"),
            )
        )

    doc_subtotal = sum(ln.line_total - ln.tax_amount for ln in lines)
    doc_tax = sum(ln.tax_amount for ln in lines)

    dn = DebitNote(
        number=number,
        supplier_id=supplier_id,
        date=dn_date,
        status=DebitNoteStatus.DRAFT,
        subtotal=doc_subtotal,
        tax_total=doc_tax,
        total=doc_subtotal + doc_tax,
        notes=notes,
        lines=lines,
    )
    session.add(dn)
    session.flush()
    return dn


def post_debit_note(session: Session, dn: DebitNote) -> DebitNote:
    if dn.status != DebitNoteStatus.DRAFT:
        raise InvalidStateTransition(
            f"Cannot post debit note {dn.number}: status is {dn.status.value}"
        )

    ap = get_account(session, "2000")
    gst_input = get_account(session, "1300")

    je_lines = [
        {"account_id": ap.id, "debit": dn.total, "credit": Decimal("0.00")},
    ]
    expense_totals: dict[int, Decimal] = {}
    for ln in dn.lines:
        acct_id = ln.expense_account_id
        if acct_id is None:
            raise PostingError(f"Debit note line {ln.line_no} has no expense account")
        subtotal = ln.line_total - ln.tax_amount
        expense_totals[acct_id] = expense_totals.get(acct_id, Decimal("0.00")) + subtotal

    for acct_id, amount in expense_totals.items():
        je_lines.append(
            {"account_id": acct_id, "debit": Decimal("0.00"), "credit": amount}
        )

    if dn.tax_total > 0:
        je_lines.append(
            {"account_id": gst_input.id, "debit": Decimal("0.00"), "credit": dn.tax_total}
        )

    entry = create_journal_entry(
        session,
        date=dn.date,
        memo=f"Debit Note {dn.number}",
        source_type=JournalSourceType.DEBIT_NOTE,
        source_id=dn.id,
        lines_data=je_lines,
    )
    dn.status = DebitNoteStatus.POSTED
    dn.journal_entry_id = entry.id
    session.flush()
    return dn


def allocate_debit_note(
    session: Session,
    dn: DebitNote,
    allocations: list[dict],
) -> DebitNote:
    if dn.status != DebitNoteStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot allocate debit note {dn.number}: status is {dn.status.value}"
        )

    from app.services.payment_made_service import (
        _update_bill_status,
        compute_bill_outstanding,
    )

    existing_allocated = sum(a.amount for a in dn.allocations)
    new_total = sum(a["amount"] for a in allocations)
    if existing_allocated + new_total > dn.total:
        raise AllocationError(
            f"Allocations ({existing_allocated + new_total}) exceed "
            f"debit note total ({dn.total})"
        )

    for alloc in allocations:
        bill = session.get(Bill, alloc["bill_id"])
        if bill is None:
            raise AllocationError(f"Bill {alloc['bill_id']} not found")
        if bill.supplier_id != dn.supplier_id:
            raise AllocationError(
                f"Bill {bill.number} belongs to a different supplier"
            )
        if bill.status not in (BillStatus.POSTED, BillStatus.PARTIALLY_PAID):
            raise AllocationError(
                f"Cannot allocate against bill {bill.number}: "
                f"status is {bill.status.value}"
            )
        outstanding = compute_bill_outstanding(session, bill)
        if alloc["amount"] > outstanding:
            raise AllocationError(
                f"Allocation {alloc['amount']} exceeds outstanding "
                f"{outstanding} on bill {bill.number}"
            )

        dn.allocations.append(
            DebitNoteAllocation(bill_id=alloc["bill_id"], amount=alloc["amount"])
        )

    session.flush()
    for alloc in allocations:
        bill = session.get(Bill, alloc["bill_id"])
        _update_bill_status(session, bill)
    session.flush()
    return dn


def void_debit_note(session: Session, dn: DebitNote) -> DebitNote:
    if dn.status != DebitNoteStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot void debit note {dn.number}: status is {dn.status.value}"
        )

    if dn.allocations:
        raise PostingError(
            f"Cannot void debit note {dn.number}: it has allocations"
        )

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, dn.journal_entry_id)
    create_reversing_entry(
        session, original_entry, memo=f"Void Debit Note {dn.number}"
    )
    dn.status = DebitNoteStatus.VOID
    session.flush()
    return dn
