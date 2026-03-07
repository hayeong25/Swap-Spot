"""Shared pytest fixtures"""
import asyncio
from datetime import date, datetime

import pytz
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.exchange_rate import Base, ExchangeRate
from app.schemas.rate import RateData
from app.services.rate_service import rate_cache

KST = pytz.timezone("Asia/Seoul")

# In-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def sample_rate_data():
    now = datetime.now(KST)
    return RateData(
        currency_code="USD",
        base_currency="KRW",
        rate=1450.0,
        tt_buy_rate=1445.0,
        tt_sell_rate=1455.0,
        cash_buy_rate=1430.0,
        cash_sell_rate=1470.0,
        spread=10.0,
        source="koreaexim",
        fetched_at=now,
        rate_date=date.today(),
    )


@pytest.fixture
def sample_rates_history():
    """90-day mock rate values for timing/forecast tests"""
    import random
    random.seed(42)
    base = 1400.0
    rates = []
    for _ in range(90):
        base += random.gauss(0, 3)
        rates.append(round(base, 2))
    return rates


@pytest.fixture(autouse=True)
def clear_rate_cache():
    """Clear rate cache before each test"""
    rate_cache.latest.clear()
    rate_cache.updated_at = None
    yield
    rate_cache.latest.clear()
    rate_cache.updated_at = None
