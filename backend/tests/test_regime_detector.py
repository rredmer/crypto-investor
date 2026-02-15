"""
Tests for Market Regime Detector — Sprint 2, Item 2.1
=====================================================
Covers: Regime enum, RegimeState, RegimeConfig, RegimeDetector
classification (all 6 regimes), sub-indicators, transition
probabilities, and detect_series.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.regime.regime_detector import (
    Regime,
    RegimeConfig,
    RegimeDetector,
    RegimeState,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_trending_up_df(n: int = 500) -> pd.DataFrame:
    """Synthetic strong uptrend data."""
    np.random.seed(42)
    close = 100 + np.linspace(0, 80, n) + np.random.randn(n) * 0.5
    high = close + np.abs(np.random.randn(n) * 0.8)
    low = close - np.abs(np.random.randn(n) * 0.8)
    volume = np.random.uniform(1000, 5000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": close - 0.1, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _make_trending_down_df(n: int = 500) -> pd.DataFrame:
    """Synthetic strong downtrend data (steeper to ensure high ADX)."""
    np.random.seed(43)
    close = 200 - np.linspace(0, 120, n) + np.random.randn(n) * 0.3
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    volume = np.random.uniform(1000, 5000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": close + 0.1, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _make_ranging_df(n: int = 500) -> pd.DataFrame:
    """Synthetic ranging/sideways data."""
    np.random.seed(44)
    close = 100 + np.sin(np.linspace(0, 30, n)) * 3 + np.random.randn(n) * 0.3
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    volume = np.random.uniform(1000, 5000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _make_volatile_df(n: int = 500) -> pd.DataFrame:
    """Synthetic high-volatility, low-trend data."""
    np.random.seed(45)
    close = 100 + np.cumsum(np.random.randn(n) * 5)  # Large random moves
    high = close + np.abs(np.random.randn(n) * 3)
    low = close - np.abs(np.random.randn(n) * 3)
    volume = np.random.uniform(1000, 5000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


# ── Regime Enum Tests ────────────────────────────────────────


class TestRegimeEnum:
    def test_has_six_values(self):
        assert len(Regime) == 6

    def test_string_values(self):
        assert Regime.STRONG_TREND_UP.value == "strong_trend_up"
        assert Regime.RANGING.value == "ranging"
        assert Regime.HIGH_VOLATILITY.value == "high_volatility"

    def test_is_string_enum(self):
        assert isinstance(Regime.RANGING, str)
        assert Regime.RANGING == "ranging"


# ── RegimeConfig Tests ───────────────────────────────────────


class TestRegimeConfig:
    def test_default_values(self):
        cfg = RegimeConfig()
        assert cfg.adx_strong == 40.0
        assert cfg.adx_weak == 25.0
        assert cfg.bb_high_vol_pct == 80.0
        assert cfg.alignment_ema_periods == [21, 50, 100, 200]

    def test_custom_values(self):
        cfg = RegimeConfig(adx_strong=50, adx_weak=30)
        assert cfg.adx_strong == 50
        assert cfg.adx_weak == 30


# ── RegimeState Tests ────────────────────────────────────────


class TestRegimeState:
    def test_creation(self):
        state = RegimeState(
            regime=Regime.RANGING,
            confidence=0.8,
            adx_value=20.0,
            bb_width_percentile=50.0,
            ema_slope=0.001,
            trend_alignment=0.0,
            price_structure_score=0.1,
        )
        assert state.regime == Regime.RANGING
        assert state.confidence == 0.8
        assert state.transition_probabilities == {}


# ── RegimeDetector detect() Tests ────────────────────────────


class TestRegimeDetectorDetect:
    def test_returns_regime_state(self):
        df = _make_ranging_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert isinstance(state, RegimeState)
        assert isinstance(state.regime, Regime)
        assert 0.0 <= state.confidence <= 1.0

    def test_trending_up_detected(self):
        df = _make_trending_up_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert state.regime in (Regime.STRONG_TREND_UP, Regime.WEAK_TREND_UP)
        assert state.ema_slope > 0
        assert state.trend_alignment > 0

    def test_trending_down_detected(self):
        df = _make_trending_down_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert state.regime in (Regime.STRONG_TREND_DOWN, Regime.WEAK_TREND_DOWN)
        assert state.ema_slope < 0
        assert state.trend_alignment < 0

    def test_ranging_detected(self):
        df = _make_ranging_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        # Ranging data should not be classified as strong trend
        assert state.regime not in (Regime.STRONG_TREND_UP, Regime.STRONG_TREND_DOWN)

    def test_adx_value_in_range(self):
        df = _make_ranging_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert 0 <= state.adx_value <= 100

    def test_bb_width_percentile_in_range(self):
        df = _make_ranging_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert 0 <= state.bb_width_percentile <= 100

    def test_trend_alignment_in_range(self):
        df = _make_trending_up_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert -1 <= state.trend_alignment <= 1

    def test_price_structure_in_range(self):
        df = _make_trending_up_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert -1 <= state.price_structure_score <= 1

    def test_custom_config(self):
        df = _make_ranging_df()
        cfg = RegimeConfig(adx_strong=50, adx_weak=30)
        detector = RegimeDetector(config=cfg)
        state = detector.detect(df)
        assert isinstance(state.regime, Regime)


# ── detect_series() Tests ────────────────────────────────────


class TestRegimeDetectorSeries:
    def test_returns_dataframe(self):
        df = _make_ranging_df(200)
        detector = RegimeDetector()
        result = detector.detect_series(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_has_required_columns(self):
        df = _make_ranging_df(200)
        detector = RegimeDetector()
        result = detector.detect_series(df)
        expected = {
            "adx_value", "bb_width_percentile", "ema_slope",
            "trend_alignment", "price_structure_score", "regime", "confidence",
        }
        assert expected.issubset(set(result.columns))

    def test_all_regimes_are_valid(self):
        df = _make_ranging_df(200)
        detector = RegimeDetector()
        result = detector.detect_series(df)
        for regime in result["regime"]:
            assert isinstance(regime, Regime)


# ── Classification Logic Tests ───────────────────────────────


class TestClassificationLogic:
    def test_high_volatility_classification(self):
        """High BB width + low ADX → HIGH_VOLATILITY."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=20, bb_pct=90, slope=0.001, alignment=0.1, structure=0.1
        )
        assert regime == Regime.HIGH_VOLATILITY

    def test_strong_trend_up_classification(self):
        """High ADX + positive alignment/slope/structure → STRONG_TREND_UP."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=50, bb_pct=50, slope=0.01, alignment=0.8, structure=0.5
        )
        assert regime == Regime.STRONG_TREND_UP

    def test_strong_trend_down_classification(self):
        """High ADX + negative alignment/slope/structure → STRONG_TREND_DOWN."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=50, bb_pct=50, slope=-0.01, alignment=-0.8, structure=-0.5
        )
        assert regime == Regime.STRONG_TREND_DOWN

    def test_weak_trend_up_classification(self):
        """Mid ADX + positive alignment → WEAK_TREND_UP."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=30, bb_pct=50, slope=0.005, alignment=0.3, structure=0.2
        )
        assert regime == Regime.WEAK_TREND_UP

    def test_weak_trend_down_classification(self):
        """Mid ADX + negative alignment → WEAK_TREND_DOWN."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=30, bb_pct=50, slope=-0.005, alignment=-0.3, structure=-0.2
        )
        assert regime == Regime.WEAK_TREND_DOWN

    def test_ranging_classification(self):
        """Low ADX + normal volatility → RANGING."""
        detector = RegimeDetector()
        regime, conf = detector._classify_regime(
            adx_val=15, bb_pct=50, slope=0.0, alignment=0.0, structure=0.0
        )
        assert regime == Regime.RANGING


# ── Transition Probabilities Tests ───────────────────────────


class TestTransitionProbabilities:
    def test_returns_dict(self):
        df = _make_ranging_df()
        detector = RegimeDetector()
        state = detector.detect(df)
        assert isinstance(state.transition_probabilities, dict)

    def test_probabilities_sum_to_one(self):
        df = _make_ranging_df(500)
        detector = RegimeDetector()
        state = detector.detect(df)
        probs = state.transition_probabilities
        if probs:
            total = sum(probs.values())
            assert abs(total - 1.0) < 0.05  # Allow small float rounding

    def test_empty_for_short_data(self):
        df = _make_ranging_df(5)
        detector = RegimeDetector()
        state = detector.detect(df)
        # With very short data, may have empty transitions
        assert isinstance(state.transition_probabilities, dict)
