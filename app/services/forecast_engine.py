"""Monte Carlo 환율 예측 엔진 (Block Bootstrap)"""
import logging
import math
import random
import statistics
import time
from datetime import datetime

import pytz

from app.services.rate_service import get_rate_values, rate_cache

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

NUM_SIMULATIONS = 5000
BLOCK_LENGTH = 3
HORIZONS_BIZ_DAYS = {1: 5, 2: 10, 3: 15}

_forecast_cache: dict[str, tuple[float, dict]] = {}
FORECAST_CACHE_TTL = 300  # 5분


def _compute_log_returns(rates: list[float]) -> list[float]:
    returns = []
    for i in range(1, len(rates)):
        if rates[i - 1] > 0 and rates[i] > 0:
            returns.append(math.log(rates[i] / rates[i - 1]))
    return returns


def _block_bootstrap_paths(
    log_returns: list[float],
    horizon: int,
    num_paths: int,
    block_len: int = BLOCK_LENGTH,
) -> list[list[float]]:
    n = len(log_returns)
    if n < block_len:
        block_len = max(1, n)

    max_start = n - block_len
    paths = []
    for _ in range(num_paths):
        path = []
        while len(path) < horizon:
            start = random.randint(0, max_start)
            path.extend(log_returns[start : start + block_len])
        paths.append(path[:horizon])
    return paths


def _generate_targets(
    current_rate: float,
    rates: list[float],
    horizon_weeks: int,
) -> list[float]:
    if len(rates) < 10:
        return [round(current_rate * (1 - 0.01 * i), 2) for i in range(1, 4)]

    log_returns = _compute_log_returns(rates)
    if not log_returns:
        return [round(current_rate * (1 - 0.01 * i), 2) for i in range(1, 4)]

    daily_vol = statistics.stdev(log_returns)
    biz_days = HORIZONS_BIZ_DAYS[horizon_weeks]
    horizon_vol = daily_vol * math.sqrt(biz_days)

    targets = []
    for multiplier in [0.15, 0.3, 0.55, 1.0]:
        target = current_rate * math.exp(-multiplier * horizon_vol)
        targets.append(round(target, 2))

    sorted_rates = sorted(rates)
    p25 = sorted_rates[len(sorted_rates) // 4]
    if p25 < targets[0]:
        targets.append(round(p25, 2))

    targets = sorted(set(targets), reverse=True)
    return targets[:4]


def _compute_probabilities(
    current_rate: float,
    paths: list[list[float]],
    targets: list[float],
) -> list[dict]:
    results = []
    for target in targets:
        count_hit = 0
        for path_returns in paths:
            price = current_rate
            for lr in path_returns:
                price *= math.exp(lr)
                if price <= target:
                    count_hit += 1
                    break
        probability = count_hit / len(paths)
        results.append({
            "rate": target,
            "label": f"{target:,.2f}원",
            "probability": round(probability, 3),
        })
    return results


def _compute_percentiles(
    current_rate: float,
    paths: list[list[float]],
) -> dict:
    terminal_rates = []
    for path_returns in paths:
        price = current_rate
        for lr in path_returns:
            price *= math.exp(lr)
        terminal_rates.append(price)

    terminal_rates.sort()
    n = len(terminal_rates)

    def pct(p):
        idx = max(0, min(int(n * p), n - 1))
        return round(terminal_rates[idx], 2)

    return {"p5": pct(0.05), "p25": pct(0.25), "p50": pct(0.50), "p75": pct(0.75), "p95": pct(0.95)}


async def compute_forecast(currency: str) -> dict:
    rates = await get_rate_values(currency, days=90)

    cached = rate_cache.latest.get(currency)
    current = cached.rate if cached else (rates[-1] if rates else 0)

    if not rates or current <= 0 or len(rates) < 15:
        return {
            "currency_code": currency,
            "current_rate": current,
            "data_points": len(rates),
            "horizons": [],
            "error": "데이터가 부족하여 예측할 수 없습니다.",
            "updated_at": datetime.now(KST).isoformat(),
        }

    if cached and rates and abs(rates[-1] - current) > 0.01:
        rates.append(current)

    log_returns = _compute_log_returns(rates)

    horizons = []
    for weeks in sorted(HORIZONS_BIZ_DAYS):
        biz_days = HORIZONS_BIZ_DAYS[weeks]
        paths = _block_bootstrap_paths(log_returns, biz_days, NUM_SIMULATIONS)
        targets = _generate_targets(current, rates, weeks)
        target_results = _compute_probabilities(current, paths, targets)
        distribution = _compute_percentiles(current, paths)

        horizons.append({
            "weeks": weeks,
            "business_days": biz_days,
            "targets": target_results,
            "distribution": distribution,
        })

    daily_vol = statistics.stdev(log_returns) if len(log_returns) > 1 else 0
    annual_vol = daily_vol * math.sqrt(252)

    return {
        "currency_code": currency,
        "current_rate": current,
        "data_points": len(rates),
        "daily_volatility_pct": round(daily_vol * 100, 3),
        "annual_volatility_pct": round(annual_vol * 100, 1),
        "num_simulations": NUM_SIMULATIONS,
        "horizons": horizons,
        "updated_at": datetime.now(KST).isoformat(),
    }


async def get_forecast_cached(currency: str) -> dict:
    now = time.monotonic()
    if currency in _forecast_cache:
        cached_time, cached_result = _forecast_cache[currency]
        if now - cached_time < FORECAST_CACHE_TTL:
            return cached_result

    result = await compute_forecast(currency)
    _forecast_cache[currency] = (now, result)
    return result
