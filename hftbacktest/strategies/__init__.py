"""
HFT Strategy Registry
======================
Maps strategy names to classes for dynamic lookup by the runner and backend.
"""

from hftbacktest.strategies.market_maker import HFTMarketMaker

STRATEGY_REGISTRY: dict[str, type] = {
    "MarketMaker": HFTMarketMaker,
}
