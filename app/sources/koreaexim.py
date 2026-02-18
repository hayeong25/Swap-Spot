import logging
from datetime import date, datetime, timedelta

import httpx
import pytz

from app.config import settings
from app.schemas.rate import RateData
from app.sources.base import ExchangeRateSource

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


class KoreaEximSource(ExchangeRateSource):
    source_name = "koreaexim"
    BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

    async def fetch_rates(self) -> list[RateData]:
        if not settings.koreaexim_api_key or settings.koreaexim_api_key == "your_api_key_here":
            logger.warning("KoreaExim API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
                # 오늘 데이터가 없으면 최근 영업일까지 최대 7일 역추적
                data = []
                search_date = datetime.now(KST).date()
                for _ in range(7):
                    params = {
                        "authkey": settings.koreaexim_api_key,
                        "searchdate": search_date.strftime("%Y%m%d"),
                        "data": "AP01",
                    }
                    resp = await client.get(self.BASE_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    if isinstance(data, list) and len(data) > 0:
                        # result 코드 확인 (1=성공)
                        first = data[0] if data else {}
                        result_code = first.get("result", 1)
                        if result_code == 4:
                            logger.warning("KoreaExim daily request limit exceeded")
                            return []
                        if result_code == 3:
                            logger.error("KoreaExim API key expired or invalid")
                            return []
                        logger.info(f"KoreaExim: found data for {search_date}")
                        break

                    search_date -= timedelta(days=1)
                else:
                    logger.warning("KoreaExim: no data found in last 7 days")
                    return []

            if not data or not isinstance(data, list):
                return []

            now = datetime.now(KST)
            rates = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                cur_unit = item.get("cur_unit")
                if not cur_unit:
                    continue
                currency_code = str(cur_unit).replace("(100)", "").strip()
                deal_bas_r = item.get("deal_bas_r") or "0"
                ttb = item.get("ttb") or "0"
                tts = item.get("tts") or "0"

                rate_val = self._parse_rate(deal_bas_r)
                if rate_val <= 0:
                    continue

                rates.append(RateData(
                    currency_code=currency_code,
                    rate=rate_val,
                    tt_buy_rate=self._parse_rate(ttb) or None,
                    tt_sell_rate=self._parse_rate(tts) or None,
                    spread=self._calc_spread(ttb, tts),
                    source=self.source_name,
                    fetched_at=now,
                    rate_date=search_date,
                ))
            logger.info(f"KoreaExim fetched {len(rates)} rates (date: {search_date})")
            return rates

        except Exception as e:
            logger.error(f"KoreaExim fetch failed: {e}")
            return []

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False, follow_redirects=True) as client:
                resp = await client.get(self.BASE_URL, params={
                    "authkey": settings.koreaexim_api_key,
                    "searchdate": datetime.now(KST).strftime("%Y%m%d"),
                    "data": "AP01",
                })
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _parse_rate(value: str) -> float:
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _calc_spread(ttb: str, tts: str) -> float | None:
        try:
            b = float(str(ttb).replace(",", ""))
            s = float(str(tts).replace(",", ""))
            if b > 0 and s > 0:
                return round(s - b, 2)
        except (ValueError, TypeError):
            pass
        return None
