"""
NautilusTrader Strategy Registry
=================================
Maps strategy names to classes for dynamic lookup by the runner and backend.
"""

from nautilus.strategies.trend_following import NautilusTrendFollowing
from nautilus.strategies.mean_reversion import NautilusMeanReversion
from nautilus.strategies.volatility_breakout import NautilusVolatilityBreakout

STRATEGY_REGISTRY: dict[str, type] = {
    "NautilusTrendFollowing": NautilusTrendFollowing,
    "NautilusMeanReversion": NautilusMeanReversion,
    "NautilusVolatilityBreakout": NautilusVolatilityBreakout,
}
