from decimal import Decimal

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UNIT_PRICE, TimestampMixin


class Item(TimestampMixin, Base):
    """Catalog of products/services for fast repeat billing. No stock tracking."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE, default=Decimal("0"))
    uom: Mapped[str] = mapped_column(String(20), default="unit")
    default_tax_code_id: Mapped[int | None] = mapped_column(ForeignKey("tax_codes.id"))
    income_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    expense_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
