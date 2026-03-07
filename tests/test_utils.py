"""Tests for utility modules"""
import pytest
from datetime import date, datetime, time
from unittest.mock import patch

import pytz

from app.utils.business_hours import (
    is_banking_hours,
    _is_korean_holiday,
    BANK_OPEN,
    BANK_CLOSE,
    KST,
)
from app.utils.currency import MAJOR_CURRENCIES, format_rate


class TestIsKoreanHoliday:
    def test_fixed_holiday(self):
        assert _is_korean_holiday(date(2026, 1, 1)) is True   # 신정
        assert _is_korean_holiday(date(2027, 3, 1)) is True   # 삼일절
        assert _is_korean_holiday(date(2025, 12, 25)) is True  # 크리스마스

    def test_lunar_holiday_2026(self):
        assert _is_korean_holiday(date(2026, 2, 17)) is True   # 설날
        assert _is_korean_holiday(date(2026, 9, 25)) is True   # 추석

    def test_lunar_holiday_2027(self):
        assert _is_korean_holiday(date(2027, 2, 7)) is True    # 설날
        assert _is_korean_holiday(date(2027, 10, 15)) is True  # 추석

    def test_normal_day(self):
        assert _is_korean_holiday(date(2026, 4, 15)) is False

    def test_unknown_year_lunar(self):
        # 2030: no lunar holidays defined -> only fixed holidays
        assert _is_korean_holiday(date(2030, 1, 1)) is True
        assert _is_korean_holiday(date(2030, 4, 15)) is False


class TestIsBankingHours:
    def _mock_kst_datetime(self, year, month, day, hour, minute):
        return KST.localize(datetime(year, month, day, hour, minute, 0))

    def test_weekday_during_hours(self):
        # 2026-03-02 is Monday
        with patch("app.utils.business_hours.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_kst_datetime(2026, 3, 2, 10, 30)
            assert is_banking_hours() is True

    def test_weekday_before_hours(self):
        with patch("app.utils.business_hours.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_kst_datetime(2026, 3, 2, 7, 0)
            assert is_banking_hours() is False

    def test_weekday_after_hours(self):
        with patch("app.utils.business_hours.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_kst_datetime(2026, 3, 2, 16, 0)
            assert is_banking_hours() is False

    def test_weekend(self):
        # 2026-03-07 is Saturday
        with patch("app.utils.business_hours.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_kst_datetime(2026, 3, 7, 10, 30)
            assert is_banking_hours() is False

    def test_holiday(self):
        # 2026-03-01 is Sunday + 삼일절, but let's test 2026-01-01 (Thursday)
        with patch("app.utils.business_hours.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_kst_datetime(2026, 1, 1, 10, 30)
            assert is_banking_hours() is False


class TestMajorCurrencies:
    def test_has_11_currencies(self):
        assert len(MAJOR_CURRENCIES) == 11

    def test_cnh_present(self):
        assert "CNH" in MAJOR_CURRENCIES

    def test_cny_not_present(self):
        assert "CNY" not in MAJOR_CURRENCIES

    def test_all_have_required_fields(self):
        for code, info in MAJOR_CURRENCIES.items():
            assert "name" in info, f"{code} missing 'name'"
            assert "symbol" in info, f"{code} missing 'symbol'"
            assert "unit" in info, f"{code} missing 'unit'"

    def test_jpy_unit_100(self):
        assert MAJOR_CURRENCIES["JPY"]["unit"] == 100


class TestFormatRate:
    def test_normal_currency(self):
        assert format_rate(1450.50, "USD") == "1,450.50"

    def test_unit_100_currency(self):
        result = format_rate(950.25, "JPY")
        assert "/100" in result

    def test_unknown_currency(self):
        result = format_rate(100.0, "XYZ")
        assert "100.00" in result
