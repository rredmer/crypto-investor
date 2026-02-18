"""
NautilusTrader Strategy Base Class
===================================
Shared functionality for all Nautilus strategies:
- Indicator computation via common.indicators.technical
- Risk API gating (same pattern as Freqtrade strategies)
- ATR-based position sizing
- Bounded bar buffer for 8GB Jetson
"""

import logging
from collections import deque
from typing import Optional

import pandas as pd

from common.indicators.technical import (
    ema,
    sma,
    rsi,
    macd,
    bollinger_bands,
    atr_indicator,
    adx,
)

logger = logging.getLogger(__name__)

# Maximum bars to keep in memory (bounded for Jetson 8GB)
MAX_BARS = 500

# Risk API defaults (same as Freqtrade strategies)
RISK_API_URL = "http://127.0.0.1:8000"
RISK_PORTFOLIO_ID = 1


class NautilusStrategyBase:
    """Base class for NautilusTrader strategies.

    Provides indicator computation, risk gating, and position sizing
    that mirror the Freqtrade strategy patterns. Subclasses implement
    ``should_enter()`` and ``should_exit()`` with pandas-based logic.

    In backtest mode, the runner calls ``on_bar()`` for each bar. The
    strategy maintains a rolling window of OHLCV data and evaluates
    entry/exit signals on each bar.
    """

    name: str = "base"
    timeframe: str = "1h"
    stoploss: float = -0.05
    atr_multiplier: float = 2.0

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.bars: deque = deque(maxlen=self.config.get("max_bars", MAX_BARS))
        self.position: Optional[dict] = None  # {side, entry_price, size, entry_time}
        self.trades: list[dict] = []
        self.risk_api_url = self.config.get("risk_api_url", RISK_API_URL)
        self.risk_portfolio_id = self.config.get("risk_portfolio_id", RISK_PORTFOLIO_ID)

    def on_bar(self, bar: dict) -> Optional[dict]:
        """Process a single OHLCV bar. Returns a trade dict if a fill occurred."""
        self.bars.append(bar)

        # Need enough bars for indicator computation
        if len(self.bars) < 200:
            return None

        df = self._bars_to_df()
        indicators = self._compute_indicators(df)

        if self.position is None:
            if self.should_enter(indicators):
                entry_price = bar["close"]
                size = self._compute_position_size(indicators, entry_price)
                if size > 0 and self._check_risk_gate(bar, entry_price, size):
                    self.position = {
                        "side": "long",
                        "entry_price": entry_price,
                        "size": size,
                        "entry_time": bar["timestamp"],
                    }
        else:
            if self.should_exit(indicators):
                exit_price = bar["close"]
                pnl = (exit_price - self.position["entry_price"]) * self.position["size"]
                pnl_pct = (exit_price / self.position["entry_price"]) - 1
                trade = {
                    "entry_time": self.position["entry_time"],
                    "exit_time": bar["timestamp"],
                    "side": self.position["side"],
                    "entry_price": self.position["entry_price"],
                    "exit_price": exit_price,
                    "size": self.position["size"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                }
                self.trades.append(trade)
                self.position = None
                return trade

            # Check stop loss
            current_price = bar["close"]
            loss_pct = (current_price / self.position["entry_price"]) - 1
            if loss_pct <= self.stoploss:
                pnl = (current_price - self.position["entry_price"]) * self.position["size"]
                trade = {
                    "entry_time": self.position["entry_time"],
                    "exit_time": bar["timestamp"],
                    "side": self.position["side"],
                    "entry_price": self.position["entry_price"],
                    "exit_price": current_price,
                    "size": self.position["size"],
                    "pnl": pnl,
                    "pnl_pct": loss_pct,
                }
                self.trades.append(trade)
                self.position = None
                return trade

        return None

    def on_stop(self) -> Optional[dict]:
        """Flatten any open position at the last bar's close."""
        if self.position is not None and len(self.bars) > 0:
            last_bar = self.bars[-1]
            exit_price = last_bar["close"]
            pnl = (exit_price - self.position["entry_price"]) * self.position["size"]
            pnl_pct = (exit_price / self.position["entry_price"]) - 1
            trade = {
                "entry_time": self.position["entry_time"],
                "exit_time": last_bar["timestamp"],
                "side": self.position["side"],
                "entry_price": self.position["entry_price"],
                "exit_price": exit_price,
                "size": self.position["size"],
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            }
            self.trades.append(trade)
            self.position = None
            return trade
        return None

    def should_enter(self, indicators: pd.Series) -> bool:
        """Override in subclass: return True to enter a long position."""
        raise NotImplementedError

    def should_exit(self, indicators: pd.Series) -> bool:
        """Override in subclass: return True to exit the current position."""
        raise NotImplementedError

    def _bars_to_df(self) -> pd.DataFrame:
        """Convert bar buffer to a pandas DataFrame."""
        df = pd.DataFrame(list(self.bars))
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
        return df

    def _compute_indicators(self, df: pd.DataFrame) -> pd.Series:
        """Compute standard indicators and return the last row as a Series."""
        result = df.copy()

        # EMAs
        for p in [7, 14, 21, 50, 100, 200]:
            result[f"ema_{p}"] = ema(result["close"], p)
            result[f"sma_{p}"] = sma(result["close"], p)

        # RSI
        result["rsi_14"] = rsi(result["close"], 14)

        # MACD
        macd_df = macd(result["close"])
        result["macd"] = macd_df["macd"]
        result["macd_signal"] = macd_df["macd_signal"]
        result["macd_hist"] = macd_df["macd_hist"]

        # Bollinger Bands
        bb = bollinger_bands(result["close"], 20, 2.0)
        result["bb_upper"] = bb["bb_upper"]
        result["bb_mid"] = bb["bb_mid"]
        result["bb_lower"] = bb["bb_lower"]
        result["bb_width"] = bb["bb_width"]

        # ATR
        result["atr_14"] = atr_indicator(result, 14)

        # ADX
        result["adx_14"] = adx(result, 14)

        # Volume
        result["volume_sma_20"] = sma(result["volume"], 20)
        result["volume_ratio"] = result["volume"] / result["volume_sma_20"]

        # N-period highs (for breakout)
        result["high_20"] = result["high"].rolling(window=20).max()

        return result.iloc[-1]

    def _compute_position_size(self, indicators: pd.Series, entry_price: float) -> float:
        """ATR-based position sizing. Returns size in base currency units."""
        atr = indicators.get("atr_14", 0)
        if atr <= 0 or entry_price <= 0:
            return 0.0

        # Risk per trade: 2% of notional per ATR unit
        risk_per_unit = atr * abs(self.atr_multiplier)
        if risk_per_unit <= 0:
            return 0.0

        initial_balance = self.config.get("initial_balance", 10000.0)
        risk_amount = initial_balance * 0.02  # 2% risk
        size = risk_amount / risk_per_unit
        return round(size, 6)

    def _check_risk_gate(self, bar: dict, entry_price: float, size: float) -> bool:
        """Call the backend risk API to approve the trade. Skip in backtest mode."""
        if self.config.get("mode") == "backtest":
            return True

        try:
            import requests

            stop_loss_price = entry_price * (1 + self.stoploss)
            resp = requests.post(
                f"{self.risk_api_url}/api/risk/{self.risk_portfolio_id}/check-trade",
                json={
                    "symbol": self.config.get("symbol", "BTC/USDT"),
                    "side": "long",
                    "size": size,
                    "entry_price": entry_price,
                    "stop_loss_price": stop_loss_price,
                },
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("approved", False):
                    logger.warning(f"Risk gate REJECTED: {data.get('reason')}")
                    return False
                return True
            logger.warning(f"Risk API returned {resp.status_code}, rejecting trade")
            return False
        except Exception as e:
            logger.error(f"Risk API unreachable ({e}), rejecting trade")
            return False

    def get_trades_df(self) -> pd.DataFrame:
        """Return all closed trades as a DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        df = pd.DataFrame(self.trades)
        for col in ["entry_time", "exit_time"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True)
        return df
