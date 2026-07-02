from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin


class CompanySettings(TimestampMixin, Base):
    """Single-row table holding the business's own details (appears on documents)."""

    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("fy_start_month BETWEEN 1 AND 12", name="fy_month_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    uen: Mapped[str | None] = mapped_column(String(20))
    gst_reg_no: Mapped[str | None] = mapped_column(String(20))
    fy_start_month: Mapped[int] = mapped_column(default=1)
