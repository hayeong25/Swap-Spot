"""Tests for rate_service.py cache and data functions"""
import pytest
import pytest_asyncio
from datetime import date, datetime

import pytz

from app.schemas.rate import RateData
from app.services.rate_service import RateCache, rate_cache

KST = pytz.timezone("Asia/Seoul")


class TestRateCache:
    @pytest.mark.asyncio
    async def test_update_and_get_all(self, sample_rate_data):
        await rate_cache.update("USD", sample_rate_data)
        all_rates = rate_cache.get_all()
        assert "USD" in all_rates
        assert all_rates["USD"].rate == 1450.0
        assert rate_cache.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_overwrites(self, sample_rate_data):
        await rate_cache.update("USD", sample_rate_data)

        updated = RateData(
            currency_code="USD",
            rate=1460.0,
            source="hanabank",
            fetched_at=datetime.now(KST),
            rate_date=date.today(),
        )
        await rate_cache.update("USD", updated)
        assert rate_cache.latest["USD"].rate == 1460.0

    @pytest.mark.asyncio
    async def test_get_all_returns_copy(self, sample_rate_data):
        await rate_cache.update("USD", sample_rate_data)
        copy = rate_cache.get_all()
        copy["EUR"] = sample_rate_data
        assert "EUR" not in rate_cache.latest

    @pytest.mark.asyncio
    async def test_multiple_currencies(self):
        now = datetime.now(KST)
        today = date.today()
        for code, rate_val in [("USD", 1450.0), ("EUR", 1550.0), ("JPY", 950.0)]:
            rd = RateData(
                currency_code=code,
                rate=rate_val,
                source="test",
                fetched_at=now,
                rate_date=today,
            )
            await rate_cache.update(code, rd)

        all_rates = rate_cache.get_all()
        assert len(all_rates) == 3
        assert all_rates["JPY"].rate == 950.0
