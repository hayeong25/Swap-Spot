import asyncio
import logging

from app.schemas.rate import RateData
from app.sources.base import ExchangeRateSource

logger = logging.getLogger(__name__)

SOURCE_PRIORITY = {"koreaexim": 1, "hanabank": 2, "ecos": 3, "demo": 4}


class RateAggregator:
    def __init__(self, sources: list[ExchangeRateSource]):
        self.sources = sources

    async def fetch_all(self) -> dict[str, RateData]:
        results = await asyncio.gather(
            *[s.fetch_rates() for s in self.sources],
            return_exceptions=True,
        )

        merged: dict[str, list[RateData]] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Source fetch error: {result}")
                continue
            for rate in result:
                merged.setdefault(rate.currency_code, []).append(rate)

        best: dict[str, RateData] = {}
        for currency, rate_list in merged.items():
            rate_list.sort(key=lambda r: SOURCE_PRIORITY.get(r.source, 99))
            best[currency] = rate_list[0]

        return best

    async def health_check_all(self) -> dict[str, bool]:
        checks = await asyncio.gather(
            *[s.health_check() for s in self.sources],
            return_exceptions=True,
        )
        return {
            s.source_name: (c if isinstance(c, bool) else False)
            for s, c in zip(self.sources, checks)
        }
