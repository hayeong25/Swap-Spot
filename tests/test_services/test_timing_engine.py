"""Tests for timing_engine.py signal functions and timing logic"""
import pytest
from app.services.timing_engine import (
    moving_average_signal,
    percentile_signal,
    bollinger_signal,
    compute_percentile,
    compute_ma,
    compute_target_rate,
    compute_timing,
    _compute_urgency,
    _adjust_recommendation,
)


class TestMovingAverageSignal:
    def test_returns_hold_when_insufficient_data(self):
        assert moving_average_signal([1, 2, 3]) == "HOLD"

    def test_returns_wait_when_short_below_long(self):
        # short MA significantly below long MA -> WAIT (rate is dropping)
        rates = [100] * 15 + [90] * 5  # long=~96.7, short=90
        assert moving_average_signal(rates) == "WAIT"

    def test_returns_buy_when_short_above_long(self):
        rates = [90] * 15 + [100] * 5  # long=~93.3, short=100
        assert moving_average_signal(rates) == "BUY"

    def test_returns_hold_when_close(self):
        rates = [100.0] * 20
        assert moving_average_signal(rates) == "HOLD"


class TestPercentileSignal:
    def test_returns_hold_when_insufficient_data(self):
        assert percentile_signal(100, [90, 95]) == "HOLD"

    def test_returns_buy_when_low_percentile(self):
        rates = list(range(100, 200))
        assert percentile_signal(105, rates) == "BUY"

    def test_returns_wait_when_high_percentile(self):
        rates = list(range(100, 200))
        assert percentile_signal(195, rates) == "WAIT"

    def test_returns_hold_when_mid_percentile(self):
        rates = list(range(100, 200))
        assert percentile_signal(150, rates) == "HOLD"


class TestBollingerSignal:
    def test_returns_hold_when_insufficient_data(self):
        assert bollinger_signal([1, 2, 3]) == "HOLD"

    def test_returns_buy_when_below_lower_band(self):
        # Create rates where current is very low
        rates = [100.0] * 19 + [80.0]
        assert bollinger_signal(rates) == "BUY"

    def test_returns_wait_when_above_upper_band(self):
        rates = [100.0] * 19 + [120.0]
        assert bollinger_signal(rates) == "WAIT"

    def test_returns_hold_when_zero_std(self):
        rates = [100.0] * 20
        assert bollinger_signal(rates) == "HOLD"


class TestComputePercentile:
    def test_empty_rates(self):
        assert compute_percentile(100, []) == 50.0

    def test_at_minimum(self):
        assert compute_percentile(1, list(range(1, 101))) == 0.0

    def test_at_maximum(self):
        # bisect_left(100) in range(1,101) = 99, 99/100 = 99%
        assert compute_percentile(100, list(range(1, 101))) == 99.0


class TestComputeMA:
    def test_insufficient_data(self):
        assert compute_ma([100.0], 5) == 100.0

    def test_exact_window(self):
        assert compute_ma([10, 20, 30], 3) == 20.0


class TestComputeTargetRate:
    def test_insufficient_data(self):
        assert compute_target_rate([1, 2, 3]) is None

    def test_returns_target(self, sample_rates_history):
        target = compute_target_rate(sample_rates_history)
        assert target is not None
        assert isinstance(target, float)
        assert target < max(sample_rates_history)


class TestUrgency:
    def test_immediate(self):
        assert _compute_urgency(3) == "immediate"

    def test_urgent(self):
        assert _compute_urgency(10) == "urgent"

    def test_caution(self):
        assert _compute_urgency(20) == "caution"

    def test_relaxed(self):
        assert _compute_urgency(60) == "relaxed"


class TestAdjustRecommendation:
    def test_immediate_always_buy(self):
        assert _adjust_recommendation("WAIT", "immediate") == "BUY"
        assert _adjust_recommendation("HOLD", "immediate") == "BUY"

    def test_urgent_hold_becomes_buy(self):
        assert _adjust_recommendation("HOLD", "urgent") == "BUY"
        assert _adjust_recommendation("WAIT", "urgent") == "WAIT"

    def test_caution_wait_becomes_hold(self):
        assert _adjust_recommendation("WAIT", "caution") == "HOLD"
        assert _adjust_recommendation("BUY", "caution") == "BUY"

    def test_relaxed_no_change(self):
        assert _adjust_recommendation("WAIT", "relaxed") == "WAIT"
        assert _adjust_recommendation("BUY", "relaxed") == "BUY"


class TestComputeTiming:
    @pytest.mark.asyncio
    async def test_with_provided_rates(self, sample_rates_history):
        result = await compute_timing("USD", _rates=sample_rates_history)
        assert result["currency_code"] == "USD"
        assert result["recommendation"] in ("BUY", "HOLD", "WAIT")
        assert 0 <= result["confidence"] <= 1
        assert "moving_average" in result["signals"]
        assert "percentile" in result["signals"]
        assert "bollinger" in result["signals"]
        assert result["ma_short"] > 0
        assert result["ma_long"] > 0

    @pytest.mark.asyncio
    async def test_empty_rates(self):
        result = await compute_timing("XYZ", _rates=[])
        assert result["recommendation"] == "HOLD"
        assert result["confidence"] == 0

    @pytest.mark.asyncio
    async def test_does_not_mutate_input(self, sample_rates_history):
        original_len = len(sample_rates_history)
        await compute_timing("USD", _rates=sample_rates_history)
        assert len(sample_rates_history) == original_len
