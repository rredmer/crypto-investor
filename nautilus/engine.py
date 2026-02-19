"""
NautilusTrader Engine Adapter
==============================
Configures a real BacktestEngine with proper Venue, Instrument, and
Bar data when nautilus_trader is installed. Falls back gracefully
when the library is not available.

Usage:
    from nautilus.engine import HAS_NAUTILUS_TRADER, create_backtest_engine
    if HAS_NAUTILUS_TRADER:
        engine, instrument = create_backtest_engine(...)
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USDT
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import (
        AccountType,
        OmsType,
    )
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.objects import Money, Price, Quantity

    HAS_NAUTILUS_TRADER = True
except ImportError:
    HAS_NAUTILUS_TRADER = False


CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "platform_config.yaml"


def _load_nautilus_config() -> dict:
    """Load nautilus section from platform_config.yaml."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        import yaml

        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("nautilus", {})
    except (ImportError, Exception):
        return {}


# ── Timeframe Mapping ───────────────────────────────


_BAR_AGG_MAP = {
    "1m": (1, "MINUTE"),
    "5m": (5, "MINUTE"),
    "15m": (15, "MINUTE"),
    "1h": (1, "HOUR"),
    "4h": (4, "HOUR"),
    "1d": (1, "DAY"),
}


def _parse_bar_spec(timeframe: str) -> tuple[int, str]:
    """Convert '1h' to (1, 'HOUR') for BarType construction."""
    return _BAR_AGG_MAP.get(timeframe, (1, "HOUR"))


# ── Engine Factory ──────────────────────────────────


def create_backtest_engine(
    trader_id: str = "CRYPTO_INVESTOR-001",
    log_level: str = "WARNING",
) -> "BacktestEngine":
    """Create and configure a NautilusTrader BacktestEngine.

    Returns the engine instance. Raises ImportError if nautilus_trader
    is not installed.
    """
    if not HAS_NAUTILUS_TRADER:
        raise ImportError("nautilus_trader is not installed")

    config = BacktestEngineConfig(
        logging=LoggingConfig(log_level=log_level),
        trader_id=trader_id,
    )
    engine = BacktestEngine(config=config)
    logger.info(f"BacktestEngine created: trader_id={trader_id}")
    return engine


def add_venue(
    engine: "BacktestEngine",
    venue_name: str = "BINANCE",
    oms_type: str = "NETTING",
    account_type: str = "CASH",
    starting_balance: float = 10000.0,
) -> "Venue":
    """Add a simulated venue to the engine."""
    if not HAS_NAUTILUS_TRADER:
        raise ImportError("nautilus_trader is not installed")

    venue = Venue(venue_name)
    oms = OmsType[oms_type]
    acct = AccountType[account_type]

    engine.add_venue(
        venue=venue,
        oms_type=oms,
        account_type=acct,
        base_currency=USDT,
        starting_balances=[Money(starting_balance, USDT)],
    )
    logger.info(f"Venue added: {venue_name}, balance={starting_balance} USDT")
    return venue


def create_crypto_instrument(
    symbol: str = "BTC/USDT",
    venue_name: str = "BINANCE",
) -> "InstrumentId":
    """Create a crypto spot instrument for backtesting.

    Returns the InstrumentId. The instrument is created using
    TestInstrumentProvider for simplicity.
    """
    if not HAS_NAUTILUS_TRADER:
        raise ImportError("nautilus_trader is not installed")

    # Use the built-in test instrument for BTCUSDT
    # For production, you'd create a custom CurrencyPair
    safe_symbol = symbol.replace("/", "")
    instrument_id = InstrumentId(
        symbol=Symbol(safe_symbol),
        venue=Venue(venue_name),
    )
    return instrument_id


def build_bar_type(
    instrument_id: "InstrumentId",
    timeframe: str = "1h",
) -> "BarType":
    """Construct a BarType for the given instrument and timeframe."""
    if not HAS_NAUTILUS_TRADER:
        raise ImportError("nautilus_trader is not installed")

    step, agg_name = _parse_bar_spec(timeframe)

    return BarType(
        instrument_id=instrument_id,
        bar_spec=f"{step}-{agg_name}-LAST",
        aggregation_source="EXTERNAL",
    )


def convert_df_to_bars(
    df: pd.DataFrame,
    bar_type: "BarType",
) -> list["Bar"]:
    """Convert a pandas OHLCV DataFrame to a list of NautilusTrader Bar objects."""
    if not HAS_NAUTILUS_TRADER:
        raise ImportError("nautilus_trader is not installed")

    bars = []
    for ts, row in df.iterrows():
        ts_ns = int(ts.value)  # nanoseconds since epoch
        bar = Bar(
            bar_type=bar_type,
            open=Price.from_str(f"{row['open']:.8f}"),
            high=Price.from_str(f"{row['high']:.8f}"),
            low=Price.from_str(f"{row['low']:.8f}"),
            close=Price.from_str(f"{row['close']:.8f}"),
            volume=Quantity.from_str(f"{row['volume']:.8f}"),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
        bars.append(bar)

    logger.info(f"Converted {len(bars)} bars for {bar_type}")
    return bars
