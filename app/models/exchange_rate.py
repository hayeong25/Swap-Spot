from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(10), default="KRW")
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    cash_buy_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_sell_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tt_buy_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tt_sell_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_rate_currency_date", "currency_code", "rate_date"),
        Index("idx_rate_fetched", "fetched_at"),
    )
