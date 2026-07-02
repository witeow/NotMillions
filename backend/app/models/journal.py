import datetime
import enum
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import MONEY, TimestampMixin


class JournalSourceType(str, enum.Enum):
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    CREDIT_NOTE = "CREDIT_NOTE"
    MANUAL = "MANUAL"


class JournalEntry(TimestampMixin, Base):
    """A balanced double-entry posting. Never deleted — voiding a document
    creates a reversing entry instead."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    memo: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType, native_enum=False, length=20)
    )
    source_id: Mapped[int | None]

    # No delete cascade on purpose: journal entries are never deleted, so any
    # deletion attempt should fail loudly on the FK instead of quietly working.
    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry")


class JournalLine(Base):
    __tablename__ = "journal_lines"
    # Debits must equal credits per entry — enforced in the service layer;
    # the DB only guarantees each line is single-sided and non-negative.
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="non_negative"),
        CheckConstraint("NOT (debit <> 0 AND credit <> 0)", name="single_sided"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    journal_entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    description: Mapped[str | None] = mapped_column(Text)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")
