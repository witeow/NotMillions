from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Bill,
    BillLine,
    BillStatus,
    JournalSourceType,
    TaxCode,
    next_document_number,
)
from app.services.shared import (
    InvalidStateTransition,
    PostingError,
    compute_line_total,
    create_journal_entry,
    create_reversing_entry,
    get_account,
)


def create_bill(
    session: Session,
    *,
    supplier_id: int,
    bill_date: date,
    due_date: date,
    lines_data: list[dict],
    notes: str | None = None,
) -> Bill:
    number = next_document_number(session, "BILL")
    lines = []
    for i, ld in enumerate(lines_data, 1):
        tax_code = session.get(TaxCode, ld["tax_code_id"]) if ld.get("tax_code_id") else None
        rate = tax_code.rate if tax_code else Decimal("0.00")
        subtotal, tax_amount, line_total = compute_line_total(
            ld.get("qty", Decimal("1")), ld["unit_price"], rate
        )
        lines.append(
            BillLine(
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

    bill = Bill(
        number=number,
        supplier_id=supplier_id,
        date=bill_date,
        due_date=due_date,
        status=BillStatus.DRAFT,
        subtotal=doc_subtotal,
        tax_total=doc_tax,
        total=doc_subtotal + doc_tax,
        notes=notes,
        lines=lines,
    )
    session.add(bill)
    session.flush()
    return bill


def post_bill(session: Session, bill: Bill) -> Bill:
    if bill.status != BillStatus.DRAFT:
        raise InvalidStateTransition(
            f"Cannot post bill {bill.number}: status is {bill.status.value}"
        )

    ap = get_account(session, "2000")
    gst_input = get_account(session, "1300")

    je_lines = []
    expense_totals: dict[int, Decimal] = {}
    for ln in bill.lines:
        acct_id = ln.expense_account_id
        if acct_id is None:
            raise PostingError(f"Bill line {ln.line_no} has no expense account")
        subtotal = ln.line_total - ln.tax_amount
        expense_totals[acct_id] = expense_totals.get(acct_id, Decimal("0.00")) + subtotal

    for acct_id, amount in expense_totals.items():
        je_lines.append(
            {"account_id": acct_id, "debit": amount, "credit": Decimal("0.00")}
        )

    if bill.tax_total > 0:
        je_lines.append(
            {"account_id": gst_input.id, "debit": bill.tax_total, "credit": Decimal("0.00")}
        )

    je_lines.append(
        {"account_id": ap.id, "debit": Decimal("0.00"), "credit": bill.total}
    )

    entry = create_journal_entry(
        session,
        date=bill.date,
        memo=f"Bill {bill.number}",
        source_type=JournalSourceType.BILL,
        source_id=bill.id,
        lines_data=je_lines,
    )
    bill.status = BillStatus.POSTED
    bill.journal_entry_id = entry.id
    session.flush()
    return bill


def void_bill(session: Session, bill: Bill) -> Bill:
    if bill.status in (BillStatus.DRAFT, BillStatus.VOID):
        raise InvalidStateTransition(
            f"Cannot void bill {bill.number}: status is {bill.status.value}"
        )

    from app.models import PaymentMadeAllocation, DebitNoteAllocation

    pmt_alloc = session.scalar(
        select(PaymentMadeAllocation.id).where(
            PaymentMadeAllocation.bill_id == bill.id
        ).limit(1)
    )
    dn_alloc = session.scalar(
        select(DebitNoteAllocation.id).where(
            DebitNoteAllocation.bill_id == bill.id
        ).limit(1)
    )
    if pmt_alloc is not None or dn_alloc is not None:
        raise PostingError(f"Cannot void bill {bill.number}: it has allocations")

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, bill.journal_entry_id)
    create_reversing_entry(
        session, original_entry, memo=f"Void Bill {bill.number}"
    )
    bill.status = BillStatus.VOID
    session.flush()
    return bill
