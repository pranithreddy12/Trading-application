import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from atlas.data.ingestion.data_normalizer import (
    normalize_bar, normalize_orderbook, normalize_trade,
    MarketDataL1, MarketDataL2, OrderFlow
)
from atlas.data.ingestion.polygon_client import PolygonIngestionClient
from atlas.data.ingestion.binance_client import BinanceIngestionClient

def test_normalize_bar_polygon():
    raw = {'sym': 'AAPL', 'o': 150.0, 'h': 155.0, 'l': 149.0, 'c': 154.0, 'v': 1000, 'e': 1620000000000}
    res = normalize_bar(raw, 'polygon')
    assert isinstance(res, MarketDataL1)
    assert res.symbol == 'AAPL'
    assert res.close == 154.0

def test_normalize_bar_binance():
    raw = {'s': 'BTCUSDT', 'k': {'t': 1620000000000, 'o': '50000', 'h': '51000', 'l': '49000', 'c': '50500', 'v': '100'}}
    res = normalize_bar(raw, 'binance')
    assert isinstance(res, MarketDataL1)
    assert res.symbol == 'BTCUSDT'
    assert res.close == 50500.0

def test_normalize_bar_invalid():
    with pytest.raises(ValueError):
        normalize_bar({}, 'unknown')

def test_normalize_orderbook_polygon():
    raw = {'sym': 'AAPL', 'bp': 150.0, 'bs': 10, 'ap': 150.1, 'as': 15, 't': 1620000000000}
    res = normalize_orderbook(raw, 'polygon')
    assert isinstance(res, MarketDataL2)
    assert res.bid_price == 150.0
    assert res.ask_size == 15.0

def test_normalize_orderbook_binance():
    raw = {'s': 'BTCUSDT', 'b': [['50000', '1.0']], 'a': [['50010', '2.0']], 'E': 1620000000000}
    res = normalize_orderbook(raw, 'binance')
    assert isinstance(res, MarketDataL2)
    assert res.bid_price == 50000.0
    assert res.ask_size == 2.0

def test_normalize_orderbook_invalid():
    with pytest.raises(ValueError):
        normalize_orderbook({}, 'unknown')

def test_normalize_trade_polygon():
    raw = {'sym': 'AAPL', 'p': 150.0, 's': 100, 't': 1620000000000, 'c': [1, 2]}
    res = normalize_trade(raw, 'polygon')
    assert isinstance(res, OrderFlow)
    assert res.price == 150.0
    assert res.conditions == [1, 2]

def test_normalize_trade_binance():
    raw = {'s': 'BTCUSDT', 'p': '50000', 'q': '1.5', 'E': 1620000000000}
    res = normalize_trade(raw, 'binance')
    assert isinstance(res, OrderFlow)
    assert res.price == 50000.0

def test_normalize_trade_invalid():
    with pytest.raises(ValueError):
        normalize_trade({}, 'unknown')

@pytest.mark.asyncio
@patch("atlas.data.ingestion.polygon_client.TimescaleClient")
@patch("atlas.data.ingestion.polygon_client.asyncio.sleep", new_callable=AsyncMock)
@patch("atlas.data.ingestion.polygon_client.websockets.connect")
async def test_polygon_simulated_disconnect(mock_connect, mock_sleep, mock_timescale):
    mock_connect.side_effect = [Exception("Simulated disconnect 1"), Exception("Simulated disconnect 2")]
    mock_sleep.side_effect = [None, Exception("Stop loop")]
    
    with patch("atlas.data.ingestion.polygon_client.get_settings") as mock_settings:
        mock_settings.return_value.polygon_api_key = "test"
        mock_settings.return_value.watchlist = "AAPL,MSFT"
        mock_settings.return_value.database_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        
        client = PolygonIngestionClient()
        
        with pytest.raises(Exception, match="Stop loop"):
            await client.start()
        
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 2
        assert mock_sleep.call_args_list[1][0][0] == 4

@pytest.mark.asyncio
@patch("atlas.data.ingestion.binance_client.TimescaleClient")
@patch("atlas.data.ingestion.binance_client.asyncio.sleep", new_callable=AsyncMock)
@patch("atlas.data.ingestion.binance_client.AsyncClient.create", new_callable=AsyncMock)
async def test_binance_simulated_disconnect(mock_create, mock_sleep, mock_timescale):
    mock_create.side_effect = [Exception("Simulated disconnect 1"), Exception("Simulated disconnect 2")]
    mock_sleep.side_effect = [None, Exception("Stop loop")]
    
    with patch("atlas.data.ingestion.binance_client.get_settings") as mock_settings:
        mock_settings.return_value.binance_api_key = "test"
        mock_settings.return_value.binance_secret = "test"
        mock_settings.return_value.crypto_pairs = "BTCUSDT,ETHUSDT"
        mock_settings.return_value.database_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        
        client = BinanceIngestionClient()
        
        with pytest.raises(Exception, match="Stop loop"):
            await client.start()
        
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 2
        assert mock_sleep.call_args_list[1][0][0] == 4
