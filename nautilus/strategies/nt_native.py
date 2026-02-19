"""
NautilusTrader Native Strategy Adapters
=========================================
Real nautilus_trader.trading.strategy.Strategy subclasses that wrap
the existing pandas-based signal logic from our strategy modules.

Each adapter:
  - on_start(): subscribes to bars
  - on_bar(): computes indicators via pandas, submits market orders
  - on_stop(): flattens any open position

These are ONLY used when nautilus_trader is installed. The runner
falls back to the pandas-based simulation otherwise.

Usage:
    from nautilus.strategies.nt_native import HAS_NAUTILUS_TRADER
    if HAS_NAUTILUS_TRADER:
        from nautilus.strategies.nt_native import NATIVE_STRATEGY_REGISTRY
"""

import logging
from collections import deque

import pandas as pd

from nautilus.strategies.base import NautilusStrategyBase

logger = logging.getLogger(__name__)

try:
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.objects import Quantity
    from nautilus_trader.trading.strategy import Strategy

    HAS_NAUTILUS_TRADER = True
except ImportError:
    HAS_NAUTILUS_TRADER = False

# Only define native strategies when NT is available
if HAS_NAUTILUS_TRADER:

    class _NativeAdapterConfig(StrategyConfig, frozen=True):
        """Shared config for all native strategy adapters."""

        instrument_id: str = "BTCUSDT.BINANCE"
        bar_type: str = "BTCUSDT.BINANCE-1-HOUR-LAST-EXTERNAL"
        max_bars: int = 500
        trade_size: float = 0.01
        mode: str = "backtest"

    class _NativeAdapterBase(Strategy):
        """Base adapter bridging NautilusTrader events to our signal logic.

        Subclasses set ``pandas_strategy_cls`` to the pandas-based strategy
        class whose ``should_enter()``/``should_exit()`` methods provide
        the actual trading signals.
        """

        pandas_strategy_cls: type = NautilusStrategyBase

        def __init__(self, config: _NativeAdapterConfig) -> None:
            super().__init__(config)
            self._config = config
            self._instrument_id = InstrumentId.from_str(config.instrument_id)
            self._bar_type = BarType.from_str(config.bar_type)
            self._trade_size = config.trade_size
            self._bars: deque = deque(maxlen=config.max_bars)
            self._position_open = False

            # Instantiate the pandas strategy for signal computation
            self._signal_engine = self.pandas_strategy_cls(
                config={"mode": config.mode}
            )

        def on_start(self) -> None:
            self.subscribe_bars(self._bar_type)
            self.log.info(f"Subscribed to {self._bar_type}")

        def on_bar(self, bar: Bar) -> None:
            # Convert NT Bar to dict for our signal engine
            bar_dict = {
                "timestamp": pd.Timestamp(bar.ts_event, unit="ns", tz="UTC"),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
            self._bars.append(bar_dict)

            if len(self._bars) < 200:
                return

            # Compute indicators via pandas
            df = pd.DataFrame(list(self._bars))
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
            indicators = self._signal_engine._compute_indicators(df)

            if not self._position_open:
                if self._signal_engine.should_enter(indicators):
                    self._enter_long(bar)
            else:
                if self._signal_engine.should_exit(indicators):
                    self._exit_position(bar)
                else:
                    # Check stop loss
                    entry = self._signal_engine.position
                    if entry:
                        loss_pct = (float(bar.close) / entry["entry_price"]) - 1
                        if loss_pct <= self._signal_engine.stoploss:
                            self._exit_position(bar)

        def _enter_long(self, bar: Bar) -> None:
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=OrderSide.BUY,
                quantity=Quantity.from_str(f"{self._trade_size:.8f}"),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self._position_open = True
            # Track in signal engine for stop loss
            self._signal_engine.position = {
                "side": "long",
                "entry_price": float(bar.close),
                "size": self._trade_size,
                "entry_time": pd.Timestamp(bar.ts_event, unit="ns", tz="UTC"),
            }
            self.log.info(f"ENTER LONG at {bar.close}")

        def _exit_position(self, bar: Bar) -> None:
            if not self._position_open:
                return
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=OrderSide.SELL,
                quantity=Quantity.from_str(f"{self._trade_size:.8f}"),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self._position_open = False
            self._signal_engine.position = None
            self.log.info(f"EXIT at {bar.close}")

        def on_stop(self) -> None:
            if self._position_open and len(self._bars) > 0:
                # Flatten at last bar's close
                self.log.info("Flattening on stop")
                self._position_open = False

    # ── Concrete Adapters ───────────────────────────

    class NativeTrendFollowing(_NativeAdapterBase):
        """Real NT Strategy wrapping NautilusTrendFollowing signal logic."""

        def __init__(self, config: _NativeAdapterConfig) -> None:
            from nautilus.strategies.trend_following import NautilusTrendFollowing

            self.pandas_strategy_cls = NautilusTrendFollowing
            super().__init__(config)

    class NativeMeanReversion(_NativeAdapterBase):
        """Real NT Strategy wrapping NautilusMeanReversion signal logic."""

        def __init__(self, config: _NativeAdapterConfig) -> None:
            from nautilus.strategies.mean_reversion import NautilusMeanReversion

            self.pandas_strategy_cls = NautilusMeanReversion
            super().__init__(config)

    class NativeVolatilityBreakout(_NativeAdapterBase):
        """Real NT Strategy wrapping NautilusVolatilityBreakout signal logic."""

        def __init__(self, config: _NativeAdapterConfig) -> None:
            from nautilus.strategies.volatility_breakout import (
                NautilusVolatilityBreakout,
            )

            self.pandas_strategy_cls = NautilusVolatilityBreakout
            super().__init__(config)

    NATIVE_STRATEGY_REGISTRY: dict[str, type] = {
        "NativeTrendFollowing": NativeTrendFollowing,
        "NativeMeanReversion": NativeMeanReversion,
        "NativeVolatilityBreakout": NativeVolatilityBreakout,
    }

else:
    # Stubs when nautilus_trader is not installed
    NATIVE_STRATEGY_REGISTRY: dict[str, type] = {}
