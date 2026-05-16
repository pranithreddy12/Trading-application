import asyncio
import json
import websockets
from loguru import logger
from datetime import datetime

from atlas.config.settings import get_settings
from atlas.data.ingestion.data_normalizer import (
    normalize_bar,
    normalize_orderbook,
    normalize_trade,
)
from atlas.data.storage.timescale_client import (
    TimescaleClient,
    BarData,
    OrderbookData,
    TradeData,
)


class PolygonIngestionClient:
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.polygon_api_key

        watchlist = self.settings.watchlist
        if isinstance(watchlist, str):
            self.watchlist = [s.strip() for s in watchlist.split(",") if s.strip()]
        else:
            self.watchlist = watchlist

        self.timescale = TimescaleClient(self.settings.database_url)
        self.uri = "wss://delayed.polygon.io/stocks"
        self.reconnect_delay = 2

    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            if not isinstance(data, list):
                data = [data]

            for raw in data:
                event_type = raw.get("ev")
                if event_type in ("A", "AM"):
                    model = normalize_bar(raw, "polygon")
                    bar = BarData(
                        time=datetime.fromtimestamp(model.timestamp / 1000.0),
                        symbol=model.symbol,
                        open=model.open,
                        high=model.high,
                        low=model.low,
                        close=model.close,
                        volume=model.volume,
                        source=model.source,
                        interval="1m",
                        asset_class=model.asset_class,
                    )
                    await self.timescale.write_bars(model.symbol, bar)
                elif event_type == "Q":
                    model = normalize_orderbook(raw, "polygon")
                    ob = OrderbookData(
                        time=datetime.fromtimestamp(model.timestamp / 1000.0),
                        symbol=model.symbol,
                        bids={str(model.bid_price): model.bid_size},
                        asks={str(model.ask_price): model.ask_size},
                        spread=model.ask_price - model.bid_price,
                        mid_price=(model.bid_price + model.ask_price) / 2.0,
                    )
                    await self.timescale.write_orderbook(model.symbol, ob)
                elif event_type == "T":
                    model = normalize_trade(raw, "polygon")
                    trade = TradeData(
                        time=datetime.fromtimestamp(model.timestamp / 1000.0),
                        symbol=model.symbol,
                        price=model.price,
                        size=model.size,
                        side="unknown",
                        exchange="polygon",
                        source=model.source,
                    )
                    await self.timescale.write_trade(trade)
        except Exception as e:
            logger.error(f"Error processing Polygon message: {e}")

    async def connect_and_listen(self):
        while True:
            try:
                logger.info("Connecting to Polygon WebSocket...")
                async with websockets.connect(self.uri) as ws:
                    auth_payload = {"action": "auth", "params": self.api_key}
                    await ws.send(json.dumps(auth_payload))

                    subs = ["Q.*", "T.*", "A.*"]
                    sub_payload = {"action": "subscribe", "params": ",".join(subs)}
                    await ws.send(json.dumps(sub_payload))

                    self.reconnect_delay = 2  # Reset
                    logger.info("Polygon WebSocket connected.")

                    async for message in ws:
                        await self._handle_message(message)

            except Exception as e:
                logger.error(
                    f"Polygon WebSocket error: {e}. Reconnecting in {self.reconnect_delay}s..."
                )

            await asyncio.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    async def start(self):
        await self.connect_and_listen()
