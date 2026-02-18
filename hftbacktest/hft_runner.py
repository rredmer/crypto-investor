"""
hftbacktest Runner
===================
Bridge between crypto-investor platform and hftbacktest HFT simulation.

Handles:
    - Converting OHLCV Parquet data to synthetic tick arrays
    - Configuring and running HFT backtests
    - Extracting performance results
"""

import json
import sys
import logging
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("hft_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CATALOG_DIR = PROJECT_ROOT / "hftbacktest" / "catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = PROJECT_ROOT / "hftbacktest" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TICKS_DIR = PROJECT_ROOT / "data" / "ticks"
TICKS_DIR.mkdir(parents=True, exist_ok=True)


def convert_ohlcv_to_hft_ticks(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    exchange: str = "binance",
) -> Path:
    """
    Convert OHLCV Parquet data to synthetic tick numpy arrays.

    Generates 4 ticks per bar (O/H/L/C) with interpolated timestamps.
    This is a development approximation — real HFT requires actual tick data.

    Returns path to saved .npy file.
    """
    from common.data_pipeline.pipeline import load_ohlcv

    df = load_ohlcv(symbol, timeframe, exchange)
    if df.empty:
        logger.error(f"No data for {symbol} {timeframe}")
        return None

    logger.info(f"Converting {len(df)} bars to synthetic ticks...")

    ticks = []
    for ts, row in df.iterrows():
        ts_ns = int(ts.value)  # nanosecond timestamp

        # Timeframe to nanosecond interval
        tf_ns_map = {
            "1m": 60_000_000_000,
            "5m": 300_000_000_000,
            "15m": 900_000_000_000,
            "1h": 3_600_000_000_000,
            "4h": 14_400_000_000_000,
            "1d": 86_400_000_000_000,
        }
        interval_ns = tf_ns_map.get(timeframe, 3_600_000_000_000)
        quarter = interval_ns // 4

        # 4 ticks per bar: Open, High, Low, Close
        # side: +1 buy, -1 sell (synthetic: up moves are buys)
        open_p = float(row["open"])
        high_p = float(row["high"])
        low_p = float(row["low"])
        close_p = float(row["close"])
        vol = float(row["volume"]) / 4  # Distribute volume

        ticks.append([ts_ns, open_p, vol, 1])
        ticks.append([ts_ns + quarter, high_p, vol, 1])
        ticks.append([ts_ns + 2 * quarter, low_p, vol, -1])
        ticks.append([ts_ns + 3 * quarter, close_p, 1 if close_p >= open_p else -1])

    tick_array = np.array(ticks, dtype=np.float64)

    safe_symbol = symbol.replace("/", "")
    output_path = TICKS_DIR / f"{exchange}_{safe_symbol}_{timeframe}_ticks.npy"
    np.save(output_path, tick_array)
    logger.info(f"Saved {len(tick_array)} ticks to {output_path}")
    return output_path


def list_hft_strategies() -> list[str]:
    """Return names of all registered HFT strategies."""
    from hftbacktest.strategies import STRATEGY_REGISTRY
    return list(STRATEGY_REGISTRY.keys())


def run_hft_backtest(
    strategy_name: str,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    exchange: str = "binance",
    latency_ns: int = 1_000_000,
    initial_balance: float = 10000.0,
) -> dict:
    """
    Run an HFT backtest using one of the registered strategies.

    Loads tick data (generating from OHLCV if needed), runs the strategy,
    and computes performance metrics.
    """
    from hftbacktest.strategies import STRATEGY_REGISTRY
    from nautilus.nautilus_runner import compute_performance_metrics

    if strategy_name not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        return {"error": f"Unknown strategy '{strategy_name}'. Available: {available}"}

    # Load or generate tick data
    safe_symbol = symbol.replace("/", "")
    tick_path = TICKS_DIR / f"{exchange}_{safe_symbol}_{timeframe}_ticks.npy"

    if not tick_path.exists():
        logger.info("Tick data not found, generating from OHLCV...")
        tick_path = convert_ohlcv_to_hft_ticks(symbol, timeframe, exchange)
        if tick_path is None:
            return {"error": f"No data for {symbol} {timeframe} on {exchange}"}

    tick_array = np.load(tick_path)
    logger.info(f"Running HFT backtest: {strategy_name} on {len(tick_array)} ticks")

    # Instantiate strategy
    strategy_cls = STRATEGY_REGISTRY[strategy_name]
    config = {
        "initial_balance": initial_balance,
        "latency_ns": latency_ns,
    }
    strategy = strategy_cls(config=config)

    # Run
    strategy.run(tick_array)

    # Collect results
    trades_df = strategy.get_trades_df()
    metrics = compute_performance_metrics(trades_df)

    result = {
        "framework": "hftbacktest",
        "strategy": strategy_name,
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange,
        "initial_balance": initial_balance,
        "latency_ns": latency_ns,
        "ticks_processed": len(tick_array),
        "total_fills": len(strategy.fills),
        "final_position": strategy.position,
        "realized_pnl": round(strategy.realized_pnl, 2),
        "metrics": metrics,
    }

    # Save results
    result_path = RESULTS_DIR / f"{strategy_name}_{safe_symbol}_{timeframe}.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Results saved to {result_path}")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="hftbacktest Runner")
    sub = parser.add_subparsers(dest="command")

    # Convert data
    conv = sub.add_parser("convert", help="Convert OHLCV data to tick format")
    conv.add_argument("--symbol", default="BTC/USDT")
    conv.add_argument("--timeframe", default="1h")
    conv.add_argument("--exchange", default="binance")

    # Backtest
    bt = sub.add_parser("backtest", help="Run HFT backtest")
    bt.add_argument("--strategy", required=True, help="Strategy name from registry")
    bt.add_argument("--symbol", default="BTC/USDT")
    bt.add_argument("--timeframe", default="1h")
    bt.add_argument("--exchange", default="binance")
    bt.add_argument("--latency", type=int, default=1_000_000, help="Latency in nanoseconds")
    bt.add_argument("--balance", type=float, default=10000.0)

    # List strategies
    sub.add_parser("list-strategies", help="List registered strategies")

    # Test
    sub.add_parser("test", help="Test hftbacktest basic functionality")

    args = parser.parse_args()

    if args.command == "convert":
        convert_ohlcv_to_hft_ticks(args.symbol, args.timeframe, args.exchange)
    elif args.command == "backtest":
        result = run_hft_backtest(
            args.strategy, args.symbol, args.timeframe, args.exchange,
            args.latency, args.balance,
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "list-strategies":
        for name in list_hft_strategies():
            print(f"  {name}")
    elif args.command == "test":
        print("hftbacktest module: OK")
        strategies = list_hft_strategies()
        print(f"Registered strategies: {strategies}")
    else:
        parser.print_help()
