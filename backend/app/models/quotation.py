import datetime
import enum
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import MONEY, QUANTITY, UNIT_PRICE, TimestampMixin
from app.models.customer import Customer


class QuotationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CONVERTED = "CONVERTED"


class Quotation(TimestampMixin, Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    # NB: annotate dates as datetime.date — the `date` column attribute shadows
    # a bare `date` name in this class namespace and breaks Optional inference.
    date: Mapped[datetime.date] = mapped_column(Date)
    valid_until: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus, native_enum=False, length=20),
        default=QuotationStatus.DRAFT,
    )
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text)
    converted_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))

    customer: Mapped[Customer] = relationship()
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationLine.line_no",
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE")
    )
    line_no: Mapped[int]
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE, default=Decimal("0"))
    tax_code_id: Mapped[int | None] = mapped_column(ForeignKey("tax_codes.id"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    quotation: Mapped[Quotation] = relationship(back_populates="lines")
