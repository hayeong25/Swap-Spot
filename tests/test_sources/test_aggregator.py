"""Tests for aggregator.py source merging and priority logic"""
import pytest
from datetime import date, datetime

import pytz

from app.schemas.rate import RateData
from app.sources.aggregator import RateAggregator, SOURCE_PRIORITY
from app.sources.base import ExchangeRateSource

KST = pytz.timezone("Asia/Seoul")


class MockSource(ExchangeRateSource):
    def __init__(self, name: str, rates: list[RateData], should_fail: bool = False):
        self.source_name = name
        self._rates = rates
        self._should_fail = should_fail

    async def fetch_rates(self) -> list[RateData]:
        if self._should_fail:
            raise ConnectionError(f"{self.source_name} failed")
        return self._rates

    async def health_check(self) -> bool:
        return not self._should_fail


def _make_rate(currency: str, rate: float, source: str) -> RateData:
    return RateData(
        currency_code=currency,
        rate=rate,
        source=source,
        fetched_at=datetime.now(KST),
        rate_date=date.today(),
    )


class TestRateAggregator:
    @pytest.mark.asyncio
    async def test_single_source(self):
        source = MockSource("koreaexim", [_make_rate("USD", 1450, "koreaexim")])
        agg = RateAggregator([source])
        result = await agg.fetch_all()
        assert "USD" in result
        assert result["USD"].rate == 1450

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """koreaexim should win over hanabank for same currency"""
        s1 = MockSource("koreaexim", [_make_rate("USD", 1450, "koreaexim")])
        s2 = MockSource("hanabank", [_make_rate("USD", 1455, "hanabank")])
        agg = RateAggregator([s2, s1])  # hanabank first, but priority should pick koreaexim
        result = await agg.fetch_all()
        assert result["USD"].rate == 1450
        assert result["USD"].source == "koreaexim"

    @pytest.mark.asyncio
    async def test_failed_source_ignored(self):
        s1 = MockSource("koreaexim", [], should_fail=True)
        s2 = MockSource("hanabank", [_make_rate("USD", 1455, "hanabank")])
        agg = RateAggregator([s1, s2])
        result = await agg.fetch_all()
        assert "USD" in result
        assert result["USD"].source == "hanabank"

    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        s1 = MockSource("koreaexim", [], should_fail=True)
        s2 = MockSource("hanabank", [], should_fail=True)
        agg = RateAggregator([s1, s2])
        result = await agg.fetch_all()
        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_currencies(self):
        s1 = MockSource("koreaexim", [
            _make_rate("USD", 1450, "koreaexim"),
            _make_rate("EUR", 1550, "koreaexim"),
        ])
        s2 = MockSource("hanabank", [
            _make_rate("USD", 1455, "hanabank"),
            _make_rate("JPY", 950, "hanabank"),
        ])
        agg = RateAggregator([s1, s2])
        result = await agg.fetch_all()
        assert len(result) == 3
        assert result["USD"].source == "koreaexim"
        assert result["JPY"].source == "hanabank"

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        s1 = MockSource("koreaexim", [])
        s2 = MockSource("hanabank", [], should_fail=True)
        agg = RateAggregator([s1, s2])
        health = await agg.health_check_all()
        assert health["koreaexim"] is True
        assert health["hanabank"] is False
