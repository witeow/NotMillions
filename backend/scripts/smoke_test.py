"""End-to-end smoke test against the dev database.

AR side: creates a customer, draft invoice with SR + ZR lines, posts it,
verifies the journal entry balances, receives a payment.

AP side: creates a supplier, a bill with TX tax code, posts it, verifies
the journal entry, makes a payment.

Run with:  python scripts/smoke_test.py   (after `uv sync` + seed)
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import (
    Account,
    BillStatus,
    Customer,
    InvoiceStatus,
    JournalEntry,
    PaymentMethod,
    Supplier,
    TaxCode,
    next_document_number,
)
from app.services.bill_service import create_bill, post_bill
from app.services.invoice_service import create_invoice, post_invoice
from app.services.payment_made_service import create_payment_made
from app.services.payment_service import create_payment


def main() -> None:
    with SessionLocal() as session:
        sr = session.scalar(select(TaxCode).where(TaxCode.code == "SR"))
        zr = session.scalar(select(TaxCode).where(TaxCode.code == "ZR"))
        tx = session.scalar(select(TaxCode).where(TaxCode.code == "TX"))
        ar = session.scalar(select(Account).where(Account.code == "1200"))
        ap = session.scalar(select(Account).where(Account.code == "2000"))
        sales = session.scalar(select(Account).where(Account.code == "4000"))
        bank = session.scalar(select(Account).where(Account.code == "1100"))
        materials = session.scalar(select(Account).where(Account.code == "5000"))
        assert all([sr, zr, tx, ar, ap, sales, bank, materials]), "Run app.seed first"

        # Use sequence-derived codes so the smoke test is re-runnable
        seq_num = next_document_number(session, "INVOICE")[-4:]

        # --- AR: Invoice + Payment ---
        customer = Customer(code=f"CUST-{seq_num}", name="Ah Huat Trading")
        session.add(customer)
        session.flush()

        inv = create_invoice(
            session,
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[
                {
                    "description": "Consulting services",
                    "qty": Decimal("10"),
                    "unit_price": Decimal("150.0000"),
                    "tax_code_id": sr.id,
                    "income_account_id": sales.id,
                },
                {
                    "description": "Reimbursable disbursements",
                    "qty": Decimal("2"),
                    "unit_price": Decimal("80.0000"),
                    "tax_code_id": zr.id,
                    "income_account_id": sales.id,
                },
            ],
        )
        assert inv.subtotal == Decimal("1660.00")
        assert inv.tax_total == Decimal("135.00")
        assert inv.total == Decimal("1795.00")

        post_invoice(session, inv)
        assert inv.status == InvoiceStatus.POSTED

        entry = session.get(JournalEntry, inv.journal_entry_id)
        debits = sum(l.debit for l in entry.lines)
        credits = sum(l.credit for l in entry.lines)
        assert debits == credits == inv.total, f"AR JE unbalanced: DR {debits} != CR {credits}"

        pmt = create_payment(
            session,
            customer_id=customer.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank.id,
            amount=inv.total,
            allocations=[{"invoice_id": inv.id, "amount": inv.total}],
            reference="PayNow ref 001",
        )
        assert inv.status == InvoiceStatus.PAID

        print(f"AR OK: {inv.number} total={inv.total} -> {pmt.number} (PAID)")

        # --- AP: Bill + Payment Made ---
        supplier = Supplier(code=f"SUP-{seq_num}", name="Cement Supplier")
        session.add(supplier)
        session.flush()

        bill = create_bill(
            session,
            supplier_id=supplier.id,
            bill_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            lines_data=[
                {
                    "description": "Portland cement 50kg bags",
                    "qty": Decimal("100"),
                    "unit_price": Decimal("5.0000"),
                    "tax_code_id": tx.id,
                    "expense_account_id": materials.id,
                },
            ],
        )
        assert bill.subtotal == Decimal("500.00")
        assert bill.tax_total == Decimal("45.00")
        assert bill.total == Decimal("545.00")

        post_bill(session, bill)
        assert bill.status == BillStatus.POSTED

        entry = session.get(JournalEntry, bill.journal_entry_id)
        debits = sum(l.debit for l in entry.lines)
        credits = sum(l.credit for l in entry.lines)
        assert debits == credits == bill.total, f"AP JE unbalanced: DR {debits} != CR {credits}"

        pmt_made = create_payment_made(
            session,
            supplier_id=supplier.id,
            payment_date=date.today(),
            method=PaymentMethod.PAYNOW,
            bank_account_id=bank.id,
            amount=bill.total,
            allocations=[{"bill_id": bill.id, "amount": bill.total}],
            reference="PayNow ref 002",
        )
        assert bill.status == BillStatus.PAID

        print(f"AP OK: {bill.number} total={bill.total} -> {pmt_made.number} (PAID)")

        session.commit()
        print("Smoke test passed.")


if __name__ == "__main__":
    main()
