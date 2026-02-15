"""
Tests for Regime Dashboard API — Sprint 2, Item 2.5
====================================================
Covers: RegimeService (with mocked data), API endpoints for
current regime, history, recommendations, and error handling.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from common.regime.regime_detector import Regime, RegimeDetector, RegimeState
from common.regime.strategy_router import StrategyRouter
from app.services.regime import RegimeService


# ── Helpers ──────────────────────────────────────────────────


def _make_synthetic_df(n: int = 500, trend: str = "up") -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    np.random.seed(42)
    if trend == "up":
        close = 100 + np.linspace(0, 50, n) + np.random.randn(n) * 0.5
    elif trend == "down":
        close = 200 - np.linspace(0, 50, n) + np.random.randn(n) * 0.5
    else:
        close = 100 + np.sin(np.linspace(0, 20, n)) * 3 + np.random.randn(n) * 0.3
    high = close + np.abs(np.random.randn(n) * 0.8)
    low = close - np.abs(np.random.randn(n) * 0.8)
    volume = np.random.uniform(1000, 5000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _make_service_with_data(trend: str = "ranging") -> RegimeService:
    """Create RegimeService with mocked data loader."""
    service = RegimeService(symbols=["BTC/USDT", "ETH/USDT"])
    df = _make_synthetic_df(trend=trend)

    with patch.object(service, "_load_data", return_value=df):
        # Prime the cache
        service.get_current_regime("BTC/USDT")
        service.get_current_regime("ETH/USDT")

    return service


# ── RegimeService Unit Tests ─────────────────────────────────


class TestRegimeService:
    def test_get_current_regime_returns_dict(self):
        service = RegimeService(symbols=["BTC/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            result = service.get_current_regime("BTC/USDT")

        assert result is not None
        assert result["symbol"] == "BTC/USDT"
        assert "regime" in result
        assert "confidence" in result
        assert "adx_value" in result

    def test_get_current_regime_no_data(self):
        service = RegimeService(symbols=["BTC/USDT"])
        with patch.object(service, "_load_data", return_value=None):
            result = service.get_current_regime("UNKNOWN/PAIR")
        assert result is None

    def test_get_all_current_regimes(self):
        service = RegimeService(symbols=["BTC/USDT", "ETH/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            results = service.get_all_current_regimes()

        assert len(results) == 2
        symbols = {r["symbol"] for r in results}
        assert "BTC/USDT" in symbols
        assert "ETH/USDT" in symbols

    def test_get_regime_history(self):
        service = RegimeService(symbols=["BTC/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            # Call multiple times to build history
            service.get_current_regime("BTC/USDT")
            service.get_current_regime("BTC/USDT")
            service.get_current_regime("BTC/USDT")

        history = service.get_regime_history("BTC/USDT")
        assert len(history) == 3
        assert "timestamp" in history[0]
        assert "regime" in history[0]
        assert "confidence" in history[0]

    def test_get_regime_history_with_limit(self):
        service = RegimeService(symbols=["BTC/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            for _ in range(5):
                service.get_current_regime("BTC/USDT")

        history = service.get_regime_history("BTC/USDT", limit=2)
        assert len(history) == 2

    def test_get_recommendation(self):
        service = RegimeService(symbols=["BTC/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            result = service.get_recommendation("BTC/USDT")

        assert result is not None
        assert result["symbol"] == "BTC/USDT"
        assert "primary_strategy" in result
        assert "weights" in result
        assert "position_size_modifier" in result

    def test_get_recommendation_no_data(self):
        service = RegimeService(symbols=["BTC/USDT"])
        with patch.object(service, "_load_data", return_value=None):
            result = service.get_recommendation("UNKNOWN/PAIR")
        assert result is None

    def test_get_all_recommendations(self):
        service = RegimeService(symbols=["BTC/USDT", "ETH/USDT"])
        df = _make_synthetic_df(trend="ranging")

        with patch.object(service, "_load_data", return_value=df):
            results = service.get_all_recommendations()

        assert len(results) == 2


# ── API Endpoint Tests (using test client) ───────────────────


@pytest.fixture
def mock_regime_service():
    """Create a RegimeService with mocked data for API tests."""
    service = RegimeService(symbols=["BTC/USDT", "ETH/USDT"])
    df = _make_synthetic_df(trend="ranging")
    # Patch _load_data permanently for this fixture
    service._load_data = MagicMock(return_value=df)
    # Prime cache
    service.get_current_regime("BTC/USDT")
    service.get_current_regime("ETH/USDT")
    return service


@pytest.fixture
async def regime_client(client, mock_regime_service):
    """Test client with mocked RegimeService."""
    from app.deps import get_regime_service

    from app.main import app

    app.dependency_overrides[get_regime_service] = lambda: mock_regime_service
    yield client
    app.dependency_overrides.pop(get_regime_service, None)


class TestRegimeAPI:
    @pytest.mark.asyncio
    async def test_get_all_regimes(self, regime_client):
        resp = await regime_client.get("/api/regime/current")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_single_regime(self, regime_client):
        resp = await regime_client.get("/api/regime/current/BTC/USDT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "BTC/USDT"
        assert "regime" in data
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_position_size_endpoint(self, regime_client):
        resp = await regime_client.post(
            "/api/regime/position-size",
            json={
                "symbol": "BTC/USDT",
                "entry_price": 50000,
                "stop_loss_price": 49000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "position_size" in data
        assert "regime_modifier" in data
        assert "primary_strategy" in data
        assert data["entry_price"] == 50000

    @pytest.mark.asyncio
    async def test_position_size_returns_regime_info(self, regime_client):
        resp = await regime_client.post(
            "/api/regime/position-size",
            json={
                "symbol": "BTC/USDT",
                "entry_price": 100,
                "stop_loss_price": 90,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regime"] != ""
        assert data["regime_modifier"] > 0
        assert data["position_size"] > 0
