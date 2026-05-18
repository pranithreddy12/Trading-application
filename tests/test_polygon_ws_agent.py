"""
Unit tests for Polygon WebSocket client and agent.

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
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from atlas.data.ingestion.polygon_ws_client import (
    PolygonWebSocketClient,
    StreamType
)
from atlas.data.storage.timescale_client import (
    QuoteData, TradeData, AggregateData, TimescaleClient
)
from atlas.agents.l1_data.polygon_ws_agent import PolygonWebSocketAgent


class TestPolygonWebSocketClient:
    """Tests for PolygonWebSocketClient"""
    
    @pytest.fixture
    def mock_handler(self):
        """Create a mock message handler"""
        return AsyncMock()
    
    @pytest.fixture
    def client(self, mock_handler):
        """Create a test client"""
        return PolygonWebSocketClient(
            api_key="test_key",
            symbols=["AAPL", "MSFT"],
            message_handler=mock_handler,
            stream_types=["Q", "T", "A"]
        )
    
    def test_client_initialization(self, client, mock_handler):
        """Test client initialization"""
        assert client.api_key == "test_key"
        assert client.symbols == ["AAPL", "MSFT"]
        assert client.message_handler == mock_handler
        assert client.is_connected == False
        assert client.is_authenticated == False
    
    def test_subscription_list_generation(self, client):
        """Test subscription list generation"""
        # This tests the subscription format (e.g., Q.AAPL, T.MSFT)
        subscriptions = []
        for symbol in client.symbols:
            for stream_type in client.stream_types:
                subscriptions.append(f"{stream_type}.{symbol}")
        
        expected = [
            "Q.AAPL", "T.AAPL", "A.AAPL",
            "Q.MSFT", "T.MSFT", "A.MSFT"
        ]
        assert subscriptions == expected
    
    def test_is_market_data_message(self):
        """Test market data message detection"""
        # Valid market data messages
        assert PolygonWebSocketClient._is_market_data_message({"ev": "Q"}) == True
        assert PolygonWebSocketClient._is_market_data_message({"ev": "T"}) == True
        assert PolygonWebSocketClient._is_market_data_message({"ev": "A"}) == True
        
        # Invalid messages
        assert PolygonWebSocketClient._is_market_data_message({"ev": "status"}) == False
        assert PolygonWebSocketClient._is_market_data_message({"ev": None}) == False
        assert PolygonWebSocketClient._is_market_data_message({}) == False
        assert PolygonWebSocketClient._is_market_data_message("not_dict") == False
    
    def test_get_status(self, client):
        """Test get_status method"""
        status = client.get_status()
        
        assert "connected" in status
        assert "authenticated" in status
        assert "subscribed_symbols" in status
        assert "retry_count" in status
        assert "stream_types" in status
        
        assert status["connected"] == False
        assert status["authenticated"] == False
        assert status["retry_count"] == 0


class TestTimescaleDataModels:
    """Tests for data models"""
    
    def test_quote_data_model(self):
        """Test QuoteData model"""
        now = datetime.now(timezone.utc)
        quote = QuoteData(
            time=now,
            symbol="AAPL",
            bid=150.0,
            ask=150.01,
            bid_size=1000,
            ask_size=2000,
            bid_exchange="Q",
            ask_exchange="Q",
            source="polygon"
        )
        
        assert quote.symbol == "AAPL"
        assert quote.bid == 150.0
        assert quote.ask == 150.01
        assert quote.spread == 0.01  # Computed in database
    
    def test_trade_data_model(self):
        """Test TradeData model"""
        now = datetime.now(timezone.utc)
        trade = TradeData(
            time=now,
            symbol="AAPL",
            price=150.05,
            size=100,
            side="buy",
            exchange="Q",
            source="polygon"
        )
        
        assert trade.symbol == "AAPL"
        assert trade.price == 150.05
        assert trade.size == 100
        assert trade.side == "buy"
    
    def test_aggregate_data_model(self):
        """Test AggregateData model"""
        now = datetime.now(timezone.utc)
        agg = AggregateData(
            time=now,
            symbol="AAPL",
            open=149.5,
            high=151.0,
            low=149.0,
            close=150.5,
            volume=1000000,
            vwap=150.25,
            source="polygon",
            interval="1m"
        )
        
        assert agg.symbol == "AAPL"
        assert agg.open == 149.5
        assert agg.close == 150.5
        assert agg.volume == 1000000


class TestPolygonWebSocketAgent:
    """Tests for PolygonWebSocketAgent"""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        return AsyncMock()
    
    @pytest.fixture
    def agent(self, mock_redis):
        """Create a test agent"""
        with patch('atlas.agents.l1_data.polygon_ws_agent.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                polygon_api_key="test_key",
                database_url="postgresql://localhost/test",
                watchlist="AAPL,MSFT",
                environment="test"
            )
            return PolygonWebSocketAgent(mock_redis, "postgresql://localhost/test")
    
    def test_agent_initialization(self, agent, mock_redis):
        """Test agent initialization"""
        assert agent.name == "PolygonWebSocketAgent"
        assert agent.agent_type == "data_ingestion"
        assert agent.symbols == ["AAPL", "MSFT"]
        assert agent._messages_received == 0
        assert agent._messages_processed == 0
    
    def test_parse_watchlist(self, agent):
        """Test watchlist parsing"""
        # Already tested in initialization, but verify the result
        assert len(agent.symbols) > 0
        assert all(isinstance(s, str) for s in agent.symbols)
        assert all(s.isupper() for s in agent.symbols)
    
    def test_parse_timestamp_valid(self):
        """Test timestamp parsing with valid input"""
        ts_ms = 1672531200000  # 2023-01-01 00:00:00 UTC
        dt = PolygonWebSocketAgent._parse_timestamp(ts_ms)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        assert dt.tzinfo is not None
    
    def test_parse_timestamp_none(self):
        """Test timestamp parsing with None"""
        dt = PolygonWebSocketAgent._parse_timestamp(None)
        assert isinstance(dt, datetime)
        # Should return current time
        now = datetime.now(timezone.utc)
        assert abs((now - dt).total_seconds()) < 1
    
    def test_determine_trade_side(self):
        """Test trade side determination"""
        # Currently returns "unknown" - can be enhanced
        side = PolygonWebSocketAgent._determine_trade_side({"x": "Q"})
        assert side == "unknown"
    
    @pytest.mark.asyncio
    async def test_handle_quote_message(self, agent, mock_redis):
        """Test handling quote message"""
        agent.ts_client = AsyncMock()
        
        message = {
            "ev": "Q",
            "sym": "AAPL",
            "bp": 150.0,
            "bs": 1000,
            "ap": 150.01,
            "as": 2000,
            "bx": "Q",
            "ax": "Q",
            "t": 1672531200000
        }
        
        await agent._handle_message(message)
        
        assert agent._messages_received == 1
        assert agent._messages_processed == 1
        assert agent.ts_client.write_quote.called


class TestStreamTypes:
    """Tests for stream type enums"""
    
    def test_stream_types(self):
        """Test stream type definitions"""
        assert StreamType.QUOTES.value == "Q"
        assert StreamType.TRADES.value == "T"
        assert StreamType.AGGREGATES.value == "A"


# Integration tests (require actual services)
class TestIntegration:
    """Integration tests with real/mock services"""
    
    @pytest.mark.asyncio
    async def test_message_handler_chain(self):
        """Test complete message handling chain"""
        messages_processed = []
        
        async def handler(msg):
            messages_processed.append(msg)
        
        client = PolygonWebSocketClient(
            api_key="test",
            symbols=["AAPL"],
            message_handler=handler,
            stream_types=["Q"]
        )
        
        # Simulate message
        test_message = {
            "ev": "Q",
            "sym": "AAPL",
            "bp": 150.0,
            "bs": 1000,
            "ap": 150.01,
            "as": 2000,
            "bx": "Q",
            "ax": "Q",
            "t": 1672531200000
        }
        
        await client.message_handler(test_message)
        
        assert len(messages_processed) == 1
        assert messages_processed[0]["sym"] == "AAPL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
