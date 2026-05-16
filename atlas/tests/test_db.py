import pytest
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch

from atlas.data.storage.timescale_client import (
    TimescaleClient,
    BarData,
    OrderbookData,
    FeatureData,
    AgentData,
    LogData,
)


@pytest.fixture
def mock_engine():
    with patch(
        "atlas.data.storage.timescale_client.create_async_engine"
    ) as mock_create:
        engine = MagicMock()

        # Setup context managers for begin() and connect()
        conn_mock = AsyncMock()
        engine.begin.return_value = AsyncMock()
        engine.begin.return_value.__aenter__.return_value = conn_mock
        engine.connect.return_value = AsyncMock()
        engine.connect.return_value.__aenter__.return_value = conn_mock

        mock_create.return_value = engine
        yield engine


@pytest.fixture
def client(mock_engine):
    return TimescaleClient("postgresql+asyncpg://user:pass@localhost/db")


@pytest.mark.asyncio
async def test_connect(client, mock_engine):
    conn_mock = AsyncMock()
    # Mock engine.begin() context manager
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    await client.connect()

    # First call is SELECT 1, remaining calls are auto-migration
    assert conn_mock.execute.call_count >= 1
    assert "SELECT 1" in str(conn_mock.execute.call_args_list[0][0][0])


@pytest.mark.asyncio
async def test_write_bars(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    bar_data = BarData(
        time=datetime.utcnow(),
        symbol="BTC/USD",
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.5,
        source="binance",
        interval="1m",
    )

    await client.write_bars("BTC/USD", bar_data)

    conn_mock.execute.assert_called_once()
    query = str(conn_mock.execute.call_args[0][0])
    assert "INSERT INTO market_data_l1" in query
    params = conn_mock.execute.call_args[0][1]
    assert params["symbol"] == "BTC/USD"
    assert params["open"] == 50000.0


@pytest.mark.asyncio
async def test_write_orderbook(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    ob_data = OrderbookData(
        time=datetime.utcnow(),
        symbol="ETH/USD",
        bids={"3000.0": 1.5},
        asks={"3001.0": 2.0},
        spread=1.0,
        mid_price=3000.5,
    )

    await client.write_orderbook("ETH/USD", ob_data)

    conn_mock.execute.assert_called_once()
    query = str(conn_mock.execute.call_args[0][0])
    assert "INSERT INTO market_data_l2" in query
    params = conn_mock.execute.call_args[0][1]
    assert params["symbol"] == "ETH/USD"
    assert isinstance(params["bids"], str)  # Should be JSON dumped


@pytest.mark.asyncio
async def test_write_features(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    features = {"rsi_14": 45.5, "macd": 0.05}

    await client.write_features("SOL/USD", features)

    assert conn_mock.execute.call_count == 2
    query = str(conn_mock.execute.call_args_list[0][0][0])
    assert "INSERT INTO features" in query
    params = conn_mock.execute.call_args_list[0][0][1]
    assert params["symbol"] == "SOL/USD"
    assert params["feature_name"] in features
    assert params["value"] == features[params["feature_name"]]


@pytest.mark.asyncio
async def test_get_bars(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    # Mock the result of execute
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        (
            datetime.utcnow(),
            "BTC/USD",
            50000.0,
            51000.0,
            49000.0,
            50500.0,
            100.5,
            "binance",
            "1m",
        )
    ]
    conn_mock.execute.return_value = result_mock

    start_time = datetime.utcnow() - timedelta(minutes=10)
    end_time = datetime.utcnow()

    df = await client.get_bars("BTC/USD", start_time, end_time, "1m")

    conn_mock.execute.assert_called_once()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert list(df.columns) == [
        "time",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        "interval",
    ]
    assert df.iloc[0]["symbol"] == "BTC/USD"


@pytest.mark.asyncio
async def test_get_bars_empty(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    # Mock empty result
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    conn_mock.execute.return_value = result_mock

    start_time = datetime.utcnow() - timedelta(minutes=10)
    end_time = datetime.utcnow()

    df = await client.get_bars("BTC/USD", start_time, end_time, "1m")

    conn_mock.execute.assert_called_once()
    assert isinstance(df, pd.DataFrame)
    assert df.empty


@pytest.mark.asyncio
async def test_write_agent(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    agent_data = AgentData(
        id="123e4567-e89b-12d3-a456-426614174000",
        name="test_agent",
        type="strategy",
        layer="l2",
        status="active",
        pid=1234,
        last_heartbeat=datetime.utcnow(),
        created_at=datetime.utcnow(),
        metadata={"version": "1.0.0"},
    )

    await client.write_agent(agent_data)

    conn_mock.execute.assert_called_once()
    query = str(conn_mock.execute.call_args[0][0])
    assert "INSERT INTO agent_registry" in query
    assert "ON CONFLICT (id) DO UPDATE" in query
    params = conn_mock.execute.call_args[0][1]
    assert params["id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert params["name"] == "test_agent"


@pytest.mark.asyncio
async def test_log(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    await client.log(
        agent_id="123e4567-e89b-12d3-a456-426614174000",
        level="INFO",
        message="System started",
        metadata={"module": "core"},
    )

    conn_mock.execute.assert_called_once()
    query = str(conn_mock.execute.call_args[0][0])
    assert "INSERT INTO system_logs" in query
    params = conn_mock.execute.call_args[0][1]
    assert params["agent_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert params["level"] == "INFO"
    assert params["message"] == "System started"
    assert isinstance(params["metadata"], str)


@pytest.mark.asyncio
async def test_get_latest_features(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        ("BTC/USD", "rsi_14", 45.0),
        ("BTC/USD", "macd", 0.05),
    ]
    conn_mock.execute.return_value = result_mock

    res = await client.get_latest_features(["BTC/USD"], limit=5)

    conn_mock.execute.assert_called_once()
    assert "BTC/USD" in res
    assert res["BTC/USD"]["rsi_14"] == 45.0
    assert res["BTC/USD"]["macd"] == 0.05


@pytest.mark.asyncio
async def test_get_recent_backtest_results(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        (
            "uuid1",
            datetime.utcnow(),
            datetime.utcnow(),
            1.5,
            0.2,
            0.1,
            0.6,
            100,
            True,
            "{}",
            datetime.utcnow(),
        )
    ]
    conn_mock.execute.return_value = result_mock

    res = await client.get_recent_backtest_results(limit=5)
    assert len(res) == 1
    assert res[0]["strategy_id"] == "uuid1"
    assert res[0]["sharpe"] == 1.5


@pytest.mark.asyncio
async def test_get_recent_strategy_names(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    result_mock = MagicMock()
    result_mock.fetchall.return_value = [("Strategy_alpha",), ("Strategy_beta",)]
    conn_mock.execute.return_value = result_mock

    res = await client.get_recent_strategy_names(limit=10)
    assert len(res) == 2
    assert "Strategy_alpha" in res


@pytest.mark.asyncio
async def test_save_strategy(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    spec = {"strategy_name": "TestStrat", "timeframe": "1h"}
    sid = await client.save_strategy(spec, "pending_code", "IdeatorAgent")

    conn_mock.execute.assert_called_once()
    assert isinstance(sid, str)


@pytest.mark.asyncio
async def test_update_strategy_code(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn_mock

    await client.update_strategy_code("uuid1", "print('hello')", "pending_backtest")

    conn_mock.execute.assert_called_once()
    params = conn_mock.execute.call_args[0][1]
    assert params["code"] == "print('hello')"
    assert params["status"] == "pending_backtest"


@pytest.mark.asyncio
async def test_get_strategies_by_status(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        (
            "uuid1",
            "TestStrat",
            "print('hello')",
            '{"param": 1}',
            "validated",
            datetime.utcnow(),
            "IdeatorAgent",
        )
    ]
    conn_mock.execute.return_value = result_mock

    res = await client.get_strategies_by_status("validated")
    assert len(res) == 1
    assert res[0]["status"] == "validated"


@pytest.mark.asyncio
async def test_get_top_strategies_by_sharpe(client, mock_engine):
    conn_mock = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn_mock

    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        (
            "uuid1",
            "TestStrat",
            "code",
            '{"p": 1}',
            "validated",
            datetime.utcnow(),
            "author",
            2.5,
        )
    ]
    conn_mock.execute.return_value = result_mock

    res = await client.get_top_strategies_by_sharpe(1.0, 3.0, 5)
    assert len(res) == 1
    assert res[0]["sharpe"] == 2.5
