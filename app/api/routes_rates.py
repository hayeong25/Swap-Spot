from datetime import date, datetime

import pytz
from fastapi import APIRouter, Query

from app.schemas.rate import HistoricalRateResponse, RateResponse
from app.services.rate_service import get_historical_rates, rate_cache
from app.services.forecast_engine import get_forecast_cached
from app.services.timing_engine import compute_timing, compute_travel_timing
from app.utils.currency import MAJOR_CURRENCIES

router = APIRouter(prefix="/api/rates", tags=["rates"])
KST = pytz.timezone("Asia/Seoul")


@router.get("/latest")
async def get_latest_rates() -> list[RateResponse]:
    rates = rate_cache.get_all()
    result = []
    for code, rate_data in rates.items():
        if code not in MAJOR_CURRENCIES:
            continue
        info = MAJOR_CURRENCIES[code]
        result.append(RateResponse(
            currency_code=code,
            currency_name=info.get("name", code),
            rate=rate_data.rate,
            tt_buy_rate=rate_data.tt_buy_rate,
            tt_sell_rate=rate_data.tt_sell_rate,
            spread=rate_data.spread,
            cash_buy_rate=rate_data.cash_buy_rate,
            cash_sell_rate=rate_data.cash_sell_rate,
            source=rate_data.source,
            updated_at=rate_data.fetched_at,
        ))
    return sorted(result, key=lambda r: list(MAJOR_CURRENCIES.keys()).index(r.currency_code) if r.currency_code in MAJOR_CURRENCIES else 99)


@router.get("/timing/{currency}")
async def get_timing(currency: str) -> dict:
    return await compute_timing(currency.upper())


@router.get("/travel-timing/{currency}")
async def get_travel_timing(currency: str, travel_date: date = Query(...)) -> dict:
    return await compute_travel_timing(currency.upper(), travel_date)


@router.get("/forecast/{currency}")
async def get_forecast(currency: str) -> dict:
    return await get_forecast_cached(currency.upper())


@router.get("/health/sources")
async def source_health() -> dict:
    from app.main import aggregator
    return await aggregator.health_check_all()


@router.get("/{currency}")
async def get_currency_history(currency: str, days: int = 30) -> HistoricalRateResponse:
    history = await get_historical_rates(currency.upper(), days)
    return HistoricalRateResponse(
        currency_code=currency.upper(),
        rates=history,
        period_days=days,
    )
