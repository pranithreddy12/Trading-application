import asyncio
from loguru import logger
from binance import AsyncClient, BinanceSocketManager
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


class BinanceIngestionClient:
    def __init__(self):
        self.settings = get_settings()

        crypto_pairs = self.settings.crypto_pairs
        if isinstance(crypto_pairs, str):
            self.pairs = [
                s.strip().upper() for s in crypto_pairs.split(",") if s.strip()
            ]
        else:
            self.pairs = [s.upper() for s in crypto_pairs]

        self.timescale = TimescaleClient(self.settings.database_url)
        self.reconnect_delay = 2

    async def connect_and_listen(self):
        while True:
            client = None
            try:
                logger.info("Connecting to Binance WebSocket...")
                client = await AsyncClient.create(
                    api_key=self.settings.binance_api_key,
                    api_secret=self.settings.binance_secret,
                )
                bsm = BinanceSocketManager(client)

                streams = []
                for pair in self.pairs:
                    streams.append(f"{pair.lower()}@trade")
                    streams.append(f"{pair.lower()}@depth20@100ms")

                async with bsm.multiplex_socket(streams) as ts:
                    self.reconnect_delay = 2
                    logger.info("Binance WebSocket connected.")

                    while True:
                        res = await ts.recv()
                        await self._handle_message(res)

            except Exception as e:
                logger.error(
                    f"Binance WebSocket error: {e}. Reconnecting in {self.reconnect_delay}s..."
                )
            finally:
                if client:
                    await client.close_connection()

            await asyncio.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    async def _handle_message(self, data: dict):
        try:
            if "stream" in data and "data" in data:
                raw = data["data"]
            else:
                raw = data

            event_type = raw.get("e")
            if event_type == "trade":
                model = normalize_trade(raw, "binance")
                trade = TradeData(
                    time=datetime.fromtimestamp(model.timestamp / 1000.0),
                    symbol=model.symbol,
                    price=model.price,
                    size=model.size,
                    side="unknown",
                    exchange="binance",
                    source=model.source,
                )
                await self.timescale.write_trade(trade)
            elif event_type == "depthUpdate" or "lastUpdateId" in raw:
                model = normalize_orderbook(raw, "binance")
                ob = OrderbookData(
                    time=datetime.fromtimestamp(model.timestamp / 1000.0),
                    symbol=model.symbol,
                    bids={str(model.bid_price): model.bid_size},
                    asks={str(model.ask_price): model.ask_size},
                    spread=model.ask_price - model.bid_price,
                    mid_price=(model.bid_price + model.ask_price) / 2.0,
                )
                await self.timescale.write_orderbook(model.symbol, ob)
            elif event_type == "kline" or "k" in raw:
                model = normalize_bar(raw, "binance")
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
        except Exception as e:
            logger.error(f"Error processing Binance message: {e}")

    async def start(self):
        await self.connect_and_listen()
