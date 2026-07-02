import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import MONEY, QUANTITY, UNIT_PRICE, TimestampMixin
from app.models.customer import Customer


class CreditNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOID = "VOID"


class CreditNote(TimestampMixin, Base):
    """Reduces what a customer owes (returns, overbilling corrections)."""

    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus, native_enum=False, length=20),
        default=CreditNoteStatus.DRAFT,
    )
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    customer: Mapped[Customer] = relationship()
    lines: Mapped[list["CreditNoteLine"]] = relationship(
        back_populates="credit_note",
        cascade="all, delete-orphan",
        order_by="CreditNoteLine.line_no",
    )
    allocations: Mapped[list["CreditNoteAllocation"]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan"
    )


class CreditNoteLine(Base):
    __tablename__ = "credit_note_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="CASCADE")
    )
    line_no: Mapped[int]
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE, default=Decimal("0"))
    tax_code_id: Mapped[int | None] = mapped_column(ForeignKey("tax_codes.id"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    # Revenue account this line debits back when posted.
    income_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))

    credit_note: Mapped[CreditNote] = relationship(back_populates="lines")


class CreditNoteAllocation(Base):
    """Applies a credit note against a specific invoice's outstanding balance."""

    __tablename__ = "credit_note_allocations"
    __table_args__ = (
        UniqueConstraint("credit_note_id", "invoice_id"),
        CheckConstraint("amount > 0", name="positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="CASCADE")
    )
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    credit_note: Mapped[CreditNote] = relationship(back_populates="allocations")
