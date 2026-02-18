import bisect
import logging
import statistics
from datetime import date, datetime

import pytz

from app.services.rate_service import get_rate_values, rate_cache

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


def moving_average_signal(rates: list[float], short_window: int = 5, long_window: int = 20) -> str:
    if len(rates) < long_window:
        return "HOLD"

    short_ma = sum(rates[-short_window:]) / short_window
    long_ma = sum(rates[-long_window:]) / long_window

    if short_ma < long_ma * 0.998:
        return "WAIT"
    elif short_ma > long_ma * 1.002:
        return "BUY"
    return "HOLD"


def percentile_signal(current_rate: float, historical_rates: list[float]) -> str:
    if len(historical_rates) < 10:
        return "HOLD"

    sorted_rates = sorted(historical_rates)
    rank = bisect.bisect_left(sorted_rates, current_rate) / len(sorted_rates)

    if rank <= 0.25:
        return "BUY"
    elif rank >= 0.75:
        return "WAIT"
    return "HOLD"


def bollinger_signal(rates: list[float], window: int = 20, num_std: int = 2) -> str:
    if len(rates) < window:
        return "HOLD"

    ma = statistics.mean(rates[-window:])
    std = statistics.stdev(rates[-window:])
    if std == 0:
        return "HOLD"

    upper = ma + num_std * std
    lower = ma - num_std * std
    current = rates[-1]

    if current <= lower:
        return "BUY"
    elif current >= upper:
        return "WAIT"
    return "HOLD"


def compute_ma(rates: list[float], window: int) -> float:
    if len(rates) < window:
        return rates[-1] if rates else 0
    return sum(rates[-window:]) / window


def compute_percentile(current: float, rates: list[float]) -> float:
    if not rates:
        return 50.0
    sorted_r = sorted(rates)
    rank = bisect.bisect_left(sorted_r, current) / len(sorted_r)
    return round(rank * 100, 1)


def compute_target_rate(rates: list[float]) -> float | None:
    """90일 데이터 기반 목표 환율 (25백분위와 볼린저 하단 평균)"""
    if len(rates) < 20:
        return None
    sorted_r = sorted(rates)
    p25 = sorted_r[max(0, len(sorted_r) // 4)]
    ma20 = statistics.mean(rates[-20:])
    std20 = statistics.stdev(rates[-20:])
    bollinger_lower = ma20 - 2 * std20 if std20 > 0 else ma20
    target = round((p25 + bollinger_lower) / 2, 2)
    return target


async def compute_timing(currency: str) -> dict:
    rates = await get_rate_values(currency, days=90)

    cached = rate_cache.latest.get(currency)
    current = cached.rate if cached else (rates[-1] if rates else 0)

    if not rates or current <= 0:
        return {
            "currency_code": currency,
            "recommendation": "HOLD",
            "confidence": 0,
            "current_rate": current,
            "signals": {},
            "percentile_90d": 50.0,
            "ma_short": 0,
            "ma_long": 0,
            "updated_at": datetime.now(KST).isoformat(),
        }

    if cached and rates and rates[-1] != current:
        rates.append(current)

    sig_ma = moving_average_signal(rates)
    sig_pct = percentile_signal(current, rates)
    sig_bb = bollinger_signal(rates)

    signals = [sig_ma, sig_pct, sig_bb]
    buy_count = signals.count("BUY")
    wait_count = signals.count("WAIT")

    if buy_count >= 2:
        recommendation = "BUY"
        confidence = round(buy_count / 3, 2)
    elif wait_count >= 2:
        recommendation = "WAIT"
        confidence = round(wait_count / 3, 2)
    else:
        recommendation = "HOLD"
        confidence = 0.5

    return {
        "currency_code": currency,
        "recommendation": recommendation,
        "confidence": confidence,
        "current_rate": current,
        "signals": {
            "moving_average": sig_ma,
            "percentile": sig_pct,
            "bollinger": sig_bb,
        },
        "percentile_90d": compute_percentile(current, rates),
        "ma_short": round(compute_ma(rates, 5), 2),
        "ma_long": round(compute_ma(rates, 20), 2),
        "updated_at": datetime.now(KST).isoformat(),
    }


def _compute_urgency(days_remaining: int) -> str:
    if days_remaining < 7:
        return "immediate"
    elif days_remaining < 14:
        return "urgent"
    elif days_remaining < 30:
        return "caution"
    return "relaxed"


def _adjust_recommendation(recommendation: str, urgency: str) -> str:
    if urgency == "immediate":
        return "BUY"
    if urgency == "urgent" and recommendation == "HOLD":
        return "BUY"
    if urgency == "caution" and recommendation == "WAIT":
        return "HOLD"
    return recommendation


URGENCY_LABELS = {
    "immediate": "즉시 환전",
    "urgent": "긴급",
    "caution": "주의",
    "relaxed": "여유",
}


def _build_message(
    currency: str, days_remaining: int, urgency: str,
    recommendation: str, percentile: float, current_rate: float,
    target_rate: float | None = None,
) -> tuple[str, str]:
    rate_str = f"{current_rate:,.2f}원"
    pct_str = f"하위 {percentile:.0f}%" if percentile < 50 else f"상위 {100 - percentile:.0f}%"
    target_str = f"{target_rate:,.2f}원" if target_rate else None

    if urgency == "immediate":
        msg = (
            f"출발까지 {days_remaining}일 남았습니다. "
            f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str}). "
            f"출발이 임박하여 즉시 환전을 권장합니다."
        )
        tip = "남은 기간이 짧아 지금 전액 환전하는 것이 안전합니다."
    elif urgency == "urgent":
        msg = (
            f"출발까지 {days_remaining}일 남았습니다. "
            f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str}). "
            f"환전 시기가 다가왔습니다. 빠른 환전을 추천합니다."
        )
        tip = "분할 환전 추천: 지금 70%, 출발 직전 나머지 30%"
    elif urgency == "caution":
        if recommendation == "BUY":
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str})로 매수 적기입니다. "
                f"지금 환전하면 유리한 가격에 확보할 수 있습니다."
            )
            tip = "분할 환전 추천: 지금 60%, 출발 2주 전 나머지 40%"
        elif recommendation == "HOLD":
            target_msg = f" 약 {target_str} 이하로 내려오면 환전 적기입니다." if target_str else ""
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str}). "
                f"조금 더 관망 후 하락 시 환전하세요.{target_msg}"
            )
            tip = f"목표 환율 {target_str} 부근에서 환전 추천. 지금 50%, 목표 도달 시 나머지 50%" if target_str else "분할 환전 추천: 지금 50%, 출발 2주 전 나머지 50%"
        else:
            target_msg = f" 약 {target_str} 이하까지 기다려보세요." if target_str else ""
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str})로 다소 높습니다. "
                f"하락을 기다리되, 2주 전까지는 환전하세요.{target_msg}"
            )
            tip = f"목표 환율 {target_str} 알림 설정 추천. 지금 30%, 하락 시 추가, 출발 2주 전 잔여분" if target_str else "분할 환전 추천: 지금 30%, 하락 시 추가, 출발 2주 전 잔여분"
    else:
        if recommendation == "BUY":
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str})로 매수 적기입니다. "
                f"지금 일부 환전해두면 유리합니다."
            )
            tip = "분할 환전 추천: 지금 50%, 출발 2주 전 나머지 50%"
        elif recommendation == "WAIT":
            target_msg = f" 약 {target_str} 이하가 적정 환전 시점입니다." if target_str else ""
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str})로 높은 편입니다. "
                f"시간 여유가 있으니 하락을 기다려보세요.{target_msg}"
            )
            tip = f"목표 환율 {target_str} 알림을 설정해두고 하락 시 환전하세요." if target_str else "급하지 않습니다. 환율 알림을 설정해두고 하락 시 환전하세요."
        else:
            target_msg = f" 약 {target_str} 이하로 떨어지면 환전 적기입니다." if target_str else ""
            msg = (
                f"출발까지 {days_remaining}일 남았습니다. "
                f"현재 {currency} 환율 {rate_str} (90일 중 {pct_str})로 보통 수준입니다. "
                f"조금 더 지켜보다 하락 시 환전하세요.{target_msg}"
            )
            tip = f"목표 환율 {target_str} 부근에서 환전 추천. 지금 30~50%, 목표 도달 시 나머지" if target_str else "분할 환전 추천: 지금 30~50%, 출발 2주 전 나머지"

    return msg, tip


async def compute_travel_timing(currency: str, travel_date: date) -> dict:
    today = date.today()
    days_remaining = (travel_date - today).days

    if days_remaining <= 0:
        cached = rate_cache.latest.get(currency)
        current = cached.rate if cached else 0
        return {
            "currency_code": currency,
            "travel_date": travel_date.isoformat(),
            "days_remaining": 0,
            "recommendation": "BUY",
            "urgency": "immediate",
            "urgency_label": "즉시 환전",
            "confidence": 1.0,
            "current_rate": current,
            "signals": {},
            "percentile_90d": 50.0,
            "message": "출발일이 지났거나 당일입니다. 즉시 환전하세요.",
            "tip": "지금 바로 환전하세요.",
            "updated_at": datetime.now(KST).isoformat(),
        }

    base = await compute_timing(currency)
    rates = await get_rate_values(currency, days=90)

    urgency = _compute_urgency(days_remaining)
    original_rec = base["recommendation"]
    adjusted_rec = _adjust_recommendation(original_rec, urgency)
    percentile = base["percentile_90d"]
    target = compute_target_rate(rates) if adjusted_rec != "BUY" else None

    msg, tip = _build_message(
        currency, days_remaining, urgency,
        adjusted_rec, percentile, base["current_rate"], target,
    )

    return {
        "currency_code": currency,
        "travel_date": travel_date.isoformat(),
        "days_remaining": days_remaining,
        "recommendation": adjusted_rec,
        "urgency": urgency,
        "urgency_label": URGENCY_LABELS[urgency],
        "confidence": base["confidence"],
        "current_rate": base["current_rate"],
        "target_rate": target,
        "signals": base["signals"],
        "percentile_90d": percentile,
        "ma_short": base["ma_short"],
        "ma_long": base["ma_long"],
        "message": msg,
        "tip": tip,
        "updated_at": base["updated_at"],
    }
