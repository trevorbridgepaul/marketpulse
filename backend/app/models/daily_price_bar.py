from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.security import Security


class DailyPriceBar(Base):
    __tablename__ = "daily_price_bars"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "session_date", name="uq_daily_price_bars_security_session"
        ),
        CheckConstraint("open > 0", name="ck_daily_price_bars_open_positive"),
        CheckConstraint("high > 0", name="ck_daily_price_bars_high_positive"),
        CheckConstraint("low > 0", name="ck_daily_price_bars_low_positive"),
        CheckConstraint("close > 0", name="ck_daily_price_bars_close_positive"),
        CheckConstraint("volume >= 0", name="ck_daily_price_bars_volume_nonnegative"),
        CheckConstraint(
            "high >= open AND high >= low AND high >= close",
            name="ck_daily_price_bars_high_is_max",
        ),
        CheckConstraint(
            "low <= open AND low <= high AND low <= close",
            name="ck_daily_price_bars_low_is_min",
        ),
        CheckConstraint(
            "data_provider = 'alpaca'", name="ck_daily_price_bars_data_provider_alpaca"
        ),
        CheckConstraint("feed = 'iex'", name="ck_daily_price_bars_feed_iex"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), nullable=False
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data_provider: Mapped[str] = mapped_column(Text, nullable=False)
    feed: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    security: Mapped["Security"] = relationship(back_populates="daily_price_bars")
