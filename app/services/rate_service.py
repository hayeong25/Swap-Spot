import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.exchange_rate import ExchangeRate
from app.schemas.rate import RateData
from app.sources.aggregator import RateAggregator

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


@dataclass
class RateCache:
    latest: dict[str, RateData] = field(default_factory=dict)
    updated_at: datetime | None = None

    def update(self, currency: str, rate: RateData):
        self.latest[currency] = rate
        self.updated_at = datetime.now(KST)

    def get_all(self) -> dict[str, RateData]:
        return dict(self.latest)


rate_cache = RateCache()


async def fetch_and_store(aggregator: RateAggregator) -> dict[str, RateData]:
    rates = await aggregator.fetch_all()

    async with async_session() as session:
        for currency, rate_data in rates.items():
            db_rate = ExchangeRate(
                currency_code=rate_data.currency_code,
                base_currency=rate_data.base_currency,
                rate=rate_data.rate,
                cash_buy_rate=rate_data.cash_buy_rate,
                cash_sell_rate=rate_data.cash_sell_rate,
                tt_buy_rate=rate_data.tt_buy_rate,
                tt_sell_rate=rate_data.tt_sell_rate,
                spread=rate_data.spread,
                source=rate_data.source,
                fetched_at=rate_data.fetched_at,
                rate_date=rate_data.rate_date,
            )
            session.add(db_rate)
            rate_cache.update(currency, rate_data)

        await session.commit()

    logger.info(f"Stored {len(rates)} rates, cache updated")
    return rates


async def get_historical_rates(
    currency: str, days: int = 30, session: AsyncSession | None = None
) -> list[dict]:
    start_date = date.today() - timedelta(days=days)

    async def _query(s: AsyncSession):
        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.currency_code == currency,
                ExchangeRate.rate_date >= start_date,
            )
            .order_by(ExchangeRate.rate_date)
        )
        result = await s.execute(stmt)
        rows = result.scalars().all()

        seen = {}
        for row in rows:
            key = row.rate_date.isoformat()
            if key not in seen:
                seen[key] = {
                    "date": key,
                    "rate": row.rate,
                    "tt_buy_rate": row.tt_buy_rate,
                    "tt_sell_rate": row.tt_sell_rate,
                    "spread": row.spread,
                    "source": row.source,
                }
        return list(seen.values())

    if session:
        return await _query(session)

    async with async_session() as s:
        return await _query(s)


async def get_rate_values(currency: str, days: int = 90) -> list[float]:
    history = await get_historical_rates(currency, days)
    return [h["rate"] for h in history]


async def load_latest_from_db():
    """DB에서 각 통화별 최신 환율을 캐시에 로드"""
    async with async_session() as session:
        from sqlalchemy import func, distinct
        currencies_stmt = select(distinct(ExchangeRate.currency_code))
        result = await session.execute(currencies_stmt)
        currencies = [row[0] for row in result.all()]

        for currency in currencies:
            stmt = (
                select(ExchangeRate)
                .where(ExchangeRate.currency_code == currency)
                .order_by(ExchangeRate.rate_date.desc(), ExchangeRate.fetched_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                rate_cache.update(currency, RateData(
                    currency_code=row.currency_code,
                    base_currency=row.base_currency,
                    rate=row.rate,
                    cash_buy_rate=row.cash_buy_rate,
                    cash_sell_rate=row.cash_sell_rate,
                    tt_buy_rate=row.tt_buy_rate,
                    tt_sell_rate=row.tt_sell_rate,
                    spread=row.spread,
                    source=row.source,
                    fetched_at=row.fetched_at,
                    rate_date=row.rate_date,
                ))

    logger.info(f"Loaded {len(rate_cache.latest)} currencies from DB")
