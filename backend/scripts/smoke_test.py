"""End-to-end schema smoke test against the dev database.

Creates a customer, an item, and a draft invoice with an SR and a ZR line,
computes totals the way the posting service will, then posts a balanced
journal entry — proving the schema supports the invoice posting rules.

Run with:  python scripts/smoke_test.py   (after `pip install -e .`)
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import (
    Account,
    Customer,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Item,
    JournalEntry,
    JournalLine,
    JournalSourceType,
    TaxCode,
    next_document_number,
)

CENT = Decimal("0.01")


def line_amounts(qty: Decimal, unit_price: Decimal, rate: Decimal):
    subtotal = (qty * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
    tax = (subtotal * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return subtotal, tax


def main() -> None:
    with SessionLocal() as session:
        sr = session.scalar(select(TaxCode).where(TaxCode.code == "SR"))
        zr = session.scalar(select(TaxCode).where(TaxCode.code == "ZR"))
        ar = session.scalar(select(Account).where(Account.code == "1200"))
        gst_output = session.scalar(select(Account).where(Account.code == "2100"))
        sales = session.scalar(select(Account).where(Account.code == "4000"))
        assert sr and zr and ar and gst_output and sales, "Run app.seed first"

        invoice_number = next_document_number(session, "INVOICE")
        customer = Customer(
            code=f"CUST-{invoice_number[-4:]}", name="Ah Huat Trading Pte Ltd"
        )
        item = Item(
            code=f"ITEM-{invoice_number[-4:]}",
            description="Consulting services",
            unit_price=Decimal("150.0000"),
            default_tax_code_id=sr.id,
            income_account_id=sales.id,
        )
        session.add_all([customer, item])
        session.flush()

        qty1, price1 = Decimal("10"), Decimal("150.0000")
        sub1, tax1 = line_amounts(qty1, price1, sr.rate)
        qty2, price2 = Decimal("2"), Decimal("80.0000")
        sub2, tax2 = line_amounts(qty2, price2, zr.rate)

        subtotal = sub1 + sub2
        tax_total = tax1 + tax2
        total = subtotal + tax_total

        invoice = Invoice(
            number=invoice_number,
            customer_id=customer.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=InvoiceStatus.POSTED,
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            lines=[
                InvoiceLine(
                    line_no=1, item_id=item.id, description=item.description,
                    qty=qty1, unit_price=price1, tax_code_id=sr.id,
                    tax_amount=tax1, line_total=sub1 + tax1,
                    income_account_id=sales.id,
                ),
                InvoiceLine(
                    line_no=2, description="Reimbursable disbursements",
                    qty=qty2, unit_price=price2, tax_code_id=zr.id,
                    tax_amount=tax2, line_total=sub2 + tax2,
                    income_account_id=sales.id,
                ),
            ],
        )
        session.add(invoice)
        session.flush()

        # Posting rule: DR AR (total) / CR income per line / CR GST output
        entry = JournalEntry(
            entry_no=next_document_number(session, "JOURNAL"),
            date=invoice.date,
            memo=f"Invoice {invoice.number}",
            source_type=JournalSourceType.INVOICE,
            source_id=invoice.id,
            lines=[
                JournalLine(account_id=ar.id, debit=total),
                JournalLine(account_id=sales.id, credit=subtotal),
                JournalLine(account_id=gst_output.id, credit=tax_total),
            ],
        )
        session.add(entry)
        session.flush()
        invoice.journal_entry_id = entry.id

        debits = sum(l.debit for l in entry.lines)
        credits = sum(l.credit for l in entry.lines)
        assert debits == credits == total, f"Unbalanced: DR {debits} != CR {credits}"
        assert subtotal == Decimal("1660.00"), subtotal
        assert tax_total == Decimal("135.00"), tax_total  # 9% of 1500 only
        assert total == Decimal("1795.00"), total

        session.commit()
        print(f"OK: {invoice.number} total={total} posted as {entry.entry_no} "
              f"(DR {debits} = CR {credits})")


if __name__ == "__main__":
    main()
