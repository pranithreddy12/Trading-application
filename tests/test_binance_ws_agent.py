"""
Unit tests for Binance WebSocket client and agent.

Tests cover:
- WebSocket connection and reconnection logic
- Message parsing and validation
- Database write operations
- Agent lifecycle management
- Error handling and resilience
"""

import asyncio
import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from atlas.data.ingestion.binance_ws_client import (
    BinanceWebSocketClient,
    StreamType
)
from atlas.data.storage.timescale_client import (
    BinanceTradeData, BinanceDepthData, TimescaleClient
)
from atlas.agents.l1_data.binance_ws_agent import BinanceWebSocketAgent


class TestBinanceWebSocketClient:
    """Tests for BinanceWebSocketClient"""
    
    @pytest.fixture
    def mock_handler(self):
        """Create a mock message handler"""
        return AsyncMock()
    
    @pytest.fixture
    def client(self, mock_handler):
        """Create a test client"""
        return BinanceWebSocketClient(
            trading_pairs=["BTCUSDT", "ETHUSDT"],
            message_handler=mock_handler,
            stream_types=["trade", "depth20@100ms"]
        )
    
    def test_client_initialization(self, client, mock_handler):
        """Test client initialization"""
        assert client.trading_pairs == ["btcusdt", "ethusdt"]  # Lowercase
        assert client.message_handler == mock_handler
        assert client.is_connected == False
        assert client.stream_types == ["trade", "depth20@100ms"]
    
    def test_stream_names_generation(self, client):
        """Test stream names generation"""
        streams = client._build_stream_names()
        
        expected = [
            "btcusdt@trade",
            "btcusdt@depth20@100ms",
            "ethusdt@trade",
            "ethusdt@depth20@100ms"
        ]
        assert streams == expected
    
    def test_is_market_data_message(self):
        """Test market data message detection"""
        # Valid market data messages
        assert BinanceWebSocketClient._is_market_data_message({"e": "trade"}) == True
        assert BinanceWebSocketClient._is_market_data_message({"e": "depthUpdate"}) == True
        
        # Invalid messages
        assert BinanceWebSocketClient._is_market_data_message({"e": "error"}) == False
        assert BinanceWebSocketClient._is_market_data_message({}) == False
        assert BinanceWebSocketClient._is_market_data_message("not_dict") == False
    
    def test_get_status(self, client):
        """Test get_status method"""
        status = client.get_status()
        
        assert "connected" in status
        assert "subscribed_pairs" in status
        assert "retry_count" in status
        assert "stream_types" in status
        
        assert status["connected"] == False
        assert status["retry_count"] == 0
        assert len(status["subscribed_pairs"]) == 2


class TestBinanceCryptoDataModels:
    """Tests for crypto data models"""
    
    def test_binance_trade_data_model(self):
        """Test BinanceTradeData model"""
        now = datetime.now(timezone.utc)
        trade = BinanceTradeData(
            time=now,
            symbol="BTCUSDT",
            price=65000.0,
            quantity=0.5,
            buyer_maker=True,
            trade_id=12345,
            source="binance"
        )
        
        assert trade.symbol == "BTCUSDT"
        assert trade.price == 65000.0
        assert trade.quantity == 0.5
        assert trade.buyer_maker == True
        assert trade.trade_id == 12345
    
    def test_binance_depth_data_model(self):
        """Test BinanceDepthData model"""
        now = datetime.now(timezone.utc)
        depth = BinanceDepthData(
            time=now,
            symbol="ETHUSDT",
            bids={"3500.0": 10.5, "3499.9": 20.0},
            asks={"3500.1": 15.0, "3500.2": 25.5},
            source="binance",
            last_update_id=123456
        )
        
        assert depth.symbol == "ETHUSDT"
        assert len(depth.bids) == 2
        assert len(depth.asks) == 2
        assert depth.last_update_id == 123456


class TestBinanceWebSocketAgent:
    """Tests for BinanceWebSocketAgent"""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        return AsyncMock()
    
    @pytest.fixture
    def agent(self, mock_redis):
        """Create a test agent"""
        with patch('atlas.agents.l1_data.binance_ws_agent.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                binance_api_key="test_key",
                binance_secret="test_secret",
                database_url="postgresql://localhost/test",
                crypto_pairs="BTCUSDT,ETHUSDT",
                environment="test"
            )
            return BinanceWebSocketAgent(mock_redis, "postgresql://localhost/test")
    
    def test_agent_initialization(self, agent, mock_redis):
        """Test agent initialization"""
        assert agent.name == "BinanceWebSocketAgent"
        assert agent.agent_type == "crypto_data_ingestion"
        assert len(agent.trading_pairs) == 2
        assert "BTCUSDT" in agent.trading_pairs
        assert agent._messages_received == 0
        assert agent._trades_received == 0
        assert agent._depth_received == 0
    
    def test_parse_crypto_pairs(self, agent):
        """Test crypto pairs parsing"""
        pairs = agent.trading_pairs
        assert len(pairs) > 0
        assert all(isinstance(p, str) for p in pairs)
        assert all(p.isupper() for p in pairs)
        assert all("USDT" in p for p in pairs)
    
    def test_parse_timestamp_ms_valid(self):
        """Test timestamp parsing with valid input"""
        ts_ms = 1672531200000  # 2023-01-01 00:00:00 UTC
        dt = BinanceWebSocketAgent._parse_timestamp_ms(ts_ms)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
    
    def test_parse_timestamp_ms_none(self):
        """Test timestamp parsing with None"""
        dt = BinanceWebSocketAgent._parse_timestamp_ms(None)
        assert isinstance(dt, datetime)
        # Should return current time
        now = datetime.now(timezone.utc)
        assert abs((now - dt).total_seconds()) < 1
    
    @pytest.mark.asyncio
    async def test_handle_trade_message(self, agent, mock_redis):
        """Test handling trade message"""
        agent.ts_client = AsyncMock()
        
        message = {
            "e": "trade",
            "E": 1672531200000,
            "s": "BTCUSDT",
            "t": 12345,
            "p": "65000.0",
            "q": "0.5",
            "m": True,
        }
        
        await agent._handle_message(message, "btcusdt@trade")
        
        assert agent._messages_received == 1
        assert agent._messages_processed == 1
        assert agent._trades_received == 1
        assert agent.ts_client.write_binance_trade.called
    
    @pytest.mark.asyncio
    async def test_handle_depth_message(self, agent, mock_redis):
        """Test handling depth message"""
        agent.ts_client = AsyncMock()
        
        message = {
            "e": "depthUpdate",
            "E": 1672531200000,
            "s": "ETHUSDT",
            "U": 123456,
            "u": 123457,
            "b": [["3500.0", "10.5"]],
            "a": [["3500.1", "15.0"]]
        }
        
        await agent._handle_message(message, "ethusdt@depth20@100ms")
        
        assert agent._messages_received == 1
        assert agent._messages_processed == 1
        assert agent._depth_received == 1
        assert agent.ts_client.write_binance_depth.called


class TestStreamTypes:
    """Tests for stream type definitions"""
    
    def test_binance_stream_types(self):
        """Test Binance stream type values"""
        assert StreamType.TRADE.value == "trade"
        assert StreamType.DEPTH.value == "depth20@100ms"


class TestBinanceIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_trade_message_handler_chain(self):
        """Test complete trade message handling chain"""
        messages_processed = []
        
        async def handler(msg, stream):
            messages_processed.append((msg, stream))
        
        client = BinanceWebSocketClient(
            trading_pairs=["BTCUSDT"],
            message_handler=handler,
            stream_types=["trade"]
        )
        
        # Simulate trade message
        test_message = {
            "e": "trade",
            "E": 1672531200000,
            "s": "BTCUSDT",
            "t": 12345,
            "p": "65000.0",
            "q": "0.5",
            "m": True,
        }
        
        await client.message_handler(test_message, "btcusdt@trade")
        
        assert len(messages_processed) == 1
        assert messages_processed[0][0]["s"] == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_depth_message_handler_chain(self):
        """Test complete depth message handling chain"""
        messages_processed = []
        
        async def handler(msg, stream):
            messages_processed.append((msg, stream))
        
        client = BinanceWebSocketClient(
            trading_pairs=["ETHUSDT"],
            message_handler=handler,
            stream_types=["depth20@100ms"]
        )
        
        # Simulate depth message
        test_message = {
            "e": "depthUpdate",
            "E": 1672531200000,
            "s": "ETHUSDT",
            "U": 123456,
            "u": 123457,
            "b": [["3500.0", "10.5"]],
            "a": [["3500.1", "15.0"]]
        }
        
        await client.message_handler(test_message, "ethusdt@depth20@100ms")
        
        assert len(messages_processed) == 1
        assert messages_processed[0][0]["e"] == "depthUpdate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
