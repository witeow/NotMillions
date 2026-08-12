from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CreditNoteAllocation,
    Invoice,
    InvoiceStatus,
    JournalSourceType,
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentStatus,
    next_document_number,
)
from app.services.shared import (
    AllocationError,
    InvalidStateTransition,
    create_journal_entry,
    get_account,
)


def compute_invoice_outstanding(session: Session, invoice: Invoice) -> Decimal:
    paid = session.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.invoice_id == invoice.id,
            PaymentAllocation.payment_id.in_(
                select(Payment.id).where(Payment.status == PaymentStatus.POSTED)
            ),
        )
    ) or Decimal("0.00")
    credited = session.scalar(
        select(func.coalesce(func.sum(CreditNoteAllocation.amount), 0)).where(
            CreditNoteAllocation.invoice_id == invoice.id,
        )
    ) or Decimal("0.00")
    return invoice.total - Decimal(str(paid)) - Decimal(str(credited))


def _update_invoice_status(session: Session, invoice: Invoice) -> None:
    outstanding = compute_invoice_outstanding(session, invoice)
    if outstanding <= 0:
        invoice.status = InvoiceStatus.PAID
    elif outstanding < invoice.total:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    else:
        invoice.status = InvoiceStatus.POSTED


def create_payment(
    session: Session,
    *,
    customer_id: int,
    payment_date: date,
    method: PaymentMethod,
    bank_account_id: int,
    amount: Decimal,
    allocations: list[dict] | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> Payment:
    if amount <= 0:
        raise AllocationError("Payment amount must be positive")

    alloc_total = Decimal("0.00")
    if allocations:
        for alloc in allocations:
            invoice = session.get(Invoice, alloc["invoice_id"])
            if invoice is None:
                raise AllocationError(f"Invoice {alloc['invoice_id']} not found")
            if invoice.customer_id != customer_id:
                raise AllocationError(
                    f"Invoice {invoice.number} belongs to a different customer"
                )
            if invoice.status not in (
                InvoiceStatus.POSTED,
                InvoiceStatus.PARTIALLY_PAID,
            ):
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
            alloc_total += alloc["amount"]

    if alloc_total > amount:
        raise AllocationError(
            f"Total allocations {alloc_total} exceed payment amount {amount}"
        )

    ar = get_account(session, "1200")
    number = next_document_number(session, "PAYMENT")

    entry = create_journal_entry(
        session,
        date=payment_date,
        memo=f"Payment {number}",
        source_type=JournalSourceType.PAYMENT,
        source_id=None,
        lines_data=[
            {"account_id": bank_account_id, "debit": amount, "credit": Decimal("0.00")},
            {"account_id": ar.id, "debit": Decimal("0.00"), "credit": amount},
        ],
    )

    payment = Payment(
        number=number,
        customer_id=customer_id,
        date=payment_date,
        method=method,
        bank_account_id=bank_account_id,
        amount=amount,
        reference=reference,
        notes=notes,
        status=PaymentStatus.POSTED,
        journal_entry_id=entry.id,
    )
    session.add(payment)
    session.flush()
    entry.source_id = payment.id

    if allocations:
        for alloc in allocations:
            payment.allocations.append(
                PaymentAllocation(
                    invoice_id=alloc["invoice_id"], amount=alloc["amount"]
                )
            )
        session.flush()
        for alloc in allocations:
            invoice = session.get(Invoice, alloc["invoice_id"])
            _update_invoice_status(session, invoice)

    session.flush()
    return payment


def void_payment(session: Session, payment: Payment) -> Payment:
    if payment.status != PaymentStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot void payment {payment.number}: status is {payment.status.value}"
        )

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, payment.journal_entry_id)
    from app.services.shared import create_reversing_entry

    create_reversing_entry(
        session, original_entry, memo=f"Void Payment {payment.number}"
    )

    invoice_ids = [a.invoice_id for a in payment.allocations]
    payment.allocations.clear()
    payment.status = PaymentStatus.VOID
    session.flush()

    for inv_id in invoice_ids:
        invoice = session.get(Invoice, inv_id)
        _update_invoice_status(session, invoice)

    session.flush()
    return payment
