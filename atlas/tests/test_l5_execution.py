import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from atlas.agents.l5_execution.alpaca_executor import AlpacaExecutor
from atlas.agents.l5_execution.binance_executor import BinanceExecutor
from atlas.agents.l4_risk.kill_switch import KillSwitch

@pytest.fixture
def redis_client():
    mock = AsyncMock()
    mock.pubsub.return_value = AsyncMock()
    return mock

@pytest.fixture
def db_client():
    mock = MagicMock()
    mock._execute_insert = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_alpaca_aborts_if_kill_switch_active(redis_client, db_client):
    executor = AlpacaExecutor(redis_client, db_client)
    
    # We call _process_signal directly
    signal_data = {"strategy_id": "s1", "type": "validated", "symbol": "AAPL", "qty": 10, "side": "buy"}
    
    with patch("atlas.agents.l4_risk.kill_switch.KillSwitch.is_active", new_callable=AsyncMock) as mock_is_active:
        mock_is_active.return_value = True
        with patch("aiohttp.ClientSession.post") as mock_post:
            await executor._process_signal(signal_data)
            mock_post.assert_not_called() # Should abort

@pytest.mark.asyncio
async def test_alpaca_aborts_if_risk_rejected(redis_client, db_client):
    executor = AlpacaExecutor(redis_client, db_client)
    
    # Symbol "REJECT_ME" is rejected by our stub RiskController
    signal_data = {"strategy_id": "s1", "type": "validated", "symbol": "REJECT_ME", "qty": 10, "side": "buy"}
    
    with patch.object(executor.risk_controller, "approve_trade", new_callable=AsyncMock) as mock_approve:
        mock_approve.return_value = False
        with patch("aiohttp.ClientSession.post") as mock_post:
            await executor._process_signal(signal_data)
            mock_post.assert_not_called()

@pytest.mark.asyncio
async def test_alpaca_cancels_all_on_kill_switch_event(redis_client, db_client):
    executor = AlpacaExecutor(redis_client, db_client)
    
    with patch("aiohttp.ClientSession.delete") as mock_delete:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_delete.return_value.__aenter__.return_value = mock_resp
        
        await executor._cancel_all_orders()
        mock_delete.assert_called_once()
        assert mock_delete.call_args[0][0].endswith("/v2/orders")

@pytest.mark.asyncio
async def test_fill_written_to_paper_trades_table(redis_client, db_client):
    executor = AlpacaExecutor(redis_client, db_client)
    signal_data = {"strategy_id": "s1", "type": "validated", "symbol": "AAPL", "qty": 10, "side": "buy"}
    
    with patch.object(executor.risk_controller, "approve_trade", new_callable=AsyncMock) as mock_approve, \
         patch("aiohttp.ClientSession.post") as mock_post, \
         patch("aiohttp.ClientSession.get") as mock_get:
        
        mock_approve.return_value = True
        
        mock_post_resp = AsyncMock()
        mock_post_resp.status = 200
        mock_post_resp.json.return_value = {"id": "order-123"}
        mock_post.return_value.__aenter__.return_value = mock_post_resp
        
        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json.return_value = {"status": "filled", "filled_avg_price": "150.5"}
        mock_get.return_value.__aenter__.return_value = mock_get_resp
        
        await executor._process_signal(signal_data)
        
        db_client._execute_insert.assert_called_once()
        query_args = db_client._execute_insert.call_args[0]
        assert "paper_trades" in query_args[0]
        params = query_args[1]
        assert params["sym"] == "AAPL"
        assert params["price"] == 150.5

@pytest.mark.asyncio
async def test_binance_quantity_precision_rounding(redis_client, db_client):
    executor = BinanceExecutor(redis_client, db_client)
    
    # 1.1234567 should be rounded to 1.123457 or 1.123456
    signal_data = {"strategy_id": "s1", "type": "validated", "symbol": "BTCUSDT", "qty": 1.1234567, "side": "buy", "price": 100000.0}
    
    with patch.object(executor.risk_controller, "approve_trade", new_callable=AsyncMock) as mock_approve, \
         patch("aiohttp.ClientSession.post") as mock_post:
        
        mock_approve.return_value = True
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {"orderId": "b-123", "status": "FILLED", "fills": [{"price": "100000", "qty": "1.123457"}], "executedQty": "1.123457"}
        mock_post.return_value.__aenter__.return_value = mock_resp
        
        await executor._process_signal(signal_data)
        
        db_client._execute_insert.assert_called_once()
        params = db_client._execute_insert.call_args[0][1]
        assert params["qty"] == 1.123457 # Expected to be rounded to 6 decimal places
