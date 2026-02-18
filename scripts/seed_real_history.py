"""수출입은행 API로 실제 과거 환율 데이터를 시딩하는 스크립트"""
import asyncio
import sys
import os
from datetime import date, datetime, timedelta

import httpx
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.models.database import engine, async_session
from app.models.exchange_rate import Base, ExchangeRate

KST = pytz.timezone("Asia/Seoul")
API_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"


async def fetch_day(client: httpx.AsyncClient, search_date: str) -> list[dict]:
    resp = await client.get(API_URL, params={
        "authkey": settings.koreaexim_api_key,
        "searchdate": search_date,
        "data": "AP01",
    })
    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        return data
    return []


def parse_rate(val: str) -> float:
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not settings.koreaexim_api_key or settings.koreaexim_api_key == "your_api_key_here":
        print("ERROR: KOREAEXIM_API_KEY not set in .env")
        return

    today = date.today()
    days_back = 90
    now = datetime.now(KST)
    total_stored = 0
    api_calls = 0

    async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
        async with async_session() as session:
            d = today
            for _ in range(days_back):
                d -= timedelta(days=1)
                # 주말 스킵
                if d.weekday() >= 5:
                    continue

                search_date = d.strftime("%Y%m%d")
                items = await fetch_day(client, search_date)
                api_calls += 1

                if not items:
                    continue

                day_count = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    cur_unit = item.get("cur_unit")
                    if not cur_unit:
                        continue

                    currency_code = str(cur_unit).replace("(100)", "").strip()
                    deal_bas_r = parse_rate(item.get("deal_bas_r") or "0")
                    ttb = parse_rate(item.get("ttb") or "0")
                    tts = parse_rate(item.get("tts") or "0")

                    if deal_bas_r <= 0:
                        continue

                    session.add(ExchangeRate(
                        currency_code=currency_code,
                        base_currency="KRW",
                        rate=deal_bas_r,
                        tt_buy_rate=ttb if ttb > 0 else None,
                        tt_sell_rate=tts if tts > 0 else None,
                        spread=round(tts - ttb, 2) if ttb > 0 and tts > 0 else None,
                        source="koreaexim",
                        fetched_at=now,
                        rate_date=d,
                    ))
                    day_count += 1

                total_stored += day_count
                if day_count > 0:
                    print(f"  {search_date}: {day_count} currencies")

                # API 속도 제한 방지 (1000회/일)
                if api_calls % 10 == 0:
                    await asyncio.sleep(0.5)

            await session.commit()

    print(f"\nDone: {total_stored} records stored ({api_calls} API calls)")


if __name__ == "__main__":
    asyncio.run(seed())
