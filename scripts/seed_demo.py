"""API 키 없이 대시보드를 체험할 수 있는 데모 데이터 시딩 스크립트"""
import asyncio
import random
from datetime import date, datetime, timedelta

import pytz

# 프로젝트 루트에서 실행: python -m scripts.seed_demo
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import engine, async_session
from app.models.exchange_rate import Base, ExchangeRate

KST = pytz.timezone("Asia/Seoul")

# 기준 환율 (2026년 2월 기준 가상 데이터)
BASE_RATES = {
    "USD": 1350.0,
    "EUR": 1460.0,
    "JPY": 890.0,  # 100엔당
    "GBP": 1710.0,
    "CNH": 186.0,
    "CHF": 1520.0,
    "CAD": 960.0,
    "AUD": 870.0,
    "HKD": 173.0,
    "SGD": 1010.0,
    "THB": 38.0,
}


def random_walk(base: float, days: int) -> list[float]:
    """랜덤 워크로 환율 시계열 생성"""
    rates = [base]
    volatility = base * 0.003  # 0.3% 일변동
    for _ in range(days - 1):
        change = random.gauss(0, volatility)
        new_rate = rates[-1] + change
        rates.append(round(new_rate, 2))
    return rates


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    today = date.today()
    days = 90
    now = datetime.now(KST)

    async with async_session() as session:
        for currency, base_rate in BASE_RATES.items():
            rates = random_walk(base_rate, days)
            for i, rate_val in enumerate(rates):
                rate_date = today - timedelta(days=days - 1 - i)
                # 주말 제외
                if rate_date.weekday() >= 5:
                    continue

                spread = round(rate_val * 0.035, 2)  # 3.5% 스프레드
                session.add(ExchangeRate(
                    currency_code=currency,
                    base_currency="KRW",
                    rate=rate_val,
                    cash_buy_rate=round(rate_val - spread / 2, 2),
                    cash_sell_rate=round(rate_val + spread / 2, 2),
                    tt_buy_rate=round(rate_val * 0.995, 2),
                    tt_sell_rate=round(rate_val * 1.005, 2),
                    spread=spread,
                    source="demo",
                    fetched_at=now,
                    rate_date=rate_date,
                ))

        await session.commit()
        print(f"Seeded {days} days of demo data for {len(BASE_RATES)} currencies")


if __name__ == "__main__":
    asyncio.run(seed())
