"""Exchange service — wraps ccxt for async market data access."""

import logging
from datetime import datetime, timezone

import ccxt.async_support as ccxt
from django.conf import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXCHANGES = ["binance", "coinbase", "kraken", "kucoin", "bybit"]


def _load_db_config(config_id: int | None = None):
    """Load ExchangeConfig from DB. Returns None if unavailable."""
    try:
        from market.models import ExchangeConfig

        if config_id is not None:
            return ExchangeConfig.objects.get(pk=config_id, is_active=True)
        return ExchangeConfig.objects.filter(is_default=True, is_active=True).first()
    except Exception:
        return None


class ExchangeService:
    def __init__(self, exchange_id: str | None = None, config_id: int | None = None) -> None:
        self._db_config = _load_db_config(config_id)
        if self._db_config:
            self._exchange_id = self._db_config.exchange_id
        else:
            self._exchange_id = exchange_id or settings.EXCHANGE_ID
        self._exchange: ccxt.Exchange | None = None

    async def _get_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            exchange_class = getattr(ccxt, self._exchange_id)
            config: dict[str, object] = {"enableRateLimit": True}

            if self._db_config and self._db_config.api_key:
                config["apiKey"] = self._db_config.api_key
                config["secret"] = self._db_config.api_secret
                if self._db_config.passphrase:
                    config["password"] = self._db_config.passphrase
                if self._db_config.is_sandbox:
                    config["sandbox"] = True
                if self._db_config.options:
                    config["options"] = self._db_config.options
            elif settings.EXCHANGE_API_KEY:
                config["apiKey"] = settings.EXCHANGE_API_KEY
                config["secret"] = settings.EXCHANGE_API_SECRET

            self._exchange = exchange_class(config)

            if self._db_config and self._db_config.is_sandbox:
                self._exchange.set_sandbox_mode(True)
        return self._exchange

    async def close(self) -> None:
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None

    def list_exchanges(self) -> list[dict]:
        result = []
        for eid in SUPPORTED_EXCHANGES:
            exchange_class = getattr(ccxt, eid)
            ex = exchange_class()
            result.append(
                {
                    "id": eid,
                    "name": ex.name,
                    "countries": getattr(ex, "countries", []) or [],
                    "has_fetch_tickers": ex.has.get("fetchTickers", False),
                    "has_fetch_ohlcv": ex.has.get("fetchOHLCV", False),
                }
            )
        return result

    async def fetch_ticker(self, symbol: str) -> dict:
        from core.services.metrics import timed

        exchange = await self._get_exchange()
        labels = {"method": "fetch_ticker", "exchange": self._exchange_id}
        with timed("exchange_api_latency_seconds", labels):
            ticker = await exchange.fetch_ticker(symbol)
        return {
            "symbol": ticker["symbol"],
            "price": ticker["last"] or 0.0,
            "volume_24h": ticker.get("quoteVolume") or 0.0,
            "change_24h": ticker.get("percentage") or 0.0,
            "high_24h": ticker.get("high") or 0.0,
            "low_24h": ticker.get("low") or 0.0,
            "timestamp": datetime.fromtimestamp(
                (ticker["timestamp"] or 0) / 1000, tz=timezone.utc
            ).isoformat(),
        }

    async def fetch_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        from core.services.metrics import timed

        exchange = await self._get_exchange()
        labels = {"method": "fetch_tickers", "exchange": self._exchange_id}
        with timed("exchange_api_latency_seconds", labels):
            tickers = await exchange.fetch_tickers(symbols)
        result = []
        for ticker in tickers.values():
            result.append(
                {
                    "symbol": ticker["symbol"],
                    "price": ticker["last"] or 0.0,
                    "volume_24h": ticker.get("quoteVolume") or 0.0,
                    "change_24h": ticker.get("percentage") or 0.0,
                    "high_24h": ticker.get("high") or 0.0,
                    "low_24h": ticker.get("low") or 0.0,
                    "timestamp": datetime.fromtimestamp(
                        (ticker["timestamp"] or 0) / 1000, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return result

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list[dict]:
        from core.services.metrics import timed

        exchange = await self._get_exchange()
        labels = {"method": "fetch_ohlcv", "exchange": self._exchange_id}
        with timed("exchange_api_latency_seconds", labels):
            data = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [
            {
                "timestamp": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5],
            }
            for candle in data
        ]
