import datetime
import enum
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import MONEY, QUANTITY, UNIT_PRICE, TimestampMixin
from app.models.customer import Customer


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    VOID = "VOID"


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    due_date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, length=20), default=InvoiceStatus.DRAFT
    )
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text)
    # Set when the invoice is posted to the GL. Paid/outstanding balances are
    # computed from payment/credit-note allocations, never stored here.
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    customer: Mapped[Customer] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.line_no",
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE")
    )
    line_no: Mapped[int]
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE, default=Decimal("0"))
    tax_code_id: Mapped[int | None] = mapped_column(ForeignKey("tax_codes.id"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    # Revenue account this line credits when posted; defaulted from the item.
    income_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
