"""Tests for Pydantic schemas validation"""
import pytest
from pydantic import ValidationError

from app.schemas.alert import AlertCreate, AlertResponse
from app.schemas.rate import RateData


class TestAlertCreate:
    def test_valid_below(self):
        alert = AlertCreate(currency_code="usd", condition="below", threshold=1400)
        assert alert.currency_code == "USD"
        assert alert.threshold == 1400.0

    def test_valid_above(self):
        alert = AlertCreate(currency_code="EUR", condition="above", threshold=1500)
        assert alert.condition == "above"

    def test_valid_percent_change(self):
        alert = AlertCreate(currency_code="JPY", condition="percent_change", threshold=1.5)
        assert alert.threshold == 1.5

    def test_invalid_condition(self):
        with pytest.raises(ValidationError):
            AlertCreate(currency_code="USD", condition="invalid", threshold=100)

    def test_negative_threshold(self):
        with pytest.raises(ValidationError):
            AlertCreate(currency_code="USD", condition="below", threshold=-100)

    def test_zero_threshold(self):
        with pytest.raises(ValidationError):
            AlertCreate(currency_code="USD", condition="below", threshold=0)

    def test_currency_code_stripped_and_uppercased(self):
        alert = AlertCreate(currency_code="  eur  ", condition="below", threshold=100)
        assert alert.currency_code == "EUR"


class TestRateData:
    def test_minimal(self):
        from datetime import date, datetime
        import pytz
        KST = pytz.timezone("Asia/Seoul")
        rd = RateData(
            currency_code="USD",
            rate=1450.0,
            source="test",
            fetched_at=datetime.now(KST),
            rate_date=date.today(),
        )
        assert rd.base_currency == "KRW"
        assert rd.cash_buy_rate is None
        assert rd.spread is None
