"""WebSocket consumers for real-time market data and system events."""

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class MarketTickerConsumer(AsyncJsonWebsocketConsumer):
    """Streams live ticker updates to authenticated clients.

    URL: /ws/market/tickers/
    Group: market_tickers
    """

    async def connect(self):
        if not await self._is_authenticated():
            await self.close(code=4001)
            return

        await self.channel_layer.group_add("market_tickers", self.channel_name)
        await self.accept()

        # Lazily start the ticker poller on first connection
        from market.services.ticker_poller import start_poller

        await start_poller()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("market_tickers", self.channel_name)

    async def ticker_update(self, event):
        """Handle ticker_update messages from the channel layer."""
        await self.send_json(event["data"])

    @database_sync_to_async
    def _is_authenticated(self) -> bool:
        user = self.scope.get("user")
        return user is not None and user.is_authenticated


class SystemEventsConsumer(AsyncJsonWebsocketConsumer):
    """Streams system events: halt status, order updates, risk alerts.

    URL: /ws/system/
    Group: system_events
    """

    async def connect(self):
        if not await self._is_authenticated():
            await self.close(code=4001)
            return

        await self.channel_layer.group_add("system_events", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("system_events", self.channel_name)

    async def halt_status(self, event):
        """Handle halt_status messages."""
        await self.send_json(
            {
                "type": "halt_status",
                "data": event["data"],
            }
        )

    async def order_update(self, event):
        """Handle order_update messages."""
        await self.send_json(
            {
                "type": "order_update",
                "data": event["data"],
            }
        )

    async def risk_alert(self, event):
        """Handle risk_alert messages."""
        await self.send_json(
            {
                "type": "risk_alert",
                "data": event["data"],
            }
        )

    @database_sync_to_async
    def _is_authenticated(self) -> bool:
        user = self.scope.get("user")
        return user is not None and user.is_authenticated
