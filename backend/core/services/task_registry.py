"""Registry mapping task_type strings to executor functions.

Each executor has signature: (params: dict, progress_cb: Callable) -> dict
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("scheduler")

ProgressCallback = Callable[[float, str], None]
TaskExecutor = Callable[[dict, ProgressCallback], dict[str, Any]]


def _run_data_refresh(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Refresh OHLCV data for an asset class watchlist."""
    from core.platform_bridge import ensure_platform_imports, get_platform_config

    ensure_platform_imports()
    from common.data_pipeline.pipeline import download_watchlist

    asset_class = params.get("asset_class", "crypto")
    config = get_platform_config()
    data_cfg = config.get("data", {})

    watchlist_key = {
        "crypto": "watchlist",
        "equity": "equity_watchlist",
        "forex": "forex_watchlist",
    }.get(asset_class, "watchlist")
    symbols = data_cfg.get(watchlist_key, [])

    if not symbols:
        return {"status": "skipped", "reason": f"No {asset_class} watchlist configured"}

    progress_cb(0.1, f"Refreshing {len(symbols)} {asset_class} symbols")
    results = download_watchlist(
        symbols=symbols[:50],
        timeframes=None,
        asset_class=asset_class,
    )
    progress_cb(0.9, "Data refresh complete")

    succeeded = sum(
        1 for v in results.values()
        if isinstance(v, dict) and v.get("status") == "ok"
    )
    failed = sum(
        1 for v in results.values()
        if isinstance(v, dict) and v.get("status") == "error"
    )
    if failed:
        logger.error(
            "Data refresh: %d/%d symbols failed to download",
            failed, len(results),
        )
    return {
        "status": "completed" if succeeded > 0 else "error",
        "symbols": len(symbols),
        "saved": succeeded,
        "failed": failed,
    }


# Track last known regimes for transition detection
_last_known_regimes: dict[str, str] = {}


def _run_regime_detection(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run regime detection for all crypto watchlist symbols."""
    progress_cb(0.1, "Detecting regimes")
    try:
        from market.services.regime import RegimeService

        service = RegimeService()
        regimes = service.get_all_current_regimes()

        # Detect regime transitions and broadcast changes
        try:
            from core.services.ws_broadcast import broadcast_regime_change

            for regime_data in regimes:
                symbol = regime_data.get("symbol", "")
                new_regime = regime_data.get("regime", "unknown")
                prev_regime = _last_known_regimes.get(symbol)
                if prev_regime is not None and prev_regime != new_regime:
                    broadcast_regime_change(
                        symbol=symbol,
                        previous_regime=prev_regime,
                        new_regime=new_regime,
                        confidence=regime_data.get("confidence", 0.0),
                    )
                _last_known_regimes[symbol] = new_regime
        except Exception:
            logger.debug("Regime broadcast failed", exc_info=True)

        return {"status": "completed", "regimes_detected": len(regimes)}
    except Exception as e:
        logger.error("Regime detection failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_order_sync(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Sync open live orders with exchange."""
    from datetime import timedelta

    from asgiref.sync import async_to_sync
    from django.conf import settings
    from django.utils import timezone

    from trading.models import Order, OrderStatus, TradingMode
    from trading.services.live_trading import LiveTradingService

    timeout_hours = getattr(settings, "ORDER_SYNC_TIMEOUT_HOURS", 24)
    cutoff = timezone.now() - timedelta(hours=timeout_hours)

    pending = Order.objects.filter(
        mode=TradingMode.LIVE,
        status__in=[OrderStatus.SUBMITTED, OrderStatus.OPEN, OrderStatus.PARTIAL_FILL],
    )
    total = pending.count()
    progress_cb(0.0, f"Syncing {total} pending orders")

    if total == 0:
        return {"status": "completed", "synced": 0, "timed_out": 0, "errors": 0, "total": 0}

    synced = 0
    timed_out = 0
    errors = 0

    for i, order in enumerate(pending):
        # Timeout stuck SUBMITTED orders
        if order.status == OrderStatus.SUBMITTED and order.created_at < cutoff:
            order.status = OrderStatus.ERROR
            order.error_message = "Order sync timeout: no exchange confirmation"
            order.save(update_fields=["status", "error_message"])
            timed_out += 1
            continue

        try:
            async_to_sync(LiveTradingService.sync_order)(order)
            synced += 1
        except Exception as exc:
            logger.error("Order sync failed for %s: %s", order.id, exc)
            errors += 1

        progress_cb((i + 1) / max(total, 1), f"Synced {i + 1}/{total}")

    return {
        "status": "completed",
        "total": total,
        "synced": synced,
        "timed_out": timed_out,
        "errors": errors,
    }


def _run_data_quality(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run full data quality validation across all data files."""
    from core.platform_bridge import ensure_platform_imports

    ensure_platform_imports()
    progress_cb(0.1, "Checking data quality")
    try:
        from common.data_pipeline.pipeline import validate_all_data

        reports = validate_all_data()
        passed = sum(1 for r in reports if r.passed)
        failed = len(reports) - passed

        summary = {
            "total": len(reports),
            "passed": passed,
            "failed": failed,
            "issues": [],
        }
        for r in reports:
            if not r.passed:
                summary["issues"].append(
                    f"{r.symbol}/{r.timeframe}: {', '.join(r.issues_summary)}"
                )

        progress_cb(0.9, f"Validated {len(reports)} files")
        return {"status": "completed", "quality_summary": summary}
    except Exception as e:
        logger.error("Data quality check failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_news_fetch(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Fetch latest news for all asset classes."""
    progress_cb(0.1, "Fetching news")
    try:
        from market.services.news import NewsService

        service = NewsService()
        total = 0
        for ac in ("crypto", "equity", "forex"):
            count = service.fetch_and_store(ac)
            total += count

            # Broadcast news + sentiment updates per asset class
            try:
                from core.services.ws_broadcast import (
                    broadcast_news_update,
                    broadcast_sentiment_update,
                )

                summary = service.get_sentiment_summary(ac)
                broadcast_news_update(ac, count, summary)
                broadcast_sentiment_update(
                    asset_class=ac,
                    avg_score=summary.get("avg_score", 0.0),
                    overall_label=summary.get("overall_label", "neutral"),
                    total_articles=summary.get("total_articles", 0),
                )
            except Exception:
                logger.debug("News broadcast failed for %s", ac, exc_info=True)

        return {"status": "completed", "articles_fetched": total}
    except Exception as e:
        logger.warning("News fetch failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_workflow(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Execute a workflow pipeline."""
    from analysis.services.workflow_engine import execute_workflow

    return execute_workflow(params, progress_cb)


def _run_risk_monitoring(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run periodic risk monitoring across all portfolios."""
    progress_cb(0.1, "Checking portfolio risk")
    try:
        from portfolio.models import Portfolio
        from risk.services.risk import RiskManagementService

        portfolios = list(Portfolio.objects.values_list("id", flat=True))
        if not portfolios:
            return {"status": "completed", "message": "No portfolios"}

        results = []
        for i, pid in enumerate(portfolios):
            try:
                result = RiskManagementService.periodic_risk_check(pid)
                results.append(result)
            except Exception as e:
                logger.error("Risk check failed for portfolio %s: %s", pid, e)
                results.append({"portfolio_id": pid, "status": "error", "error": str(e)})
            progress_cb(0.1 + 0.8 * (i + 1) / len(portfolios), f"Checked portfolio {pid}")

        return {"status": "completed", "portfolios_checked": len(portfolios), "results": results}
    except Exception as e:
        logger.error("Risk monitoring failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_db_maintenance(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run SQLite WAL checkpoint to prevent unbounded WAL growth."""
    from django.db import connection

    progress_cb(0.1, "Running WAL checkpoint")
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        row = cursor.fetchone()
        wal_result = {"busy": row[0], "log": row[1], "checkpointed": row[2]}
    progress_cb(0.9, "Checkpoint complete")
    return {"status": "completed", "wal_checkpoint": wal_result}


def _run_vbt_screen(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run VectorBT strategy screen on watchlist symbols."""
    from core.platform_bridge import ensure_platform_imports, get_platform_config

    ensure_platform_imports()
    asset_class = params.get("asset_class", "crypto")
    timeframe = params.get("timeframe", "1h")
    config = get_platform_config()
    data_cfg = config.get("data", {})

    watchlist_key = {
        "crypto": "watchlist",
        "equity": "equity_watchlist",
        "forex": "forex_watchlist",
    }.get(asset_class, "watchlist")
    symbols = data_cfg.get(watchlist_key, [])

    if not symbols:
        return {"status": "skipped", "reason": f"No {asset_class} watchlist configured"}

    progress_cb(0.1, f"Screening {len(symbols)} {asset_class} symbols")
    results = []
    for i, symbol in enumerate(symbols):
        try:
            from analysis.services.screening import ScreenerService

            default_exchange = "yfinance" if asset_class in ("equity", "forex") else "kraken"
            screen_params = {
                "symbol": symbol,
                "timeframe": "1d" if asset_class in ("equity", "forex") else timeframe,
                "exchange": params.get("exchange", default_exchange),
                "asset_class": asset_class,
            }
            result = ScreenerService.run_full_screen(
                screen_params,
                lambda p, m, _i=i: progress_cb(0.1 + 0.8 * (_i + p) / len(symbols), m),
            )
            results.append({"symbol": symbol, "status": "completed", "result": result})
        except Exception as e:
            logger.warning("VBT screen failed for %s: %s", symbol, e)
            results.append({"symbol": symbol, "status": "error", "error": str(e)})
        progress_cb(0.1 + 0.8 * (i + 1) / len(symbols), f"Screened {i + 1}/{len(symbols)}")

    return {"status": "completed", "symbols_screened": len(results), "results": results}


def _run_ml_training(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Train ML models on OHLCV data for specified symbols."""
    progress_cb(0.1, "Starting ML training")
    symbols = params.get("symbols", [params.get("symbol", "BTC/USDT")])
    if isinstance(symbols, str):
        symbols = [symbols]
    timeframe = params.get("timeframe", "1h")

    results = []
    for i, symbol in enumerate(symbols):
        try:
            from analysis.services.ml import MLService

            train_params = {
                "symbol": symbol,
                "timeframe": timeframe,
                "exchange": params.get("exchange", "kraken"),
                "test_ratio": params.get("test_ratio", 0.2),
            }
            result = MLService.train(
                train_params,
                lambda p, m, _i=i: progress_cb(0.1 + 0.8 * (_i + p) / len(symbols), m),
            )
            results.append({"symbol": symbol, **result})
        except Exception as e:
            logger.warning("ML training failed for %s: %s", symbol, e)
            results.append({"symbol": symbol, "status": "error", "error": str(e)})
        progress_cb(0.1 + 0.8 * (i + 1) / len(symbols), f"Trained {i + 1}/{len(symbols)}")

    return {"status": "completed", "models_trained": len(results), "results": results}


def _run_market_scan(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Scan pairs for trading opportunities."""
    asset_class = params.get("asset_class", "crypto")
    progress_cb(0.1, f"Scanning {asset_class} market for opportunities")
    try:
        from market.services.market_scanner import MarketScannerService

        scanner = MarketScannerService()
        timeframe = params.get("timeframe", "1h")
        result = scanner.scan_all(timeframe=timeframe, asset_class=asset_class)
        progress_cb(0.9, "Market scan complete")
        return result
    except Exception as e:
        logger.error("Market scan failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_daily_report(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Generate daily intelligence report and send Telegram summary."""
    progress_cb(0.1, "Generating daily report")
    try:
        from market.services.daily_report import DailyReportService

        service = DailyReportService()
        report = service.generate()
        progress_cb(0.9, "Daily report complete")

        # Send Telegram summary
        try:
            from core.services.notification import NotificationService

            regime = report.get("regime", {})
            perf = report.get("strategy_performance", {})
            sys_status = report.get("system_status", {})
            lines = [
                "<b>Daily Intelligence Report</b>",
                f"Regime: {regime.get('dominant_regime', 'unknown')} "
                f"(conf {regime.get('avg_confidence', 0):.0%})",
                f"Orders: {perf.get('total_orders', 0)} | "
                f"Win rate: {perf.get('win_rate', 0):.1f}% | "
                f"P&L: ${perf.get('total_pnl', 0):.2f}",
                f"Paper trading day {sys_status.get('days_paper_trading', 0)}"
                f"/{sys_status.get('min_days_required', 14)}",
            ]
            NotificationService.send_telegram_sync("\n".join(lines))
        except Exception:
            logger.debug("Daily report Telegram send failed", exc_info=True)

        return {"status": "completed", "report": report}
    except Exception as e:
        logger.error("Daily report generation failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_forex_paper_trading(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run forex paper trading cycle — entries and exits from scanner signals."""
    progress_cb(0.1, "Running forex paper trading cycle")
    try:
        from trading.services.forex_paper_trading import ForexPaperTradingService

        service = ForexPaperTradingService()
        result = service.run_cycle()
        progress_cb(0.9, "Forex paper trading cycle complete")
        return result
    except Exception as e:
        logger.error("Forex paper trading cycle failed: %s", e)
        return {"status": "error", "error": str(e)}


def _run_nautilus_backtest(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run NautilusTrader backtests across configured strategies for an asset class."""
    from core.platform_bridge import ensure_platform_imports, get_platform_config

    ensure_platform_imports()
    asset_class = params.get("asset_class", "crypto")
    timeframe = params.get("timeframe", "1h")
    exchange = params.get("exchange", "kraken")
    initial_balance = params.get("initial_balance", 10000.0)

    try:
        from nautilus.nautilus_runner import list_nautilus_strategies, run_nautilus_backtest
    except ImportError as e:
        return {"status": "error", "error": f"NautilusTrader not available: {e}"}

    # Map asset class to strategy subset
    strategy_map = {
        "crypto": ["NautilusTrendFollowing", "NautilusMeanReversion", "NautilusVolatilityBreakout"],
        "equity": ["EquityMomentum", "EquityMeanReversion"],
        "forex": ["ForexTrend", "ForexRange"],
    }
    strategies = params.get("strategies") or strategy_map.get(asset_class, [])
    available = list_nautilus_strategies()
    strategies = [s for s in strategies if s in available]

    if not strategies:
        return {"status": "skipped", "reason": f"No Nautilus strategies for {asset_class}"}

    # Get symbols from watchlist
    config = get_platform_config()
    data_cfg = config.get("data", {})
    watchlist_key = {
        "crypto": "watchlist",
        "equity": "equity_watchlist",
        "forex": "forex_watchlist",
    }.get(asset_class, "watchlist")
    symbols = data_cfg.get(watchlist_key, [])[:3]  # Top 3 symbols per run

    if not symbols:
        return {"status": "skipped", "reason": f"No {asset_class} watchlist configured"}

    progress_cb(0.1, f"Running {len(strategies)} Nautilus strategies on {len(symbols)} {asset_class} symbols")
    results = []
    total_steps = len(strategies) * len(symbols)
    step = 0

    for strategy in strategies:
        for symbol in symbols:
            step += 1
            try:
                result = run_nautilus_backtest(
                    strategy, symbol, timeframe, exchange, initial_balance,
                    asset_class=asset_class,
                )
                results.append({
                    "strategy": strategy, "symbol": symbol,
                    "status": "completed", "result": result,
                })
            except Exception as e:
                logger.warning("Nautilus backtest failed %s/%s: %s", strategy, symbol, e)
                results.append({
                    "strategy": strategy, "symbol": symbol,
                    "status": "error", "error": str(e),
                })
            progress_cb(0.1 + 0.8 * step / total_steps, f"{strategy} on {symbol}")

    completed = sum(1 for r in results if r["status"] == "completed")
    progress_cb(0.95, f"Nautilus backtests done: {completed}/{len(results)}")
    return {
        "status": "completed",
        "framework": "nautilus",
        "asset_class": asset_class,
        "strategies_run": len(strategies),
        "symbols_tested": len(symbols),
        "total_backtests": len(results),
        "completed": completed,
        "results": results,
    }


def _run_hft_backtest(params: dict, progress_cb: ProgressCallback) -> dict[str, Any]:
    """Run HFT backtests across configured strategies."""
    from core.platform_bridge import ensure_platform_imports, get_platform_config

    ensure_platform_imports()
    exchange = params.get("exchange", "kraken")
    initial_balance = params.get("initial_balance", 10000.0)
    latency_ns = params.get("latency_ns", 1_000_000)

    try:
        from hftbacktest.hft_runner import list_hft_strategies, run_hft_backtest
    except ImportError as e:
        return {"status": "error", "error": f"hftbacktest not available: {e}"}

    strategies = params.get("strategies") or list_hft_strategies()
    if not strategies:
        return {"status": "skipped", "reason": "No HFT strategies available"}

    # HFT is crypto-only, use top crypto symbols
    config = get_platform_config()
    symbols = config.get("data", {}).get("watchlist", [])[:3]
    timeframe = params.get("timeframe", "1h")

    if not symbols:
        return {"status": "skipped", "reason": "No crypto watchlist configured"}

    progress_cb(0.1, f"Running {len(strategies)} HFT strategies on {len(symbols)} symbols")
    results = []
    total_steps = len(strategies) * len(symbols)
    step = 0

    for strategy in strategies:
        for symbol in symbols:
            step += 1
            try:
                result = run_hft_backtest(
                    strategy, symbol, timeframe, exchange, latency_ns, initial_balance,
                )
                results.append({
                    "strategy": strategy, "symbol": symbol,
                    "status": "completed", "result": result,
                })
            except Exception as e:
                logger.warning("HFT backtest failed %s/%s: %s", strategy, symbol, e)
                results.append({
                    "strategy": strategy, "symbol": symbol,
                    "status": "error", "error": str(e),
                })
            progress_cb(0.1 + 0.8 * step / total_steps, f"{strategy} on {symbol}")

    completed = sum(1 for r in results if r["status"] == "completed")
    progress_cb(0.95, f"HFT backtests done: {completed}/{len(results)}")
    return {
        "status": "completed",
        "framework": "hftbacktest",
        "strategies_run": len(strategies),
        "symbols_tested": len(symbols),
        "total_backtests": len(results),
        "completed": completed,
        "results": results,
    }


TASK_REGISTRY: dict[str, TaskExecutor] = {
    "data_refresh": _run_data_refresh,
    "regime_detection": _run_regime_detection,
    "order_sync": _run_order_sync,
    "data_quality": _run_data_quality,
    "news_fetch": _run_news_fetch,
    "workflow": _run_workflow,
    "risk_monitoring": _run_risk_monitoring,
    "db_maintenance": _run_db_maintenance,
    "vbt_screen": _run_vbt_screen,
    "ml_training": _run_ml_training,
    "market_scan": _run_market_scan,
    "daily_report": _run_daily_report,
    "forex_paper_trading": _run_forex_paper_trading,
    "nautilus_backtest": _run_nautilus_backtest,
    "hft_backtest": _run_hft_backtest,
}
