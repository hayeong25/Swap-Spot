import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pytz
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.exchange_rate import ExchangeRate
from app.schemas.rate import RateData
from app.sources.aggregator import RateAggregator, SOURCE_PRIORITY

_broadcast_callback = None


def set_broadcast_callback(callback):
    global _broadcast_callback
    _broadcast_callback = callback

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

_cache_lock = asyncio.Lock()


@dataclass
class RateCache:
    latest: dict[str, RateData] = field(default_factory=dict)
    updated_at: datetime | None = None

    async def update(self, currency: str, rate: RateData):
        async with _cache_lock:
            self.latest[currency] = rate
            self.updated_at = datetime.now(KST)

    def get_all(self) -> dict[str, RateData]:
        return dict(self.latest)


rate_cache = RateCache()


async def fetch_and_store(aggregator: RateAggregator) -> dict[str, RateData]:
    rates = await aggregator.fetch_all()

    if not rates:
        logger.debug("No rates fetched, skipping store")
        return rates

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
            await rate_cache.update(currency, rate_data)

        await session.commit()

    logger.info(f"Stored {len(rates)} rates, cache updated")

    if _broadcast_callback:
        try:
            await _broadcast_callback(rate_cache.get_all())
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")

    return rates


async def get_historical_rates(
    currency: str, days: int = 30, session: AsyncSession | None = None
) -> list[dict]:
    start_date = datetime.now(KST).date() - timedelta(days=days)

    async def _query(s: AsyncSession):
        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.currency_code == currency,
                ExchangeRate.rate_date >= start_date,
            )
            .order_by(ExchangeRate.rate_date, ExchangeRate.fetched_at)
        )
        result = await s.execute(stmt)
        rows = result.scalars().all()

        seen = {}
        for row in rows:
            key = row.rate_date.isoformat()
            row_priority = SOURCE_PRIORITY.get(row.source, 99)
            if key not in seen or row_priority < SOURCE_PRIORITY.get(seen[key]["source"], 99):
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
    """DB에서 각 통화별 최신 환율을 캐시에 로드 (단일 쿼리)"""
    async with async_session() as session:
        # 통화별 최신 id를 서브쿼리로 가져와 N+1 방지
        latest_ids_subq = (
            select(
                func.max(ExchangeRate.id).label("max_id")
            )
            .group_by(ExchangeRate.currency_code)
            .subquery()
        )
        stmt = select(ExchangeRate).where(
            ExchangeRate.id.in_(select(latest_ids_subq.c.max_id))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        for row in rows:
            await rate_cache.update(row.currency_code, RateData(
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
