"""
Tests for Paper Trading Infrastructure — Sprint 1, Item 1.5
============================================================
Covers: process lifecycle (start/stop/status), Freqtrade API proxy,
event logging, idempotent operations, error handling.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.services.paper_trading import PaperTradingService

# ── Helpers ───────────────────────────────────────────────────


def _make_service(tmp_path: Path) -> PaperTradingService:
    """Create a PaperTradingService with temp log directory."""
    with patch.object(
        PaperTradingService,
        "_read_ft_config",
        return_value={
            "api_server": {
                "listen_ip_address": "127.0.0.1",
                "listen_port": 8080,
                "username": "freqtrader",
                "password": "freqtrader",
            }
        },
    ):
        return PaperTradingService(log_dir=tmp_path)


def _mock_running_process() -> MagicMock:
    """Create a mock subprocess.Popen that appears to be running."""
    proc = MagicMock()
    proc.poll.return_value = None  # None = still running
    proc.pid = 12345
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = MagicMock()
    return proc


# ── Process Lifecycle Tests ───────────────────────────────────


class TestPaperTradingLifecycle:
    def test_not_running_initially(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc.is_running is False

    def test_status_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        status = svc.get_status()
        assert status["running"] is False
        assert status["uptime_seconds"] == 0

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_start_success(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)

        result = svc.start(strategy="CryptoInvestorV1")
        assert result["status"] == "started"
        assert result["strategy"] == "CryptoInvestorV1"
        assert result["pid"] == 12345
        assert "started_at" in result
        assert svc.is_running is True

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_start_already_running(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)

        svc.start("CryptoInvestorV1")
        result = svc.start("BollingerMeanReversion")
        assert result["status"] == "already_running"
        assert result["strategy"] == "CryptoInvestorV1"

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_stop_running_process(self, mock_popen, tmp_path):
        proc = _mock_running_process()
        mock_popen.return_value = proc
        svc = _make_service(tmp_path)

        svc.start("CryptoInvestorV1")
        result = svc.stop()

        assert result["status"] == "stopped"
        assert result["pid"] == 12345
        proc.terminate.assert_called_once()
        assert svc.is_running is False

    def test_stop_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = svc.stop()
        assert result["status"] == "not_running"

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_stop_force_kill_on_timeout(self, mock_popen, tmp_path):
        proc = _mock_running_process()
        proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 15), None]
        mock_popen.return_value = proc
        svc = _make_service(tmp_path)

        svc.start("CryptoInvestorV1")
        result = svc.stop()

        assert result["status"] == "stopped"
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_status_when_running(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        status = svc.get_status()
        assert status["running"] is True
        assert status["strategy"] == "CryptoInvestorV1"
        assert status["pid"] == 12345
        assert status["uptime_seconds"] >= 0
        assert "started_at" in status

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_detects_process_exit(self, mock_popen, tmp_path):
        proc = _mock_running_process()
        mock_popen.return_value = proc
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        # Simulate process crash
        proc.poll.return_value = 1
        assert svc.is_running is False

        status = svc.get_status()
        assert status["running"] is False
        assert status["exit_code"] == 1

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_start_config_missing(self, mock_popen, tmp_path):
        svc = _make_service(tmp_path)
        with patch.object(Path, "exists", return_value=False):
            result = svc.start("CryptoInvestorV1")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_start_popen_fails(self, mock_popen, tmp_path):
        mock_popen.side_effect = FileNotFoundError("freqtrade not found")
        svc = _make_service(tmp_path)
        result = svc.start("CryptoInvestorV1")
        assert result["status"] == "error"


# ── Freqtrade API Proxy Tests ────────────────────────────────


import subprocess  # noqa: E402 (needed for TimeoutExpired in test above)


class TestFreqtradeAPIProxy:
    def test_open_trades_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = asyncio.run(svc.get_open_trades())
        assert result == []

    def test_trade_history_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = asyncio.run(svc.get_trade_history())
        assert result == []

    def test_profit_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = asyncio.run(svc.get_profit())
        assert result == {}

    def test_performance_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = asyncio.run(svc.get_performance())
        assert result == []

    def test_balance_when_not_running(self, tmp_path):
        svc = _make_service(tmp_path)
        result = asyncio.run(svc.get_balance())
        assert result == {}

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_open_trades_with_mock_api(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        mock_trades = [
            {"pair": "BTC/USDT", "profit_pct": 2.5, "open_rate": 50000},
            {"pair": "ETH/USDT", "profit_pct": -1.0, "open_rate": 3000},
        ]

        async def _test():
            with patch.object(svc, "_ft_get", new_callable=AsyncMock, return_value=mock_trades):
                return await svc.get_open_trades()

        result = asyncio.run(_test())
        assert len(result) == 2
        assert result[0]["pair"] == "BTC/USDT"

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_profit_with_mock_api(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        mock_profit = {
            "profit_all_coin": 0.05,
            "profit_all_fiat": 500.0,
            "trade_count": 15,
            "first_trade_date": "2024-01-01",
        }

        async def _test():
            with patch.object(svc, "_ft_get", new_callable=AsyncMock, return_value=mock_profit):
                return await svc.get_profit()

        result = asyncio.run(_test())
        assert result["profit_all_fiat"] == 500.0
        assert result["trade_count"] == 15

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_performance_with_mock_api(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        mock_perf = [
            {"pair": "BTC/USDT", "profit": 3.5, "count": 10},
            {"pair": "ETH/USDT", "profit": -1.2, "count": 5},
        ]

        async def _test():
            with patch.object(svc, "_ft_get", new_callable=AsyncMock, return_value=mock_perf):
                return await svc.get_performance()

        result = asyncio.run(_test())
        assert len(result) == 2

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_api_returns_none_gracefully(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        async def _test():
            with patch.object(svc, "_ft_get", new_callable=AsyncMock, return_value=None):
                trades = await svc.get_open_trades()
                profit = await svc.get_profit()
                perf = await svc.get_performance()
                return trades, profit, perf

        trades, profit, perf = asyncio.run(_test())
        assert trades == []
        assert profit == {}
        assert perf == []


# ── Event Log Tests ───────────────────────────────────────────


class TestEventLog:
    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_start_creates_log_entry(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")

        entries = svc.get_log_entries()
        assert len(entries) == 1
        assert entries[0]["event"] == "started"
        assert entries[0]["strategy"] == "CryptoInvestorV1"
        assert "timestamp" in entries[0]

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_stop_creates_log_entry(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)
        svc.start("CryptoInvestorV1")
        svc.stop()

        entries = svc.get_log_entries()
        assert len(entries) == 2
        assert entries[0]["event"] == "started"
        assert entries[1]["event"] == "stopped"

    def test_empty_log(self, tmp_path):
        svc = _make_service(tmp_path)
        entries = svc.get_log_entries()
        assert entries == []

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_log_limit(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc = _make_service(tmp_path)

        # Create many log entries
        for i in range(10):
            svc._log_event("test_event", {"index": i})

        entries = svc.get_log_entries(limit=3)
        assert len(entries) == 3
        # Should be the last 3 entries
        assert entries[0]["index"] == 7
        assert entries[2]["index"] == 9

    @patch("trading.services.paper_trading.subprocess.Popen")
    def test_log_persists_across_instances(self, mock_popen, tmp_path):
        mock_popen.return_value = _mock_running_process()
        svc1 = _make_service(tmp_path)
        svc1.start("CryptoInvestorV1")
        svc1.stop()

        # New service instance reads the same log
        svc2 = _make_service(tmp_path)
        entries = svc2.get_log_entries()
        assert len(entries) == 2


# ── Config Reading Tests ──────────────────────────────────────


class TestConfigReading:
    def test_reads_api_config(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc._ft_api_url == "http://127.0.0.1:8080"
        assert svc._ft_username == "freqtrader"
        assert svc._ft_password == "freqtrader"

    def test_handles_missing_config(self, tmp_path):
        with patch.object(PaperTradingService, "_read_ft_config", return_value={}):
            svc = PaperTradingService(log_dir=tmp_path)
        # Should use defaults
        assert svc._ft_api_url == "http://127.0.0.1:8080"
        assert svc._ft_username == "freqtrader"
