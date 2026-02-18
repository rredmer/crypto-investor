"""
HFT Strategy Base Class
========================
Shared functionality for all hftbacktest strategies:
- Inventory tracking (position, avg cost)
- Order management (submit/cancel helpers)
- PnL + drawdown tracking
- Tick-by-tick processing loop
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class HFTBaseStrategy:
    """Base class for HFT strategies.

    Strategies override ``on_tick()`` which receives each tick as a dict:
    ``{timestamp, price, volume, side}`` where side is 'buy' or 'sell'.

    The base class manages inventory, fills, and PnL.
    """

    name: str = "base"
    max_position: float = 1.0  # Max absolute position size
    initial_balance: float = 10000.0

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.initial_balance = self.config.get("initial_balance", 10000.0)
        self.max_position = self.config.get("max_position", self.max_position)

        # State
        self.position: float = 0.0  # Signed position (+ long, - short)
        self.avg_cost: float = 0.0
        self.realized_pnl: float = 0.0
        self.balance: float = self.initial_balance
        self.peak_balance: float = self.initial_balance
        self.fills: list[dict] = []
        self.halted: bool = False

        # Latency simulation
        self.latency_ns: int = self.config.get("latency_ns", 1_000_000)  # 1ms default

    def run(self, ticks: np.ndarray) -> list[dict]:
        """Process all ticks through the strategy. Returns list of fills."""
        for i in range(len(ticks)):
            if self.halted:
                break
            tick = {
                "timestamp": ticks[i, 0],
                "price": ticks[i, 1],
                "volume": ticks[i, 2],
                "side": "buy" if ticks[i, 3] > 0 else "sell",
            }
            self.on_tick(tick)
        return self.fills

    def on_tick(self, tick: dict) -> None:
        """Override in subclass: process a single tick."""
        raise NotImplementedError

    def submit_order(self, side: str, price: float, size: float, tick: dict) -> Optional[dict]:
        """Submit a simulated order. Returns fill dict or None if rejected."""
        if self.halted:
            return None

        # Position limit check
        new_position = self.position + (size if side == "buy" else -size)
        if abs(new_position) > self.max_position:
            return None

        # Simulate fill at the given price
        fill = {
            "timestamp": tick["timestamp"],
            "side": side,
            "price": price,
            "size": size,
            "position_after": new_position,
        }

        # Update position and PnL
        if side == "buy":
            if self.position < 0:
                # Closing short
                close_size = min(size, abs(self.position))
                pnl = close_size * (self.avg_cost - price)
                self.realized_pnl += pnl
                self.balance += pnl
                fill["pnl"] = pnl
            else:
                fill["pnl"] = 0.0

            # Update average cost
            if new_position > 0:
                if self.position > 0:
                    total_cost = self.avg_cost * self.position + price * size
                    self.avg_cost = total_cost / new_position
                else:
                    self.avg_cost = price
        else:  # sell
            if self.position > 0:
                # Closing long
                close_size = min(size, self.position)
                pnl = close_size * (price - self.avg_cost)
                self.realized_pnl += pnl
                self.balance += pnl
                fill["pnl"] = pnl
            else:
                fill["pnl"] = 0.0

            # Update average cost
            if new_position < 0:
                if self.position < 0:
                    total_cost = self.avg_cost * abs(self.position) + price * size
                    self.avg_cost = total_cost / abs(new_position)
                else:
                    self.avg_cost = price

        self.position = new_position

        # Track peak balance for drawdown
        self.peak_balance = max(self.peak_balance, self.balance)

        self.fills.append(fill)
        return fill

    def check_drawdown_halt(self, max_drawdown_pct: float = 0.05) -> bool:
        """Halt trading if drawdown exceeds threshold."""
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - self.balance) / self.peak_balance
            if drawdown >= max_drawdown_pct:
                logger.warning(f"Drawdown halt: {drawdown:.2%} >= {max_drawdown_pct:.2%}")
                self.halted = True
                return True
        return False

    def get_trades_df(self) -> pd.DataFrame:
        """Convert fills to a trades DataFrame compatible with compute_performance_metrics."""
        if not self.fills:
            return pd.DataFrame()

        # Pair fills into round-trip trades
        trades = []
        entry_fill = None
        for fill in self.fills:
            if entry_fill is None:
                entry_fill = fill
            elif fill["side"] != entry_fill["side"]:
                # Opposite side = closing trade
                if entry_fill["side"] == "buy":
                    pnl = (fill["price"] - entry_fill["price"]) * entry_fill["size"]
                    pnl_pct = (fill["price"] / entry_fill["price"]) - 1
                else:
                    pnl = (entry_fill["price"] - fill["price"]) * entry_fill["size"]
                    pnl_pct = (entry_fill["price"] / fill["price"]) - 1
                trades.append({
                    "entry_time": pd.Timestamp(entry_fill["timestamp"], unit="ns", tz="UTC"),
                    "exit_time": pd.Timestamp(fill["timestamp"], unit="ns", tz="UTC"),
                    "side": entry_fill["side"],
                    "entry_price": entry_fill["price"],
                    "exit_price": fill["price"],
                    "size": entry_fill["size"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                })
                entry_fill = None

        if not trades:
            return pd.DataFrame()
        return pd.DataFrame(trades)
