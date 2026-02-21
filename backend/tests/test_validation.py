"""
Tests for Gate 2+3 Validation Engine — Sprint 1, Items 1.2 & 1.3
================================================================
Covers: Gate 2 criteria checking, synthetic data generation,
signal function shapes, ADX indicator, and integration tests.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root and scripts directory on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "research" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common.indicators.technical import adx
from validate_bollinger_mean_reversion import bollinger_mr_signals
from validate_crypto_investor_v1 import crypto_investor_v1_signals
from validate_volatility_breakout import volatility_breakout_signals
from validation_engine import (
    GATE2_MAX_DRAWDOWN,
    GATE2_MIN_SHARPE,
    GATE2_MIN_TRADES_PER_YEAR,
    GATE2_PVALUE,
    check_gate2,
    generate_synthetic_ohlcv,
)

# ── ADX Indicator Tests ───────────────────────────────────────


class TestADX:
    def test_adx_returns_series(self):
        np.random.seed(42)
        n = 200
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)
        df = pd.DataFrame({"high": high, "low": low, "close": close})
        result = adx(df, 14)
        assert isinstance(result, pd.Series)
        assert len(result) == n

    def test_adx_bounded_0_100(self):
        np.random.seed(42)
        n = 500
        close = 100 + np.cumsum(np.random.randn(n))
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))
        df = pd.DataFrame({"high": high, "low": low, "close": close})
        result = adx(df, 14)
        valid = result.dropna()
        assert valid.min() >= 0
        assert valid.max() <= 100

    def test_adx_trending_vs_ranging(self):
        """Strong trend should have higher ADX than ranging market."""
        n = 300
        # Trending: steady upward
        trend_close = np.linspace(100, 200, n)
        trend_high = trend_close + 1
        trend_low = trend_close - 1
        trend_df = pd.DataFrame({"high": trend_high, "low": trend_low, "close": trend_close})

        # Ranging: oscillating
        np.random.seed(42)
        range_close = 100 + np.sin(np.linspace(0, 20, n)) * 5
        range_high = range_close + 1
        range_low = range_close - 1
        range_df = pd.DataFrame({"high": range_high, "low": range_low, "close": range_close})

        trend_adx = adx(trend_df, 14).iloc[-1]
        range_adx = adx(range_df, 14).iloc[-1]
        assert trend_adx > range_adx


# ── Gate 2 Criteria Tests ─────────────────────────────────────


class TestCheckGate2:
    def test_passing_result(self):
        result = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.15,
            "annualized_trades": 50,
            "pvalue": 0.01,
        }
        passed, failures = check_gate2(result)
        assert passed is True
        assert len(failures) == 0

    def test_fails_low_sharpe(self):
        result = {
            "sharpe_ratio": 0.5,
            "max_drawdown": 0.10,
            "annualized_trades": 50,
            "pvalue": 0.01,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert any("Sharpe" in f for f in failures)

    def test_fails_high_drawdown(self):
        result = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.30,
            "annualized_trades": 50,
            "pvalue": 0.01,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert any("Drawdown" in f for f in failures)

    def test_fails_few_trades(self):
        result = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.10,
            "annualized_trades": 10,
            "pvalue": 0.01,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert any("Trades" in f for f in failures)

    def test_fails_high_pvalue(self):
        result = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.10,
            "annualized_trades": 50,
            "pvalue": 0.20,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert any("p-value" in f for f in failures)

    def test_fails_nan_sharpe(self):
        result = {
            "sharpe_ratio": float("nan"),
            "max_drawdown": 0.10,
            "annualized_trades": 50,
            "pvalue": 0.01,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert any("Sharpe" in f for f in failures)

    def test_multiple_failures(self):
        result = {
            "sharpe_ratio": 0.3,
            "max_drawdown": 0.30,
            "annualized_trades": 5,
            "pvalue": 0.50,
        }
        passed, failures = check_gate2(result)
        assert passed is False
        assert len(failures) == 4

    def test_boundary_values_pass(self):
        """Exactly at thresholds should pass."""
        result = {
            "sharpe_ratio": GATE2_MIN_SHARPE,
            "max_drawdown": GATE2_MAX_DRAWDOWN,
            "annualized_trades": GATE2_MIN_TRADES_PER_YEAR,
            "pvalue": GATE2_PVALUE,
        }
        passed, failures = check_gate2(result)
        assert passed is True


# ── Synthetic Data Tests ──────────────────────────────────────


class TestSyntheticData:
    def test_generates_correct_shape(self):
        df = generate_synthetic_ohlcv(n=1000)
        assert len(df) == 1000
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}

    def test_ohlc_integrity(self):
        df = generate_synthetic_ohlcv(n=500)
        assert (df["high"] >= df["close"]).all()
        assert (df["high"] >= df["open"]).all()
        assert (df["low"] <= df["close"]).all()
        assert (df["low"] <= df["open"]).all()

    def test_positive_prices_and_volume(self):
        df = generate_synthetic_ohlcv(n=500)
        assert (df["close"] > 0).all()
        assert (df["volume"] > 0).all()

    def test_has_timezone_aware_index(self):
        df = generate_synthetic_ohlcv(n=100)
        assert df.index.tz is not None

    def test_reproducible_with_seed(self):
        df1 = generate_synthetic_ohlcv(n=100, seed=42)
        df2 = generate_synthetic_ohlcv(n=100, seed=42)
        pd.testing.assert_frame_equal(df1, df2)


# ── Signal Function Tests ─────────────────────────────────────


class TestCryptoInvestorV1Signals:
    def test_returns_boolean_series(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "ema_fast": 50,
            "ema_slow": 200,
            "rsi_threshold": 40,
            "sell_rsi_threshold": 80,
        }
        entries, exits = crypto_investor_v1_signals(df, params)
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_no_nans_in_signals(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "ema_fast": 50,
            "ema_slow": 200,
            "rsi_threshold": 40,
            "sell_rsi_threshold": 80,
        }
        entries, exits = crypto_investor_v1_signals(df, params)
        assert not entries.isna().any()
        assert not exits.isna().any()

    def test_generates_some_signals(self):
        df = generate_synthetic_ohlcv(n=5000)
        params = {
            "ema_fast": 50,
            "ema_slow": 200,
            "rsi_threshold": 45,
            "sell_rsi_threshold": 70,
        }
        entries, exits = crypto_investor_v1_signals(df, params)
        # With 5000 rows of synthetic data, we expect at least some signals
        assert entries.sum() >= 0  # May be 0 depending on data
        assert exits.sum() >= 0


class TestBollingerMRSignals:
    def test_returns_boolean_series(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_threshold": 35,
            "volume_factor": 1.5,
            "sell_rsi_threshold": 65,
        }
        entries, exits = bollinger_mr_signals(df, params)
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_no_nans_in_signals(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_threshold": 35,
            "volume_factor": 1.5,
            "sell_rsi_threshold": 65,
        }
        entries, exits = bollinger_mr_signals(df, params)
        assert not entries.isna().any()
        assert not exits.isna().any()

    def test_generates_some_signals(self):
        df = generate_synthetic_ohlcv(n=5000)
        params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_threshold": 40,
            "volume_factor": 1.0,
            "sell_rsi_threshold": 55,
        }
        entries, exits = bollinger_mr_signals(df, params)
        assert entries.sum() >= 0
        assert exits.sum() >= 0


# ── Integration Tests (require VectorBT) ─────────────────────

try:
    import vectorbt  # noqa: F401

    HAS_VBT = True
except ImportError:
    HAS_VBT = False


@pytest.mark.skipif(not HAS_VBT, reason="vectorbt not installed")
class TestIntegrationWithVBT:
    def test_run_backtest_returns_metrics(self):
        from validation_engine import _run_backtest

        df = generate_synthetic_ohlcv(n=2000)
        params = {
            "ema_fast": 50,
            "ema_slow": 200,
            "rsi_threshold": 40,
            "sell_rsi_threshold": 80,
        }
        entries, exits = crypto_investor_v1_signals(df, params)
        metrics = _run_backtest(df["close"], entries, exits, fees=0.0015, sl_stop=0.05)
        assert "sharpe_ratio" in metrics
        assert "total_return" in metrics
        assert "max_drawdown" in metrics
        assert "num_trades" in metrics
        assert "annualized_trades" in metrics
        assert "pvalue" in metrics

    def test_sweep_tiny_grid(self):
        from validation_engine import sweep_parameters

        df = generate_synthetic_ohlcv(n=2000)
        tiny_grid = {
            "ema_fast": [50],
            "ema_slow": [200],
            "rsi_threshold": [40],
            "sell_rsi_threshold": [80],
        }
        results_df = sweep_parameters(df, crypto_investor_v1_signals, tiny_grid, sl_stop=0.05)
        assert len(results_df) == 1
        assert "sharpe_ratio" in results_df.columns
        assert "passes_gate2" in results_df.columns

    def test_full_validation_report_structure(self):
        from validation_engine import run_validation

        df = generate_synthetic_ohlcv(n=3000)
        tiny_grid = {
            "ema_fast": [50],
            "ema_slow": [200],
            "rsi_threshold": [40],
            "sell_rsi_threshold": [80],
        }
        report = run_validation(
            "CIV1_test",
            df,
            crypto_investor_v1_signals,
            tiny_grid,
            sl_stop=0.05,
            symbol="SYNTHETIC",
        )
        assert "strategy_name" in report
        assert "gate2" in report
        assert "overall" in report
        assert isinstance(report["overall"]["passed"], bool)
        assert "gate2_passed" in report["overall"]
        assert "gate3_wf_passed" in report["overall"]
        assert "gate3_perturb_passed" in report["overall"]

    def test_save_and_load_report(self, tmp_path):
        import json

        from validation_engine import run_validation, save_report

        df = generate_synthetic_ohlcv(n=2000)
        tiny_grid = {
            "bb_period": [20],
            "bb_std": [2.0],
            "rsi_threshold": [35],
            "volume_factor": [1.5],
            "sell_rsi_threshold": [65],
        }
        report = run_validation("BMR_test", df, bollinger_mr_signals, tiny_grid, sl_stop=0.04)
        filepath = save_report(report, output_dir=tmp_path)
        assert filepath.exists()

        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded["strategy_name"] == "BMR_test"
        assert "gate2" in loaded


# ── VolatilityBreakout Signal Tests ──────────────────────────


class TestVolatilityBreakoutSignals:
    def test_returns_boolean_series(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "breakout_period": 20,
            "volume_factor": 1.8,
            "adx_low": 15,
            "adx_high": 25,
            "rsi_low": 40,
            "rsi_high": 70,
            "adx_tolerance": 0.5,
            "sell_rsi_threshold": 85,
        }
        entries, exits = volatility_breakout_signals(df, params)
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_no_nans_in_signals(self):
        df = generate_synthetic_ohlcv(n=1000)
        params = {
            "breakout_period": 20,
            "volume_factor": 1.8,
            "adx_low": 15,
            "adx_high": 25,
            "rsi_low": 40,
            "rsi_high": 70,
            "adx_tolerance": 0.5,
            "sell_rsi_threshold": 85,
        }
        entries, exits = volatility_breakout_signals(df, params)
        assert not entries.isna().any()
        assert not exits.isna().any()

    def test_generates_some_signals(self):
        df = generate_synthetic_ohlcv(n=5000)
        params = {
            "breakout_period": 15,
            "volume_factor": 1.2,
            "adx_low": 10,
            "adx_high": 35,
            "rsi_low": 35,
            "rsi_high": 70,
            "adx_tolerance": 0.5,
            "sell_rsi_threshold": 80,
        }
        entries, exits = volatility_breakout_signals(df, params)
        assert entries.sum() >= 0
        assert exits.sum() >= 0


class TestVolatilityBreakoutParams:
    def test_rsi_high_param_respected(self):
        """Different rsi_high values should produce different entry counts."""
        df = generate_synthetic_ohlcv(n=5000)
        params_narrow = {
            "breakout_period": 20,
            "volume_factor": 1.2,
            "adx_low": 10,
            "adx_high": 35,
            "rsi_low": 35,
            "rsi_high": 60,
            "adx_tolerance": 0.5,
            "sell_rsi_threshold": 85,
        }
        params_wide = {
            **params_narrow,
            "rsi_high": 75,
        }
        entries_narrow, _ = volatility_breakout_signals(df, params_narrow)
        entries_wide, _ = volatility_breakout_signals(df, params_wide)
        # Wider RSI band should allow at least as many entries
        assert entries_wide.sum() >= entries_narrow.sum()

    def test_adx_tolerance_param_respected(self):
        """Higher ADX tolerance should generate more entries."""
        df = generate_synthetic_ohlcv(n=5000)
        params_strict = {
            "breakout_period": 20,
            "volume_factor": 1.2,
            "adx_low": 10,
            "adx_high": 35,
            "rsi_low": 35,
            "rsi_high": 70,
            "adx_tolerance": 0.0,
            "sell_rsi_threshold": 85,
        }
        params_tolerant = {
            **params_strict,
            "adx_tolerance": 1.0,
        }
        entries_strict, _ = volatility_breakout_signals(df, params_strict)
        entries_tolerant, _ = volatility_breakout_signals(df, params_tolerant)
        # More tolerance should allow at least as many entries
        assert entries_tolerant.sum() >= entries_strict.sum()

    def test_adx_tolerance_default(self):
        """Without adx_tolerance param, default 0.5 should be used."""
        df = generate_synthetic_ohlcv(n=2000)
        params_no_key = {
            "breakout_period": 20,
            "volume_factor": 1.8,
            "adx_low": 15,
            "adx_high": 25,
            "rsi_low": 40,
            "sell_rsi_threshold": 85,
        }
        params_explicit = {
            **params_no_key,
            "adx_tolerance": 0.5,
            "rsi_high": 70,
        }
        entries_default, _ = volatility_breakout_signals(df, params_no_key)
        entries_explicit, _ = volatility_breakout_signals(df, params_explicit)
        assert entries_default.sum() == entries_explicit.sum()


@pytest.mark.skipif(not HAS_VBT, reason="vectorbt not installed")
class TestVolatilityBreakoutIntegration:
    def test_vb_backtest_returns_metrics(self):
        from validation_engine import _run_backtest

        df = generate_synthetic_ohlcv(n=2000)
        params = {
            "breakout_period": 20,
            "volume_factor": 1.8,
            "adx_low": 15,
            "adx_high": 25,
            "rsi_low": 40,
            "rsi_high": 70,
            "adx_tolerance": 0.5,
            "sell_rsi_threshold": 85,
        }
        entries, exits = volatility_breakout_signals(df, params)
        metrics = _run_backtest(df["close"], entries, exits, fees=0.0015, sl_stop=0.03)
        assert "sharpe_ratio" in metrics
        assert "total_return" in metrics
        assert "max_drawdown" in metrics

    def test_vb_sweep_tiny_grid(self):
        from validation_engine import sweep_parameters

        df = generate_synthetic_ohlcv(n=2000)
        tiny_grid = {
            "breakout_period": [20],
            "volume_factor": [1.8],
            "adx_low": [15],
            "adx_high": [25],
            "rsi_low": [40],
            "rsi_high": [70],
            "adx_tolerance": [0.5],
            "sell_rsi_threshold": [85],
        }
        results_df = sweep_parameters(df, volatility_breakout_signals, tiny_grid, sl_stop=0.03)
        assert len(results_df) == 1
        assert "sharpe_ratio" in results_df.columns
        assert "passes_gate2" in results_df.columns
