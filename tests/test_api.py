"""Tests for API endpoints"""
import pytest
from datetime import date, datetime
from unittest.mock import patch, AsyncMock

import pytz
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.rate import RateData
from app.services.rate_service import rate_cache

KST = pytz.timezone("Asia/Seoul")


def _seed_cache():
    """Directly seed rate cache for testing without DB"""
    now = datetime.now(KST)
    today = date.today()
    currencies = {
        "USD": 1450.0,
        "EUR": 1550.0,
        "JPY": 950.0,
        "GBP": 1800.0,
        "CNH": 200.0,
    }
    for code, rate_val in currencies.items():
        rate_cache.latest[code] = RateData(
            currency_code=code,
            rate=rate_val,
            source="test",
            fetched_at=now,
            rate_date=today,
        )
    rate_cache.updated_at = now


@pytest.fixture(autouse=True)
def seed_cache():
    _seed_cache()
    yield
    rate_cache.latest.clear()


class TestRatesAPI:
    @pytest.mark.asyncio
    async def test_get_latest_rates(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/latest")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
            codes = {r["currency_code"] for r in data}
            assert "USD" in codes

    @pytest.mark.asyncio
    async def test_get_timing(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/timing/USD")
            assert resp.status_code == 200
            data = resp.json()
            assert data["currency_code"] == "USD"
            assert data["recommendation"] in ("BUY", "HOLD", "WAIT")
            assert "signals" in data

    @pytest.mark.asyncio
    async def test_get_timing_unknown_currency(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/timing/XYZ")
            assert resp.status_code == 200
            data = resp.json()
            assert data["recommendation"] == "HOLD"

    @pytest.mark.asyncio
    async def test_get_history_days_validation(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/USD?days=0")
            assert resp.status_code == 422  # validation error

            resp = await client.get("/api/rates/USD?days=500")
            assert resp.status_code == 422

            resp = await client.get("/api/rates/USD?days=30")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_lowercase_currency(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/usd?days=7")
            assert resp.status_code == 200
            assert resp.json()["currency_code"] == "USD"


    @pytest.mark.asyncio
    async def test_invalid_currency_code_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/timing/123")
            assert resp.status_code == 400

            resp = await client.get("/api/rates/timing/USD;DROP")
            assert resp.status_code == 400

            resp = await client.get("/api/rates/timing/TOOLONG")
            assert resp.status_code == 400

            # Valid ones still work
            resp = await client.get("/api/rates/timing/USD")
            assert resp.status_code == 200


class TestAlertsAPI:
    @pytest.mark.asyncio
    async def test_create_and_list_alert(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            resp = await client.post("/api/alerts/", json={
                "currency_code": "USD",
                "condition": "below",
                "threshold": 1400.0,
            })
            assert resp.status_code == 200
            alert = resp.json()
            assert alert["currency_code"] == "USD"
            assert alert["threshold"] == 1400.0
            alert_id = alert["id"]

            # List
            resp = await client.get("/api/alerts/")
            assert resp.status_code == 200
            alerts = resp.json()
            ids = [a["id"] for a in alerts]
            assert alert_id in ids

            # Delete
            resp = await client.delete(f"/api/alerts/{alert_id}")
            assert resp.status_code == 200

            # Verify deleted
            resp = await client.delete(f"/api/alerts/{alert_id}")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_alert_validation(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # negative threshold
            resp = await client.post("/api/alerts/", json={
                "currency_code": "USD",
                "condition": "below",
                "threshold": -100,
            })
            assert resp.status_code == 422

            # invalid condition
            resp = await client.post("/api/alerts/", json={
                "currency_code": "USD",
                "condition": "invalid",
                "threshold": 1400,
            })
            assert resp.status_code == 422


class TestStaticFiles:
    @pytest.mark.asyncio
    async def test_index_html(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "Swap Spot" in resp.text

    @pytest.mark.asyncio
    async def test_css_loads(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/css/style.css")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_js_loads(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/js/app.js")
            assert resp.status_code == 200
