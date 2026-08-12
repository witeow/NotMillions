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
from app.models.supplier import Supplier


class DebitNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOID = "VOID"


class DebitNote(TimestampMixin, Base):
    """Reduces what is owed to a supplier (purchase returns, overbilling)."""

    __tablename__ = "debit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[DebitNoteStatus] = mapped_column(
        Enum(DebitNoteStatus, native_enum=False, length=20),
        default=DebitNoteStatus.DRAFT,
    )
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    supplier: Mapped[Supplier] = relationship()
    lines: Mapped[list["DebitNoteLine"]] = relationship(
        back_populates="debit_note",
        cascade="all, delete-orphan",
        order_by="DebitNoteLine.line_no",
    )
    allocations: Mapped[list["DebitNoteAllocation"]] = relationship(
        back_populates="debit_note", cascade="all, delete-orphan"
    )


class DebitNoteLine(Base):
    __tablename__ = "debit_note_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    debit_note_id: Mapped[int] = mapped_column(
        ForeignKey("debit_notes.id", ondelete="CASCADE")
    )
    line_no: Mapped[int]
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE, default=Decimal("0"))
    tax_code_id: Mapped[int | None] = mapped_column(ForeignKey("tax_codes.id"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    expense_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))

    debit_note: Mapped[DebitNote] = relationship(back_populates="lines")


class DebitNoteAllocation(Base):
    """Applies a debit note against a specific bill's outstanding balance."""

    __tablename__ = "debit_note_allocations"
    __table_args__ = (
        UniqueConstraint("debit_note_id", "bill_id"),
        CheckConstraint("amount > 0", name="positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    debit_note_id: Mapped[int] = mapped_column(
        ForeignKey("debit_notes.id", ondelete="CASCADE")
    )
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    debit_note: Mapped[DebitNote] = relationship(back_populates="allocations")
