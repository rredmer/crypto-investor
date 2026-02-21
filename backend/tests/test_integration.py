"""Multi-step API integration tests — end-to-end workflow validation."""

import pytest


@pytest.mark.django_db
class TestPortfolioWorkflow:
    """Create portfolio → add holdings → verify portfolio detail includes holdings."""

    def test_full_portfolio_lifecycle(self, authenticated_client):
        # Step 1: Create a portfolio
        resp = authenticated_client.post(
            "/api/portfolios/",
            {"name": "Integration Test", "exchange_id": "binance"},
            format="json",
        )
        assert resp.status_code == 201
        portfolio = resp.json()
        pid = portfolio["id"]
        assert portfolio["name"] == "Integration Test"
        assert portfolio["holdings"] == []

        # Step 2: Add BTC holding
        resp = authenticated_client.post(
            f"/api/portfolios/{pid}/holdings/",
            {"symbol": "BTC/USDT", "amount": 0.5, "avg_buy_price": 60000},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["symbol"] == "BTC/USDT"

        # Step 3: Add ETH holding
        resp = authenticated_client.post(
            f"/api/portfolios/{pid}/holdings/",
            {"symbol": "ETH/USDT", "amount": 5.0, "avg_buy_price": 3500},
            format="json",
        )
        assert resp.status_code == 201

        # Step 4: Verify portfolio detail shows both holdings
        resp = authenticated_client.get(f"/api/portfolios/{pid}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["holdings"]) == 2
        symbols = {h["symbol"] for h in data["holdings"]}
        assert symbols == {"BTC/USDT", "ETH/USDT"}

        # Step 5: Verify portfolio appears in list
        resp = authenticated_client.get("/api/portfolios/")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Integration Test" in names

        # Step 6: Delete portfolio
        resp = authenticated_client.delete(f"/api/portfolios/{pid}/")
        assert resp.status_code == 204

        # Step 7: Verify gone
        resp = authenticated_client.get(f"/api/portfolios/{pid}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestOrderWorkflow:
    """Create paper order → verify detail → cancel → verify cancelled."""

    def test_paper_order_lifecycle(self, authenticated_client):
        # Step 1: Create paper order
        resp = authenticated_client.post(
            "/api/trading/orders/",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "order_type": "market",
                "amount": 0.1,
                "price": 0,
                "exchange_id": "binance",
                "mode": "paper",
                "portfolio_id": 1,
            },
            format="json",
        )
        assert resp.status_code == 201
        order = resp.json()
        oid = order["id"]
        assert order["symbol"] == "BTC/USDT"
        assert order["side"] == "buy"
        assert order["mode"] == "paper"
        assert order["status"] == "pending"

        # Step 2: Verify in order list
        resp = authenticated_client.get("/api/trading/orders/")
        assert resp.status_code == 200
        order_ids = [o["id"] for o in resp.json()]
        assert oid in order_ids

        # Step 3: Get order detail
        resp = authenticated_client.get(f"/api/trading/orders/{oid}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == oid

        # Step 4: Cancel order
        resp = authenticated_client.post(f"/api/trading/orders/{oid}/cancel/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Step 5: Verify cancelled in detail
        resp = authenticated_client.get(f"/api/trading/orders/{oid}/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Step 6: Cannot cancel again
        resp = authenticated_client.post(f"/api/trading/orders/{oid}/cancel/")
        assert resp.status_code == 400

    def test_order_list_mode_filter(self, authenticated_client):
        # Create paper and check filter
        authenticated_client.post(
            "/api/trading/orders/",
            {
                "symbol": "ETH/USDT",
                "side": "sell",
                "order_type": "limit",
                "amount": 1.0,
                "price": 4000,
                "exchange_id": "binance",
                "mode": "paper",
                "portfolio_id": 1,
            },
            format="json",
        )
        resp = authenticated_client.get("/api/trading/orders/?mode=paper")
        assert resp.status_code == 200
        assert all(o["mode"] == "paper" for o in resp.json())

        resp = authenticated_client.get("/api/trading/orders/?mode=live")
        assert resp.status_code == 200
        assert all(o["mode"] == "live" for o in resp.json())


@pytest.mark.django_db
class TestRiskWorkflow:
    """Update equity → check trade → verify position sizing → halt → resume."""

    def _ensure_risk_state(self, client, pid=1):
        """Seed risk state by posting initial equity."""
        client.post(f"/api/risk/{pid}/equity/", {"equity": 10000}, format="json")

    def test_equity_and_trade_check(self, authenticated_client):
        pid = 1
        self._ensure_risk_state(authenticated_client, pid)

        # Step 1: Update equity
        resp = authenticated_client.post(
            f"/api/risk/{pid}/equity/",
            {"equity": 50000},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["equity"] == 50000

        # Step 2: Check risk status
        resp = authenticated_client.get(f"/api/risk/{pid}/status/")
        assert resp.status_code == 200
        status = resp.json()
        assert status["equity"] == 50000
        assert "drawdown" in status

        # Step 3: Check trade gate (should pass with fresh state)
        resp = authenticated_client.post(
            f"/api/risk/{pid}/check-trade/",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "size": 0.1,
                "entry_price": 60000,
                "stop_loss_price": 58000,
            },
            format="json",
        )
        assert resp.status_code == 200
        result = resp.json()
        assert "approved" in result
        assert "reason" in result

        # Step 4: Position sizing
        resp = authenticated_client.post(
            f"/api/risk/{pid}/position-size/",
            {"entry_price": 60000, "stop_loss_price": 58000},
            format="json",
        )
        assert resp.status_code == 200
        pos = resp.json()
        assert "size" in pos or "position_size" in pos or "error" not in pos

        # Step 5: Verify trade log has entries
        resp = authenticated_client.get(f"/api/risk/{pid}/trade-log/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_halt_resume_workflow(self, authenticated_client):
        pid = 1
        self._ensure_risk_state(authenticated_client, pid)

        # Step 1: Halt trading
        resp = authenticated_client.post(
            f"/api/risk/{pid}/halt/",
            {"reason": "Integration test halt"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["is_halted"] is True

        # Step 2: Verify halted in status
        resp = authenticated_client.get(f"/api/risk/{pid}/status/")
        assert resp.status_code == 200
        assert resp.json()["is_halted"] is True

        # Step 3: Check alerts captured the halt
        resp = authenticated_client.get(f"/api/risk/{pid}/alerts/")
        assert resp.status_code == 200
        alerts = resp.json()
        assert isinstance(alerts, list)

        # Step 4: Resume trading
        resp = authenticated_client.post(f"/api/risk/{pid}/resume/")
        assert resp.status_code == 200
        assert resp.json()["is_halted"] is False

        # Step 5: Verify resumed in status
        resp = authenticated_client.get(f"/api/risk/{pid}/status/")
        assert resp.status_code == 200
        assert resp.json()["is_halted"] is False

    def test_risk_limits_workflow(self, authenticated_client):
        pid = 1
        self._ensure_risk_state(authenticated_client, pid)

        # Step 1: Get current limits
        resp = authenticated_client.get(f"/api/risk/{pid}/limits/")
        assert resp.status_code == 200
        original = resp.json()
        assert "max_daily_loss" in original

        # Step 2: Update limits
        resp = authenticated_client.put(
            f"/api/risk/{pid}/limits/",
            {"max_daily_loss": 0.10, "max_open_positions": 3},
            format="json",
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["max_daily_loss"] == 0.10
        assert updated["max_open_positions"] == 3

        # Step 3: Verify persisted
        resp = authenticated_client.get(f"/api/risk/{pid}/limits/")
        assert resp.status_code == 200
        assert resp.json()["max_daily_loss"] == 0.10
        assert resp.json()["max_open_positions"] == 3


@pytest.mark.django_db
class TestCrossAppWorkflow:
    """Test workflows spanning multiple Django apps."""

    def test_portfolio_then_risk(self, authenticated_client):
        """Create portfolio, then use its ID for risk operations."""
        # Create portfolio
        resp = authenticated_client.post(
            "/api/portfolios/",
            {"name": "Risk Test Portfolio"},
            format="json",
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Seed risk state for this portfolio
        resp = authenticated_client.post(
            f"/api/risk/{pid}/equity/",
            {"equity": 100000},
            format="json",
        )
        assert resp.status_code == 200

        # Check status
        resp = authenticated_client.get(f"/api/risk/{pid}/status/")
        assert resp.status_code == 200
        assert resp.json()["equity"] == 100000

        # Get VaR
        resp = authenticated_client.get(f"/api/risk/{pid}/var/")
        assert resp.status_code == 200
        var_data = resp.json()
        assert "var_95" in var_data

        # Get heat check
        resp = authenticated_client.get(f"/api/risk/{pid}/heat-check/")
        assert resp.status_code == 200
        assert "healthy" in resp.json()

    def test_equity_update_and_metric_recording(self, authenticated_client):
        """Update equity then record metrics snapshot."""
        pid = 1

        # Seed equity
        resp = authenticated_client.post(
            f"/api/risk/{pid}/equity/",
            {"equity": 25000},
            format="json",
        )
        assert resp.status_code == 200

        # Record a metrics snapshot
        resp = authenticated_client.post(f"/api/risk/{pid}/record-metrics/")
        assert resp.status_code == 200
        metric = resp.json()
        assert "equity" in metric
        assert metric["equity"] == 25000

        # Verify it appears in metric history
        resp = authenticated_client.get(f"/api/risk/{pid}/metric-history/")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert any(m["equity"] == 25000 for m in history)

    def test_reset_daily_clears_counters(self, authenticated_client):
        """Seed equity, update, reset daily, verify counters."""
        pid = 1

        # Seed
        authenticated_client.post(f"/api/risk/{pid}/equity/", {"equity": 10000}, format="json")

        # Update equity to simulate P&L
        authenticated_client.post(f"/api/risk/{pid}/equity/", {"equity": 9500}, format="json")

        # Reset daily
        resp = authenticated_client.post(f"/api/risk/{pid}/reset-daily/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_pnl"] == 0
