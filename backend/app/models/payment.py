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
from app.models.base import MONEY, TimestampMixin
from app.models.customer import Customer


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    PAYNOW = "PAYNOW"
    CARD = "CARD"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    POSTED = "POSTED"
    VOID = "VOID"


class Payment(TimestampMixin, Base):
    """Money received from a customer, allocated against one or more invoices."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20)
    )
    # Cash/bank asset account the money lands in (debited on posting).
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=20), default=PaymentStatus.POSTED
    )
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    customer: Mapped[Customer] = relationship()
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class PaymentAllocation(Base):
    """How much of a payment settles a given invoice. Unallocated remainder is
    on-account customer credit."""

    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id"),
        CheckConstraint("amount > 0", name="positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE")
    )
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    payment: Mapped[Payment] = relationship(back_populates="allocations")
