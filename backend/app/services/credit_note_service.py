from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CreditNote,
    CreditNoteAllocation,
    CreditNoteLine,
    CreditNoteStatus,
    Invoice,
    InvoiceStatus,
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


def create_credit_note(
    session: Session,
    *,
    customer_id: int,
    cn_date: date,
    lines_data: list[dict],
    notes: str | None = None,
) -> CreditNote:
    number = next_document_number(session, "CREDIT_NOTE")
    lines = []
    for i, ld in enumerate(lines_data, 1):
        tax_code = session.get(TaxCode, ld["tax_code_id"]) if ld.get("tax_code_id") else None
        rate = tax_code.rate if tax_code else Decimal("0.00")
        subtotal, tax_amount, line_total = compute_line_total(
            ld.get("qty", Decimal("1")), ld["unit_price"], rate
        )
        lines.append(
            CreditNoteLine(
                line_no=i,
                item_id=ld.get("item_id"),
                description=ld["description"],
                qty=ld.get("qty", Decimal("1")),
                unit_price=ld["unit_price"],
                tax_code_id=ld.get("tax_code_id"),
                tax_amount=tax_amount,
                line_total=line_total,
                income_account_id=ld.get("income_account_id"),
            )
        )

    doc_subtotal = sum(ln.line_total - ln.tax_amount for ln in lines)
    doc_tax = sum(ln.tax_amount for ln in lines)

    cn = CreditNote(
        number=number,
        customer_id=customer_id,
        date=cn_date,
        status=CreditNoteStatus.DRAFT,
        subtotal=doc_subtotal,
        tax_total=doc_tax,
        total=doc_subtotal + doc_tax,
        notes=notes,
        lines=lines,
    )
    session.add(cn)
    session.flush()
    return cn


def post_credit_note(session: Session, cn: CreditNote) -> CreditNote:
    if cn.status != CreditNoteStatus.DRAFT:
        raise InvalidStateTransition(
            f"Cannot post credit note {cn.number}: status is {cn.status.value}"
        )

    ar = get_account(session, "1200")
    gst_output = get_account(session, "2100")

    je_lines = []
    income_totals: dict[int, Decimal] = {}
    for ln in cn.lines:
        acct_id = ln.income_account_id
        if acct_id is None:
            raise PostingError(f"Credit note line {ln.line_no} has no income account")
        subtotal = ln.line_total - ln.tax_amount
        income_totals[acct_id] = income_totals.get(acct_id, Decimal("0.00")) + subtotal

    for acct_id, amount in income_totals.items():
        je_lines.append(
            {"account_id": acct_id, "debit": amount, "credit": Decimal("0.00")}
        )

    if cn.tax_total > 0:
        je_lines.append(
            {"account_id": gst_output.id, "debit": cn.tax_total, "credit": Decimal("0.00")}
        )

    je_lines.append(
        {"account_id": ar.id, "debit": Decimal("0.00"), "credit": cn.total}
    )

    entry = create_journal_entry(
        session,
        date=cn.date,
        memo=f"Credit Note {cn.number}",
        source_type=JournalSourceType.CREDIT_NOTE,
        source_id=cn.id,
        lines_data=je_lines,
    )
    cn.status = CreditNoteStatus.POSTED
    cn.journal_entry_id = entry.id
    session.flush()
    return cn


def allocate_credit_note(
    session: Session,
    cn: CreditNote,
    allocations: list[dict],
) -> CreditNote:
    if cn.status != CreditNoteStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot allocate credit note {cn.number}: status is {cn.status.value}"
        )

    from app.services.payment_service import (
        _update_invoice_status,
        compute_invoice_outstanding,
    )

    existing_allocated = sum(a.amount for a in cn.allocations)
    new_total = sum(a["amount"] for a in allocations)
    if existing_allocated + new_total > cn.total:
        raise AllocationError(
            f"Allocations ({existing_allocated + new_total}) exceed "
            f"credit note total ({cn.total})"
        )

    for alloc in allocations:
        invoice = session.get(Invoice, alloc["invoice_id"])
        if invoice is None:
            raise AllocationError(f"Invoice {alloc['invoice_id']} not found")
        if invoice.customer_id != cn.customer_id:
            raise AllocationError(
                f"Invoice {invoice.number} belongs to a different customer"
            )
        if invoice.status not in (InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID):
            raise AllocationError(
                f"Cannot allocate against invoice {invoice.number}: "
                f"status is {invoice.status.value}"
            )
        outstanding = compute_invoice_outstanding(session, invoice)
        if alloc["amount"] > outstanding:
            raise AllocationError(
                f"Allocation {alloc['amount']} exceeds outstanding "
                f"{outstanding} on invoice {invoice.number}"
            )

        cn.allocations.append(
            CreditNoteAllocation(
                invoice_id=alloc["invoice_id"], amount=alloc["amount"]
            )
        )

    session.flush()
    for alloc in allocations:
        invoice = session.get(Invoice, alloc["invoice_id"])
        _update_invoice_status(session, invoice)
    session.flush()
    return cn


def void_credit_note(session: Session, cn: CreditNote) -> CreditNote:
    if cn.status != CreditNoteStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot void credit note {cn.number}: status is {cn.status.value}"
        )

    if cn.allocations:
        raise PostingError(
            f"Cannot void credit note {cn.number}: it has allocations"
        )

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, cn.journal_entry_id)
    create_reversing_entry(
        session, original_entry, memo=f"Void Credit Note {cn.number}"
    )
    cn.status = CreditNoteStatus.VOID
    session.flush()
    return cn
