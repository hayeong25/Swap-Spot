import logging
from datetime import date, datetime

import httpx
import pytz
from bs4 import BeautifulSoup

from app.schemas.rate import RateData
from app.sources.base import ExchangeRateSource

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

CURRENCY_MAP = {
    "미 달러": "USD",
    "유로": "EUR",
    "일본 엔": "JPY",
    "영국 파운드": "GBP",
    "중국 위안": "CNY",
    "스위스 프랑": "CHF",
    "캐나다 달러": "CAD",
    "호주 달러": "AUD",
    "홍콩 달러": "HKD",
    "싱가포르 달러": "SGD",
}

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.kebhana.com/",
}


class HanaBankSource(ExchangeRateSource):
    source_name = "hanabank"
    URL = "https://www.kebhana.com/cms/rate/wpfxd651_01i_01.do"

    async def fetch_rates(self) -> list[RateData]:
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers=DESKTOP_HEADERS,
                verify=False,
            ) as client:
                # POST 요청으로 환율 데이터 조회
                resp = await client.post(
                    self.URL,
                    data={"ajax": "true", "curCd": "", "tmpInqStrDt": "", "tmpInqEndDt": ""},
                )
                if resp.status_code != 200:
                    # GET fallback
                    resp = await client.get(self.URL)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "lxml")
            return self._parse_rates(soup)

        except Exception as e:
            logger.error(f"HanaBank fetch failed: {e}")
            return []

    def _parse_rates(self, soup: BeautifulSoup) -> list[RateData]:
        rates = []
        now = datetime.now(KST)
        today = date.today()

        # 여러 가능한 테이블 선택자 시도
        table = None
        for selector in ["table.tbl_exchange", "table.tbl_col", "#grdExRate", "table"]:
            table = soup.select_one(selector)
            if table and table.select("tr"):
                break

        if not table:
            logger.warning("HanaBank: exchange rate table not found")
            return []

        rows = table.select("tbody tr") or table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            name_text = cells[0].get_text(strip=True)
            currency_code = None
            for key, code in CURRENCY_MAP.items():
                if key in name_text:
                    currency_code = code
                    break

            if not currency_code:
                continue

            try:
                # 칼럼 순서: 통화명, 현찰매입, 현찰매도, 송금보내실때, 송금받으실때, 매매기준율 등
                values = [self._parse_val(c.get_text(strip=True)) for c in cells[1:]]
                values = [v for v in values if v is not None and v > 0]

                if not values:
                    continue

                # 마지막 유효값을 기준율로, 나머지에서 매입/매도 추정
                rate_val = values[-1] if len(values) >= 1 else 0
                cash_buy = values[0] if len(values) >= 2 else None
                cash_sell = values[1] if len(values) >= 3 else None
                spread = round(cash_sell - cash_buy, 2) if cash_buy and cash_sell else None

                rates.append(RateData(
                    currency_code=currency_code,
                    rate=rate_val,
                    cash_buy_rate=cash_buy,
                    cash_sell_rate=cash_sell,
                    spread=spread,
                    source=self.source_name,
                    fetched_at=now,
                    rate_date=today,
                ))
            except (ValueError, IndexError) as e:
                logger.debug(f"HanaBank parse error for {name_text}: {e}")
                continue

        logger.info(f"HanaBank fetched {len(rates)} rates")
        return rates

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, headers=DESKTOP_HEADERS, verify=False) as client:
                resp = await client.get(self.URL)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _parse_val(text: str) -> float | None:
        try:
            cleaned = text.replace(",", "").replace(" ", "").strip()
            if not cleaned or cleaned == "-":
                return None
            return float(cleaned)
        except (ValueError, TypeError):
            return None
