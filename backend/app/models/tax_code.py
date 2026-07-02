from decimal import Decimal

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TAX_RATE, TimestampMixin


class TaxCode(TimestampMixin, Base):
    """GST treatment for a line: SR (standard-rated), ZR (zero-rated), ES (exempt)."""

    __tablename__ = "tax_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    rate: Mapped[Decimal] = mapped_column(TAX_RATE, default=Decimal("0.00"))
    # Where the collected tax posts (GST Output Tax); null for non-taxable codes.
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
