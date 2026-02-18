from datetime import date, datetime

from pydantic import BaseModel


class RateData(BaseModel):
    currency_code: str
    base_currency: str = "KRW"
    rate: float
    cash_buy_rate: float | None = None
    cash_sell_rate: float | None = None
    tt_buy_rate: float | None = None
    tt_sell_rate: float | None = None
    spread: float | None = None
    source: str
    fetched_at: datetime
    rate_date: date


class RateResponse(BaseModel):
    currency_code: str
    currency_name: str
    base_currency: str = "KRW"
    rate: float
    tt_buy_rate: float | None = None
    tt_sell_rate: float | None = None
    spread: float | None = None
    cash_buy_rate: float | None = None
    cash_sell_rate: float | None = None
    source: str
    updated_at: datetime


class HistoricalRateResponse(BaseModel):
    currency_code: str
    rates: list[dict]  # [{date, rate}]
    period_days: int


class TimingResponse(BaseModel):
    currency_code: str
    recommendation: str  # BUY, HOLD, WAIT
    confidence: float
    current_rate: float
    signals: dict
    percentile_90d: float
    ma_short: float
    ma_long: float
    updated_at: datetime
