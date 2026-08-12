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
from app.models.payment import PaymentMethod
from app.models.supplier import Supplier


class PaymentMadeStatus(str, enum.Enum):
    POSTED = "POSTED"
    VOID = "VOID"


class PaymentMade(TimestampMixin, Base):
    """Money paid to a supplier, allocated against one or more bills."""

    __tablename__ = "payments_made"
    __table_args__ = (CheckConstraint("amount > 0", name="positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20)
    )
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PaymentMadeStatus] = mapped_column(
        Enum(PaymentMadeStatus, native_enum=False, length=20),
        default=PaymentMadeStatus.POSTED,
    )
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    supplier: Mapped[Supplier] = relationship()
    allocations: Mapped[list["PaymentMadeAllocation"]] = relationship(
        back_populates="payment_made", cascade="all, delete-orphan"
    )


class PaymentMadeAllocation(Base):
    """How much of a payment settles a given bill."""

    __tablename__ = "payment_made_allocations"
    __table_args__ = (
        UniqueConstraint("payment_made_id", "bill_id"),
        CheckConstraint("amount > 0", name="positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_made_id: Mapped[int] = mapped_column(
        ForeignKey("payments_made.id", ondelete="CASCADE")
    )
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    payment_made: Mapped[PaymentMade] = relationship(back_populates="allocations")
