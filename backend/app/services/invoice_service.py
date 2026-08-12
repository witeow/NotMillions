from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
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


def create_invoice(
    session: Session,
    *,
    customer_id: int,
    invoice_date: date,
    due_date: date,
    lines_data: list[dict],
    notes: str | None = None,
) -> Invoice:
    number = next_document_number(session, "INVOICE")
    lines = []
    for i, ld in enumerate(lines_data, 1):
        tax_code = session.get(TaxCode, ld["tax_code_id"]) if ld.get("tax_code_id") else None
        rate = tax_code.rate if tax_code else Decimal("0.00")
        subtotal, tax_amount, line_total = compute_line_total(
            ld.get("qty", Decimal("1")), ld["unit_price"], rate
        )
        lines.append(
            InvoiceLine(
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

    invoice = Invoice(
        number=number,
        customer_id=customer_id,
        date=invoice_date,
        due_date=due_date,
        status=InvoiceStatus.DRAFT,
        subtotal=doc_subtotal,
        tax_total=doc_tax,
        total=doc_subtotal + doc_tax,
        notes=notes,
        lines=lines,
    )
    session.add(invoice)
    session.flush()
    return invoice


def post_invoice(session: Session, invoice: Invoice) -> Invoice:
    if invoice.status != InvoiceStatus.DRAFT:
        raise InvalidStateTransition(
            f"Cannot post invoice {invoice.number}: status is {invoice.status.value}"
        )

    ar = get_account(session, "1200")
    gst_output = get_account(session, "2100")

    je_lines = [
        {"account_id": ar.id, "debit": invoice.total, "credit": Decimal("0.00")},
    ]
    income_totals: dict[int, Decimal] = {}
    for ln in invoice.lines:
        acct_id = ln.income_account_id
        if acct_id is None:
            raise PostingError(
                f"Invoice line {ln.line_no} has no income account"
            )
        subtotal = ln.line_total - ln.tax_amount
        income_totals[acct_id] = income_totals.get(acct_id, Decimal("0.00")) + subtotal

    for acct_id, amount in income_totals.items():
        je_lines.append(
            {"account_id": acct_id, "debit": Decimal("0.00"), "credit": amount}
        )

    if invoice.tax_total > 0:
        je_lines.append(
            {"account_id": gst_output.id, "debit": Decimal("0.00"), "credit": invoice.tax_total}
        )

    entry = create_journal_entry(
        session,
        date=invoice.date,
        memo=f"Invoice {invoice.number}",
        source_type=JournalSourceType.INVOICE,
        source_id=invoice.id,
        lines_data=je_lines,
    )
    invoice.status = InvoiceStatus.POSTED
    invoice.journal_entry_id = entry.id
    session.flush()
    return invoice


def void_invoice(session: Session, invoice: Invoice) -> Invoice:
    if invoice.status in (InvoiceStatus.DRAFT, InvoiceStatus.VOID):
        raise InvalidStateTransition(
            f"Cannot void invoice {invoice.number}: status is {invoice.status.value}"
        )

    from app.models import PaymentAllocation, CreditNoteAllocation

    alloc_count = session.scalar(
        select(PaymentAllocation.id).where(
            PaymentAllocation.invoice_id == invoice.id
        ).limit(1)
    )
    cn_count = session.scalar(
        select(CreditNoteAllocation.id).where(
            CreditNoteAllocation.invoice_id == invoice.id
        ).limit(1)
    )
    if alloc_count is not None or cn_count is not None:
        raise PostingError(
            f"Cannot void invoice {invoice.number}: it has allocations"
        )

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, invoice.journal_entry_id)
    create_reversing_entry(
        session, original_entry, memo=f"Void Invoice {invoice.number}"
    )
    invoice.status = InvoiceStatus.VOID
    session.flush()
    return invoice
