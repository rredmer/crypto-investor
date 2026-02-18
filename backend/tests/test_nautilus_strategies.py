"""
Tests for NautilusTrader strategies (Tier 3)
=============================================
Covers: strategy registry, base class, indicator computation,
data conversion, backtesting, and backend integration.

Engine-level tests are skipped when nautilus_trader is not installed.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Helpers ──────────────────────────────────────────


def _make_ohlcv(n: int = 300, start_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    returns = np.random.normal(0.0001, 0.01, n)
    prices = start_price * np.exp(np.cumsum(returns))
    noise = np.random.uniform(0.998, 1.002, n)
    return pd.DataFrame(
        {
            "open": prices * noise,
            "high": prices * np.random.uniform(1.001, 1.02, n),
            "low": prices * np.random.uniform(0.98, 0.999, n),
            "close": prices,
            "volume": np.random.lognormal(10, 1, n),
        },
        index=timestamps,
    )


def _bars_from_df(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of bar dicts."""
    bars = []
    for ts, row in df.iterrows():
        bars.append(
            {
                "timestamp": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    return bars


# ── Registry Tests ───────────────────────────────────


class TestNautilusRegistry:
    def test_registry_has_three_strategies(self):
        from nautilus.strategies import STRATEGY_REGISTRY

        assert len(STRATEGY_REGISTRY) == 3

    def test_registry_keys(self):
        from nautilus.strategies import STRATEGY_REGISTRY

        expected = {
            "NautilusTrendFollowing",
            "NautilusMeanReversion",
            "NautilusVolatilityBreakout",
        }
        assert set(STRATEGY_REGISTRY.keys()) == expected

    def test_all_strategies_are_classes(self):
        from nautilus.strategies import STRATEGY_REGISTRY

        for name, cls in STRATEGY_REGISTRY.items():
            assert isinstance(cls, type), f"{name} is not a class"

    def test_list_nautilus_strategies(self):
        from nautilus.nautilus_runner import list_nautilus_strategies

        names = list_nautilus_strategies()
        assert len(names) == 3
        assert "NautilusTrendFollowing" in names


# ── Base Class Tests ─────────────────────────────────


class TestNautilusBase:
    def test_base_init_defaults(self):
        from nautilus.strategies.base import NautilusStrategyBase

        s = NautilusStrategyBase()
        assert s.position is None
        assert len(s.trades) == 0
        assert len(s.bars) == 0

    def test_base_bars_bounded(self):
        from nautilus.strategies.base import NautilusStrategyBase

        s = NautilusStrategyBase(config={"max_bars": 10})
        assert s.bars.maxlen == 10

    def test_bars_to_df(self):
        from nautilus.strategies.base import NautilusStrategyBase

        s = NautilusStrategyBase()
        df = _make_ohlcv(5)
        for bar in _bars_from_df(df):
            s.bars.append(bar)
        result = s._bars_to_df()
        assert len(result) == 5
        assert "close" in result.columns

    def test_indicator_computation(self):
        from nautilus.strategies.base import NautilusStrategyBase

        s = NautilusStrategyBase()
        df = _make_ohlcv(250)
        for bar in _bars_from_df(df):
            s.bars.append(bar)
        indicators = s._compute_indicators(s._bars_to_df())
        assert "rsi_14" in indicators.index
        assert "ema_50" in indicators.index
        assert "atr_14" in indicators.index
        assert "bb_upper" in indicators.index

    def test_on_stop_flattens_position(self):
        from nautilus.strategies.base import NautilusStrategyBase

        s = NautilusStrategyBase()
        df = _make_ohlcv(5)
        for bar in _bars_from_df(df):
            s.bars.append(bar)
        s.position = {
            "side": "long",
            "entry_price": 100.0,
            "size": 1.0,
            "entry_time": df.index[0],
        }
        trade = s.on_stop()
        assert trade is not None
        assert s.position is None
        assert len(s.trades) == 1


# ── Strategy Signal Tests ────────────────────────────


class TestTrendFollowing:
    def test_instantiation(self):
        from nautilus.strategies.trend_following import NautilusTrendFollowing

        s = NautilusTrendFollowing()
        assert s.name == "NautilusTrendFollowing"
        assert s.stoploss == -0.05

    def test_processes_bars_without_error(self):
        from nautilus.strategies.trend_following import NautilusTrendFollowing

        s = NautilusTrendFollowing(config={"mode": "backtest"})
        df = _make_ohlcv(250)
        for bar in _bars_from_df(df):
            s.on_bar(bar)
        # Should not crash; may or may not produce trades depending on data


class TestMeanReversion:
    def test_instantiation(self):
        from nautilus.strategies.mean_reversion import NautilusMeanReversion

        s = NautilusMeanReversion()
        assert s.name == "NautilusMeanReversion"
        assert s.stoploss == -0.04

    def test_processes_bars_without_error(self):
        from nautilus.strategies.mean_reversion import NautilusMeanReversion

        s = NautilusMeanReversion(config={"mode": "backtest"})
        df = _make_ohlcv(250)
        for bar in _bars_from_df(df):
            s.on_bar(bar)


class TestVolatilityBreakout:
    def test_instantiation(self):
        from nautilus.strategies.volatility_breakout import NautilusVolatilityBreakout

        s = NautilusVolatilityBreakout()
        assert s.name == "NautilusVolatilityBreakout"
        assert s.stoploss == -0.03

    def test_processes_bars_without_error(self):
        from nautilus.strategies.volatility_breakout import NautilusVolatilityBreakout

        s = NautilusVolatilityBreakout(config={"mode": "backtest"})
        df = _make_ohlcv(250)
        for bar in _bars_from_df(df):
            s.on_bar(bar)


# ── Data Conversion Tests ────────────────────────────


class TestNautilusDataConversion:
    def test_csv_conversion(self, tmp_path):
        """Test Nautilus CSV conversion with mock data."""
        from common.data_pipeline.pipeline import save_ohlcv
        from nautilus.nautilus_runner import convert_ohlcv_to_nautilus_csv

        df = _make_ohlcv(50)
        save_ohlcv(df, "TEST/USDT", "1h", "testexch")

        path = convert_ohlcv_to_nautilus_csv("TEST/USDT", "1h", "testexch")
        assert path is not None
        assert path.exists()

        csv_df = pd.read_csv(path)
        assert len(csv_df) == 50
        assert "bar_type" in csv_df.columns


# ── Backend Integration Tests ────────────────────────


class TestBacktestServiceNautilus:
    def test_list_strategies_includes_nautilus(self):
        from core.platform_bridge import ensure_platform_imports

        ensure_platform_imports()
        from analysis.services.backtest import BacktestService

        strategies = BacktestService.list_strategies()
        nautilus_strategies = [s for s in strategies if s["framework"] == "nautilus"]
        assert len(nautilus_strategies) == 3
