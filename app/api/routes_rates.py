from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.rate import HistoricalRateResponse, RateResponse
from app.services.rate_service import get_historical_rates, rate_cache
from app.services.forecast_engine import get_forecast_cached
from app.services.timing_engine import compute_timing, compute_travel_timing
from app.utils.currency import MAJOR_CURRENCIES

router = APIRouter(prefix="/api/rates", tags=["rates"])


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
    currency_order = {code: i for i, code in enumerate(MAJOR_CURRENCIES)}
    return sorted(result, key=lambda r: currency_order.get(r.currency_code, 99))


def _validate_currency(currency: str) -> str:
    code = currency.strip().upper()
    if not code.isalpha() or len(code) > 5:
        raise HTTPException(status_code=400, detail="Invalid currency code")
    return code


@router.get("/timing/{currency}")
async def get_timing(currency: str) -> dict:
    return await compute_timing(_validate_currency(currency))


@router.get("/travel-timing/{currency}")
async def get_travel_timing(currency: str, travel_date: date = Query(...)) -> dict:
    return await compute_travel_timing(_validate_currency(currency), travel_date)


@router.get("/forecast/{currency}")
async def get_forecast(currency: str) -> dict:
    return await get_forecast_cached(_validate_currency(currency))


@router.get("/health/sources")
async def source_health(request: Request) -> dict:
    aggregator = request.app.state.aggregator
    return await aggregator.health_check_all()


@router.get("/{currency}")
async def get_currency_history(currency: str, days: int = Query(default=30, ge=1, le=365)) -> HistoricalRateResponse:
    code = _validate_currency(currency)
    history = await get_historical_rates(code, days)
    return HistoricalRateResponse(
        currency_code=code,
        rates=history,
        period_days=days,
    )
