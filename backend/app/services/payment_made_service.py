from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Bill,
    BillStatus,
    DebitNoteAllocation,
    JournalSourceType,
    PaymentMade,
    PaymentMadeAllocation,
    PaymentMadeStatus,
    PaymentMethod,
    next_document_number,
)
from app.services.shared import (
    AllocationError,
    InvalidStateTransition,
    create_journal_entry,
    create_reversing_entry,
    get_account,
)


def compute_bill_outstanding(session: Session, bill: Bill) -> Decimal:
    paid = session.scalar(
        select(func.coalesce(func.sum(PaymentMadeAllocation.amount), 0)).where(
            PaymentMadeAllocation.bill_id == bill.id,
            PaymentMadeAllocation.payment_made_id.in_(
                select(PaymentMade.id).where(PaymentMade.status == PaymentMadeStatus.POSTED)
            ),
        )
    ) or Decimal("0.00")
    credited = session.scalar(
        select(func.coalesce(func.sum(DebitNoteAllocation.amount), 0)).where(
            DebitNoteAllocation.bill_id == bill.id,
        )
    ) or Decimal("0.00")
    return bill.total - Decimal(str(paid)) - Decimal(str(credited))


def _update_bill_status(session: Session, bill: Bill) -> None:
    outstanding = compute_bill_outstanding(session, bill)
    if outstanding <= 0:
        bill.status = BillStatus.PAID
    elif outstanding < bill.total:
        bill.status = BillStatus.PARTIALLY_PAID
    else:
        bill.status = BillStatus.POSTED


def create_payment_made(
    session: Session,
    *,
    supplier_id: int,
    payment_date: date,
    method: PaymentMethod,
    bank_account_id: int,
    amount: Decimal,
    allocations: list[dict] | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> PaymentMade:
    if amount <= 0:
        raise AllocationError("Payment amount must be positive")

    alloc_total = Decimal("0.00")
    if allocations:
        for alloc in allocations:
            bill = session.get(Bill, alloc["bill_id"])
            if bill is None:
                raise AllocationError(f"Bill {alloc['bill_id']} not found")
            if bill.supplier_id != supplier_id:
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
            alloc_total += alloc["amount"]

    if alloc_total > amount:
        raise AllocationError(
            f"Total allocations {alloc_total} exceed payment amount {amount}"
        )

    ap = get_account(session, "2000")
    number = next_document_number(session, "PAYMENT_MADE")

    entry = create_journal_entry(
        session,
        date=payment_date,
        memo=f"Payment Made {number}",
        source_type=JournalSourceType.PAYMENT_MADE,
        source_id=None,
        lines_data=[
            {"account_id": ap.id, "debit": amount, "credit": Decimal("0.00")},
            {"account_id": bank_account_id, "debit": Decimal("0.00"), "credit": amount},
        ],
    )

    pmt = PaymentMade(
        number=number,
        supplier_id=supplier_id,
        date=payment_date,
        method=method,
        bank_account_id=bank_account_id,
        amount=amount,
        reference=reference,
        notes=notes,
        status=PaymentMadeStatus.POSTED,
        journal_entry_id=entry.id,
    )
    session.add(pmt)
    session.flush()
    entry.source_id = pmt.id

    if allocations:
        for alloc in allocations:
            pmt.allocations.append(
                PaymentMadeAllocation(
                    bill_id=alloc["bill_id"], amount=alloc["amount"]
                )
            )
        session.flush()
        for alloc in allocations:
            bill = session.get(Bill, alloc["bill_id"])
            _update_bill_status(session, bill)

    session.flush()
    return pmt


def void_payment_made(session: Session, pmt: PaymentMade) -> PaymentMade:
    if pmt.status != PaymentMadeStatus.POSTED:
        raise InvalidStateTransition(
            f"Cannot void payment {pmt.number}: status is {pmt.status.value}"
        )

    from app.models import JournalEntry

    original_entry = session.get(JournalEntry, pmt.journal_entry_id)
    create_reversing_entry(
        session, original_entry, memo=f"Void Payment Made {pmt.number}"
    )

    bill_ids = [a.bill_id for a in pmt.allocations]
    pmt.allocations.clear()
    pmt.status = PaymentMadeStatus.VOID
    session.flush()

    for bill_id in bill_ids:
        bill = session.get(Bill, bill_id)
        _update_bill_status(session, bill)

    session.flush()
    return pmt
