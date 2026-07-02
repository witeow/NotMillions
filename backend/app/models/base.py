from datetime import datetime

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

# Column type conventions:
# - Money amounts are exact to the cent (SGD).
# - Unit prices carry extra precision; rounding to cents happens per line.
MONEY = Numeric(12, 2)
UNIT_PRICE = Numeric(12, 4)
QUANTITY = Numeric(12, 3)
TAX_RATE = Numeric(5, 2)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
