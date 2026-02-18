"""
NautilusTrader Integration Layer
=================================
Bridge between crypto-investor platform and NautilusTrader's
institutional-grade backtesting and execution engine.

Handles:
    - Converting shared Parquet data into Nautilus bar format
    - Configuring backtest engines with risk controls
    - Running event-driven backtests (pandas-based strategy runner)
    - Extracting performance results
"""

import json
import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("nautilus_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CATALOG_DIR = PROJECT_ROOT / "nautilus" / "catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = PROJECT_ROOT / "nautilus" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def convert_ohlcv_to_nautilus_csv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    exchange: str = "binance",
) -> Path:
    """
    Convert shared Parquet OHLCV data into Nautilus-compatible CSV bars.
    NautilusTrader can ingest CSV data via its data catalog or wranglers.
    """
    from common.data_pipeline.pipeline import load_ohlcv

    df = load_ohlcv(symbol, timeframe, exchange)
    if df.empty:
        logger.error(f"No data for {symbol} {timeframe}")
        return None

    safe_symbol = symbol.replace("/", "")
    venue = exchange.upper()

    nautilus_df = pd.DataFrame({
        "bar_type": f"{safe_symbol}.{venue}-{_tf_to_nautilus(timeframe)}-LAST-EXTERNAL",
        "open": df["open"].astype(str),
        "high": df["high"].astype(str),
        "low": df["low"].astype(str),
        "close": df["close"].astype(str),
        "volume": df["volume"].astype(str),
        "ts_event": df.index.astype(np.int64),
        "ts_init": df.index.astype(np.int64),
    })

    output_path = CATALOG_DIR / f"{safe_symbol}_{venue}_{timeframe}_bars.csv"
    nautilus_df.to_csv(output_path, index=False)
    logger.info(f"Exported {len(nautilus_df)} bars to {output_path}")
    return output_path


def _tf_to_nautilus(timeframe: str) -> str:
    """Convert common timeframe strings to Nautilus bar aggregation format."""
    mapping = {
        "1m": "1-MINUTE",
        "5m": "5-MINUTE",
        "15m": "15-MINUTE",
        "1h": "1-HOUR",
        "4h": "4-HOUR",
        "1d": "1-DAY",
    }
    return mapping.get(timeframe, "1-HOUR")


def list_nautilus_strategies() -> list[str]:
    """Return names of all registered NautilusTrader strategies."""
    from nautilus.strategies import STRATEGY_REGISTRY
    return list(STRATEGY_REGISTRY.keys())


def run_nautilus_backtest(
    strategy_name: str,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    exchange: str = "binance",
    initial_balance: float = 10000.0,
) -> dict:
    """
    Run a backtest using one of the registered Nautilus strategies.

    Loads Parquet data, feeds bars to the strategy, collects trades,
    computes performance metrics, and saves results as JSON.
    """
    from nautilus.strategies import STRATEGY_REGISTRY
    from common.data_pipeline.pipeline import load_ohlcv

    if strategy_name not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        return {"error": f"Unknown strategy '{strategy_name}'. Available: {available}"}

    # Load data
    df = load_ohlcv(symbol, timeframe, exchange)
    if df.empty:
        return {"error": f"No data for {symbol} {timeframe} on {exchange}"}

    logger.info(f"Running backtest: {strategy_name} on {symbol} {timeframe} ({len(df)} bars)")

    # Instantiate strategy
    strategy_cls = STRATEGY_REGISTRY[strategy_name]
    config = {
        "mode": "backtest",
        "symbol": symbol,
        "initial_balance": initial_balance,
    }
    strategy = strategy_cls(config=config)

    # Feed bars
    for ts, row in df.iterrows():
        bar = {
            "timestamp": ts,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        strategy.on_bar(bar)

    # Flatten any remaining position
    strategy.on_stop()

    # Collect results
    trades_df = strategy.get_trades_df()
    metrics = compute_performance_metrics(trades_df)

    result = {
        "framework": "nautilus",
        "strategy": strategy_name,
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange,
        "initial_balance": initial_balance,
        "bars_processed": len(df),
        "metrics": metrics,
    }

    # Save to results dir
    safe_symbol = symbol.replace("/", "")
    result_path = RESULTS_DIR / f"{strategy_name}_{safe_symbol}_{timeframe}.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Results saved to {result_path}")

    return result


def run_nautilus_backtest_example():
    """
    Demonstrate NautilusTrader backtest setup.

    This creates a minimal backtest configuration showing how to:
    1. Configure the engine
    2. Add venues and instruments
    3. Add data
    4. Run strategies

    For production use, strategies are defined in nautilus/strategies/.
    """
    try:
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.identifiers import Venue  # noqa: F401
    except ImportError as e:
        logger.error(f"NautilusTrader import failed: {e}")
        logger.info("Install with: pip install nautilus_trader")
        return None

    config = BacktestEngineConfig(
        logging=LoggingConfig(log_level="INFO"),
        trader_id="CRYPTO_INVESTOR-001",
    )

    engine = BacktestEngine(config=config)
    logger.info("NautilusTrader BacktestEngine initialized successfully")
    logger.info(f"  Trader ID: {config.trader_id}")
    logger.info(f"  Engine type: {type(engine).__name__}")

    return engine


def compute_performance_metrics(trades_df: pd.DataFrame) -> dict:
    """
    Compute standard performance metrics from a trades DataFrame.
    Works with output from any framework (Nautilus, Freqtrade, or VectorBT).

    Expected columns: entry_time, exit_time, pnl, pnl_pct, side
    """
    if trades_df.empty:
        return {"error": "No trades to analyze"}

    total_trades = len(trades_df)
    winners = trades_df[trades_df["pnl"] > 0]
    losers = trades_df[trades_df["pnl"] <= 0]

    total_pnl = trades_df["pnl"].sum()
    win_rate = len(winners) / total_trades if total_trades > 0 else 0

    gross_profit = winners["pnl"].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers["pnl"].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = winners["pnl"].mean() if len(winners) > 0 else 0
    avg_loss = losers["pnl"].mean() if len(losers) > 0 else 0

    # Sharpe-like ratio from trade returns
    if "pnl_pct" in trades_df.columns and trades_df["pnl_pct"].std() > 0:
        sharpe = (trades_df["pnl_pct"].mean() / trades_df["pnl_pct"].std()) * np.sqrt(252)
    else:
        sharpe = 0

    # Max drawdown from cumulative PnL
    cum_pnl = trades_df["pnl"].cumsum()
    running_max = cum_pnl.cummax()
    drawdown = cum_pnl - running_max
    max_drawdown = drawdown.min()

    return {
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 3),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_drawdown, 2),
        "best_trade": round(trades_df["pnl"].max(), 2),
        "worst_trade": round(trades_df["pnl"].min(), 2),
        "avg_trade_duration": str(
            (trades_df["exit_time"] - trades_df["entry_time"]).mean()
        ) if "exit_time" in trades_df.columns and "entry_time" in trades_df.columns else "N/A",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NautilusTrader Runner")
    sub = parser.add_subparsers(dest="command")

    # Convert data
    conv = sub.add_parser("convert", help="Convert Parquet data to Nautilus CSV")
    conv.add_argument("--symbol", default="BTC/USDT")
    conv.add_argument("--timeframe", default="1h")
    conv.add_argument("--exchange", default="binance")

    # Test engine
    sub.add_parser("test", help="Test NautilusTrader engine initialization")

    # Backtest
    bt = sub.add_parser("backtest", help="Run strategy backtest")
    bt.add_argument("--strategy", required=True, help="Strategy name from registry")
    bt.add_argument("--symbol", default="BTC/USDT")
    bt.add_argument("--timeframe", default="1h")
    bt.add_argument("--exchange", default="binance")
    bt.add_argument("--balance", type=float, default=10000.0)

    # List strategies
    sub.add_parser("list-strategies", help="List registered strategies")

    args = parser.parse_args()

    if args.command == "convert":
        convert_ohlcv_to_nautilus_csv(args.symbol, args.timeframe, args.exchange)
    elif args.command == "test":
        engine = run_nautilus_backtest_example()
        if engine:
            print("NautilusTrader engine test: PASSED")
        else:
            print("NautilusTrader engine test: FAILED")
    elif args.command == "backtest":
        result = run_nautilus_backtest(
            args.strategy, args.symbol, args.timeframe, args.exchange, args.balance,
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "list-strategies":
        for name in list_nautilus_strategies():
            print(f"  {name}")
    else:
        parser.print_help()
