import logging
from datetime import date, datetime, timedelta

import httpx
import pytz

from app.config import settings
from app.schemas.rate import RateData
from app.sources.base import ExchangeRateSource

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

# ECOS 환율 통계 항목 코드 (주요 통화 기준환율)
ECOS_CURRENCY_ITEMS = {
    "USD": "0000001",  # 원/미달러
    "EUR": "0000003",  # 원/유로
    "JPY": "0000002",  # 원/100엔
    "GBP": "0000005",  # 원/영파운드
    "CNY": "0000053",  # 원/위안
}

TABLE_CODE = "731Y001"  # 환율 일별 시세
ITEM_CODE_PREFIX = "0000001"  # 기준환율


class EcosSource(ExchangeRateSource):
    source_name = "ecos"
    BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"

    async def fetch_rates(self) -> list[RateData]:
        today = date.today()
        rates = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for currency, item_code in ECOS_CURRENCY_ITEMS.items():
                    rate = await self._fetch_single(client, currency, item_code, today)
                    if rate:
                        rates.append(rate)
            logger.info(f"ECOS fetched {len(rates)} rates")
        except Exception as e:
            logger.error(f"ECOS fetch failed: {e}")
        return rates

    async def fetch_historical(self, currency: str, days: int = 90) -> list[RateData]:
        item_code = ECOS_CURRENCY_ITEMS.get(currency)
        if not item_code:
            return []

        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        url = (
            f"{self.BASE_URL}/{settings.ecos_api_key}/json/kr/1/300"
            f"/{TABLE_CODE}/D/{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
            f"/{item_code}"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            rows = data.get("StatisticSearch", {}).get("row", [])
            rates = []
            for row in rows:
                rate_val = float(row.get("DATA_VALUE", "0").replace(",", ""))
                rate_date_str = row.get("TIME", "")
                if rate_val > 0 and rate_date_str:
                    rd = datetime.strptime(rate_date_str, "%Y%m%d").date()
                    rates.append(RateData(
                        currency_code=currency,
                        rate=rate_val,
                        source=self.source_name,
                        fetched_at=datetime.now(KST),
                        rate_date=rd,
                    ))
            return rates
        except Exception as e:
            logger.error(f"ECOS historical fetch failed for {currency}: {e}")
            return []

    async def _fetch_single(
        self, client: httpx.AsyncClient, currency: str, item_code: str, today: date
    ) -> RateData | None:
        start = (today - timedelta(days=7)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        url = (
            f"{self.BASE_URL}/{settings.ecos_api_key}/json/kr/1/10"
            f"/{TABLE_CODE}/D/{start}/{end}/{item_code}"
        )
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if not rows:
                return None

            latest = rows[-1]
            rate_val = float(latest.get("DATA_VALUE", "0").replace(",", ""))
            rate_date_str = latest.get("TIME", "")
            if rate_val <= 0:
                return None

            rd = datetime.strptime(rate_date_str, "%Y%m%d").date()
            return RateData(
                currency_code=currency,
                rate=rate_val,
                source=self.source_name,
                fetched_at=datetime.now(KST),
                rate_date=rd,
            )
        except Exception as e:
            logger.error(f"ECOS fetch {currency} failed: {e}")
            return None

    async def health_check(self) -> bool:
        try:
            url = (
                f"{self.BASE_URL}/{settings.ecos_api_key}/json/kr/1/1"
                f"/{TABLE_CODE}/D/20240101/20240102/{ITEM_CODE_PREFIX}"
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False
