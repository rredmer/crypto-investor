"""
NautilusTrendFollowing — ports CryptoInvestorV1 logic
======================================================
EMA alignment + RSI pullback + MACD confirmation.

Entry: price > EMA50 > EMA200, RSI < 40, volume above average, MACD histogram positive.
Exit: RSI > 80 OR price closes below EMA50.
"""

import pandas as pd

from nautilus.strategies.base import NautilusStrategyBase


class NautilusTrendFollowing(NautilusStrategyBase):

    name = "NautilusTrendFollowing"
    stoploss = -0.05
    atr_multiplier = 2.0

    # Mirrors CryptoInvestorV1 defaults
    ema_fast: int = 50
    ema_slow: int = 200
    buy_rsi_threshold: int = 40
    sell_rsi_threshold: int = 80

    def should_enter(self, ind: pd.Series) -> bool:
        # EMA alignment: price > fast EMA > slow EMA
        if ind.get(f"ema_{self.ema_fast}", 0) <= ind.get(f"ema_{self.ema_slow}", 0):
            return False
        if ind.get("close", 0) <= ind.get(f"ema_{self.ema_fast}", 0):
            return False

        # RSI pullback in uptrend
        if ind.get("rsi_14", 50) >= self.buy_rsi_threshold:
            return False

        # Volume confirmation
        if ind.get("volume_ratio", 0) < 0.8:
            return False

        # MACD momentum (histogram positive or turning)
        macd_hist = ind.get("macd_hist", 0)
        if macd_hist <= 0:
            return False

        # Not near BB upper band (avoid chasing)
        if ind.get("close", 0) >= ind.get("bb_upper", float("inf")) * 0.98:
            return False

        return True

    def should_exit(self, ind: pd.Series) -> bool:
        # RSI overbought
        if ind.get("rsi_14", 50) > self.sell_rsi_threshold:
            return True

        # Price closed below fast EMA (trend weakening)
        if ind.get("close", 0) < ind.get(f"ema_{self.ema_fast}", 0):
            return True

        return False
