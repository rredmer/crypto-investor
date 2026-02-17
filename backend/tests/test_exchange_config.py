"""Tests for ExchangeConfig and DataSourceConfig — encryption, API security, CRUD."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.db import connection

from market.fields import EncryptedTextField
from market.models import DataSourceConfig, ExchangeConfig

# ── EncryptedTextField ───────────────────────────────────────


@pytest.mark.django_db
class TestEncryptedTextField:
    def test_round_trip(self):
        """Value is decrypted when read back from DB."""
        config = ExchangeConfig.objects.create(
            name="Test", exchange_id="binance", api_key="my-secret-key-12345"
        )
        config.refresh_from_db()
        assert config.api_key == "my-secret-key-12345"

    def test_raw_db_value_is_ciphertext(self):
        """Raw database value should be encrypted, not plaintext."""
        config = ExchangeConfig.objects.create(
            name="Test", exchange_id="binance", api_key="plaintext-secret"
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT api_key FROM market_exchangeconfig WHERE id = %s",
                [config.pk],
            )
            raw_value = cursor.fetchone()[0]
        assert raw_value != "plaintext-secret"
        assert raw_value != ""
        # Fernet tokens start with gAAAAA
        assert raw_value.startswith("gAAAAA")

    def test_empty_string_not_encrypted(self):
        """Empty strings should pass through unchanged."""
        config = ExchangeConfig.objects.create(
            name="Test", exchange_id="binance", api_key=""
        )
        config.refresh_from_db()
        assert config.api_key == ""

    def test_none_not_encrypted(self):
        """None should pass through unchanged."""
        field = EncryptedTextField()
        assert field.get_prep_value(None) is None


# ── API Security ─────────────────────────────────────────────


@pytest.mark.django_db
class TestExchangeConfigAPISecurity:
    def test_credentials_not_in_response(self, authenticated_client):
        """API response must never contain raw credentials."""
        ExchangeConfig.objects.create(
            name="Test", exchange_id="binance",
            api_key="super-secret-key-abc123",
            api_secret="super-secret-secret-xyz",
            passphrase="my-passphrase",
        )
        resp = authenticated_client.get("/api/exchange-configs/")
        assert resp.status_code == 200
        data = resp.json()[0]
        assert "api_key" not in data
        assert "api_secret" not in data
        assert "passphrase" not in data

    def test_masked_key_format(self, authenticated_client):
        """Masked key should show first4****last4."""
        ExchangeConfig.objects.create(
            name="Test", exchange_id="binance",
            api_key="abcdefghijklmnop",
        )
        resp = authenticated_client.get("/api/exchange-configs/")
        data = resp.json()[0]
        assert data["api_key_masked"] == "abcd****mnop"

    def test_short_key_masked_as_stars(self, authenticated_client):
        """Keys 8 chars or fewer are masked as ****."""
        ExchangeConfig.objects.create(
            name="Test", exchange_id="binance", api_key="short"
        )
        resp = authenticated_client.get("/api/exchange-configs/")
        data = resp.json()[0]
        assert data["api_key_masked"] == "****"

    def test_has_credential_booleans(self, authenticated_client):
        """has_api_key, has_api_secret, has_passphrase booleans exposed."""
        ExchangeConfig.objects.create(
            name="Test", exchange_id="binance",
            api_key="key123456789", api_secret="secret123",
        )
        resp = authenticated_client.get("/api/exchange-configs/")
        data = resp.json()[0]
        assert data["has_api_key"] is True
        assert data["has_api_secret"] is True
        assert data["has_passphrase"] is False

    def test_unauthenticated_returns_401(self, api_client):
        """Unauthenticated requests should return 401 or 403."""
        resp = api_client.get("/api/exchange-configs/")
        assert resp.status_code in (401, 403)


# ── CRUD ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExchangeConfigCRUD:
    def test_create(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/exchange-configs/",
            {"name": "My Binance", "exchange_id": "binance", "api_key": "key123456789"},
            format="json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Binance"
        assert data["exchange_id"] == "binance"
        assert data["is_sandbox"] is True  # safe default
        assert "api_key" not in data

    def test_list(self, authenticated_client):
        ExchangeConfig.objects.create(name="A", exchange_id="binance")
        ExchangeConfig.objects.create(name="B", exchange_id="kraken")
        resp = authenticated_client.get("/api/exchange-configs/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_detail(self, authenticated_client):
        config = ExchangeConfig.objects.create(name="A", exchange_id="binance")
        resp = authenticated_client.get(f"/api/exchange-configs/{config.pk}/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "A"

    def test_update(self, authenticated_client):
        config = ExchangeConfig.objects.create(
            name="Old", exchange_id="binance", api_key="original-key-1234"
        )
        resp = authenticated_client.put(
            f"/api/exchange-configs/{config.pk}/",
            {"name": "New Name"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_partial_update_preserves_credentials(self, authenticated_client):
        """Updating name without sending credentials should keep them."""
        config = ExchangeConfig.objects.create(
            name="Old", exchange_id="binance",
            api_key="keep-this-key-123", api_secret="keep-this-secret",
        )
        authenticated_client.put(
            f"/api/exchange-configs/{config.pk}/",
            {"name": "New Name"},
            format="json",
        )
        config.refresh_from_db()
        assert config.api_key == "keep-this-key-123"
        assert config.api_secret == "keep-this-secret"

    def test_delete(self, authenticated_client):
        config = ExchangeConfig.objects.create(name="Delete Me", exchange_id="binance")
        resp = authenticated_client.delete(f"/api/exchange-configs/{config.pk}/")
        assert resp.status_code == 204
        assert not ExchangeConfig.objects.filter(pk=config.pk).exists()

    def test_not_found(self, authenticated_client):
        resp = authenticated_client.get("/api/exchange-configs/9999/")
        assert resp.status_code == 404


# ── Default uniqueness ───────────────────────────────────────


@pytest.mark.django_db
class TestExchangeConfigDefault:
    def test_only_one_default(self):
        """Setting a new default should unset the previous one."""
        a = ExchangeConfig.objects.create(
            name="A", exchange_id="binance", is_default=True
        )
        b = ExchangeConfig.objects.create(
            name="B", exchange_id="kraken", is_default=True
        )
        a.refresh_from_db()
        assert a.is_default is False
        assert b.is_default is True


# ── Connectivity test ────────────────────────────────────────


@pytest.mark.django_db
class TestExchangeConfigTest:
    def test_test_endpoint(self, authenticated_client):
        config = ExchangeConfig.objects.create(
            name="Test", exchange_id="binance", api_key="key123456789"
        )

        mock_exchange = MagicMock()
        mock_exchange.load_markets = AsyncMock()
        mock_exchange.markets = {"BTC/USDT": {}, "ETH/USDT": {}}
        mock_exchange.close = AsyncMock()
        mock_exchange.set_sandbox_mode = MagicMock()

        with patch("ccxt.async_support.binance", return_value=mock_exchange):
            resp = authenticated_client.post(
                f"/api/exchange-configs/{config.pk}/test/"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["markets_count"] == 2

    def test_test_endpoint_not_found(self, authenticated_client):
        resp = authenticated_client.post("/api/exchange-configs/9999/test/")
        assert resp.status_code == 404


# ── Data Sources ─────────────────────────────────────────────


@pytest.mark.django_db
class TestDataSourceConfig:
    def test_create(self, authenticated_client):
        config = ExchangeConfig.objects.create(name="Binance", exchange_id="binance")
        resp = authenticated_client.post(
            "/api/data-sources/",
            {
                "exchange_config": config.pk,
                "symbols": ["BTC/USDT", "ETH/USDT"],
                "timeframes": ["1h", "4h"],
                "fetch_interval_minutes": 30,
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbols"] == ["BTC/USDT", "ETH/USDT"]
        assert data["timeframes"] == ["1h", "4h"]
        assert data["exchange_name"] == "Binance"

    def test_list(self, authenticated_client):
        config = ExchangeConfig.objects.create(name="Binance", exchange_id="binance")
        DataSourceConfig.objects.create(
            exchange_config=config, symbols=["BTC/USDT"], timeframes=["1h"]
        )
        resp = authenticated_client.get("/api/data-sources/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_cascade_delete(self):
        """Deleting an exchange config should delete its data sources."""
        config = ExchangeConfig.objects.create(name="Binance", exchange_id="binance")
        DataSourceConfig.objects.create(
            exchange_config=config, symbols=["BTC/USDT"], timeframes=["1h"]
        )
        config.delete()
        assert DataSourceConfig.objects.count() == 0

    def test_delete(self, authenticated_client):
        config = ExchangeConfig.objects.create(name="Binance", exchange_id="binance")
        ds = DataSourceConfig.objects.create(
            exchange_config=config, symbols=["BTC/USDT"], timeframes=["1h"]
        )
        resp = authenticated_client.delete(f"/api/data-sources/{ds.pk}/")
        assert resp.status_code == 204
