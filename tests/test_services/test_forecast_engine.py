"""Tests for forecast_engine.py Monte Carlo simulation functions"""
import math
import pytest
from app.services.forecast_engine import (
    _compute_log_returns,
    _block_bootstrap_paths,
    _generate_targets,
    _compute_probabilities,
    _compute_percentiles,
)


class TestComputeLogReturns:
    def test_basic(self):
        rates = [100, 105, 110]
        returns = _compute_log_returns(rates)
        assert len(returns) == 2
        assert abs(returns[0] - math.log(105 / 100)) < 1e-10

    def test_skips_zero_rates(self):
        rates = [100, 0, 110]
        returns = _compute_log_returns(rates)
        assert len(returns) == 0

    def test_empty(self):
        assert _compute_log_returns([]) == []

    def test_single(self):
        assert _compute_log_returns([100]) == []


class TestBlockBootstrapPaths:
    def test_path_length(self):
        log_returns = [0.01, -0.005, 0.003, 0.002, -0.001, 0.004, 0.001, -0.003, 0.005, 0.002]
        paths = _block_bootstrap_paths(log_returns, horizon=5, num_paths=10, block_len=3)
        assert len(paths) == 10
        assert all(len(p) == 5 for p in paths)

    def test_small_returns(self):
        log_returns = [0.01, -0.02]
        paths = _block_bootstrap_paths(log_returns, horizon=5, num_paths=5, block_len=3)
        assert len(paths) == 5
        assert all(len(p) == 5 for p in paths)


class TestGenerateTargets:
    def test_returns_targets_with_sufficient_data(self, sample_rates_history):
        targets = _generate_targets(1400.0, sample_rates_history, 1)
        assert len(targets) > 0
        assert all(t < 1400.0 for t in targets)
        assert targets == sorted(targets, reverse=True)

    def test_fallback_with_insufficient_data(self):
        targets = _generate_targets(1400.0, [1400, 1401, 1402], 1)
        assert len(targets) == 3
        assert all(t < 1400.0 for t in targets)


class TestComputeProbabilities:
    def test_basic_probabilities(self):
        # All paths go down -> high probability of hitting targets
        paths = [[-0.01] * 5] * 100  # 100 paths that all decline
        targets = [1380.0, 1370.0]
        results = _compute_probabilities(1400.0, paths, targets)
        assert len(results) == 2
        assert all(0 <= r["probability"] <= 1 for r in results)
        # Higher target should have >= probability of lower target
        assert results[0]["probability"] >= results[1]["probability"]

    def test_impossible_target(self):
        paths = [[0.01] * 5] * 100  # All paths go up
        results = _compute_probabilities(1400.0, paths, [1.0])  # Impossibly low target
        assert results[0]["probability"] == 0.0


class TestComputePercentiles:
    def test_returns_all_keys(self):
        paths = [[0.001] * 5] * 100
        pcts = _compute_percentiles(1400.0, paths)
        assert "p5" in pcts
        assert "p25" in pcts
        assert "p50" in pcts
        assert "p75" in pcts
        assert "p95" in pcts

    def test_ordering(self):
        paths = [[0.001 * (i % 10 - 5)] * 5 for i in range(1000)]
        pcts = _compute_percentiles(1400.0, paths)
        assert pcts["p5"] <= pcts["p25"] <= pcts["p50"] <= pcts["p75"] <= pcts["p95"]
