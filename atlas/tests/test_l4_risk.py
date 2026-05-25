import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.core.messaging import Channel

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.hget.return_value = None
    
    pubsub = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    redis.pubsub.return_value = pubsub
    
    return redis

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_agent_metadata.return_value = {}
    db.update_agent_metadata_active = AsyncMock()
    db.get_open_paper_trades.return_value = []
    db.get_daily_pnl.return_value = 0.0
    db.get_weekly_pnl.return_value = 0.0
    db.log = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_kill_switch_persists_after_restart(mock_redis, mock_db):
    ks = KillSwitch(mock_redis, mock_db)

    # Set up async context manager for db_client.engine.begin() and connect()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    # Mock result row with _mapping for _load_portfolio_risk_state
    mock_row = MagicMock()
    mock_row._mapping = {"halted": True, "reason": "restored from DB", "activated_at": None, "released_at": None}
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_conn.execute.return_value = mock_result
    mock_engine = MagicMock()
    # __aenter__/__aexit__ must be AsyncMock so they can be awaited
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_db.engine = mock_engine

    with patch("atlas.agents.l4_risk.kill_switch.settings") as mock_settings, \
         patch("atlas.agents.l4_risk.kill_switch.aiohttp.ClientSession"):
        mock_settings.slack_webhook_url = "http://test"
        await ks.activate("test_reason")
        
        mock_redis.hset.assert_called_once()
        args, kwargs = mock_redis.hset.call_args
        assert kwargs["mapping"]["active"] == "1"
        assert kwargs["mapping"]["reason"] == "test_reason"
        
        mock_db.update_agent_metadata_active.assert_called_once_with(ks.name, True)

@pytest.mark.asyncio
async def test_kill_switch_restores_state_on_startup(mock_redis, mock_db):
    # Set up async context manager for db_client.engine.connect()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    # Mock result row with _mapping for _load_portfolio_risk_state
    mock_row = MagicMock()
    mock_row._mapping = {"halted": True, "reason": "restored from DB", "activated_at": None, "released_at": None}
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_conn.execute.return_value = mock_result
    mock_engine = MagicMock()
    # __aenter__/__aexit__ must be AsyncMock so they can be awaited
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_db.engine = mock_engine
    
    mock_redis.hget.side_effect = lambda key, field: b"1" if field == "active" else None
    mock_db.get_agent_metadata.return_value = {"active": True}
    
    ks = KillSwitch(mock_redis, mock_db)
    # mock _heartbeat_loop and _run_with_retry to avoid running actual tasks
    with patch.object(ks, '_heartbeat_loop', return_value=None), \
         patch.object(ks, '_run_with_retry', return_value=None):
        await ks.start()
        
        assert ks._is_active is True
        assert ks._reason == "restored from DB"

@pytest.mark.asyncio
async def test_daily_loss_triggers_kill_switch(mock_redis, mock_db):
    rc = RiskController(mock_redis, mock_db)
    rc.RUN_INTERVAL = 0.01
    rc.status = "running"
    
    mock_db.get_daily_pnl.return_value = -3000.0  # -3% of 100,000
    
    with patch.object(rc, '_trigger_kill_switch', new_callable=AsyncMock) as mock_trigger:
        task = asyncio.create_task(rc.run())
        await asyncio.sleep(0.05)
        rc.status = "stopped"
        await task
        
        mock_trigger.assert_called()

@pytest.mark.asyncio
async def test_weekly_loss_triggers_kill_switch(mock_redis, mock_db):
    rc = RiskController(mock_redis, mock_db)
    rc.RUN_INTERVAL = 0.01
    rc.status = "running"
    
    mock_db.get_weekly_pnl.return_value = -5000.0  # -5% of 100,000
    
    with patch.object(rc, '_trigger_kill_switch', new_callable=AsyncMock) as mock_trigger:
        task = asyncio.create_task(rc.run())
        await asyncio.sleep(0.05)
        rc.status = "stopped"
        await task
        
        mock_trigger.assert_called()

@pytest.mark.asyncio
async def test_risk_controller_rejects_oversized_trade(mock_redis, mock_db):
    rc = RiskController(mock_redis, mock_db)
    
    # max_single_position_pct is 0.10 (10,000 out of 100,000)
    oversized_trade = {"size": 200, "price": 100}  # value = 20,000
    
    result = await rc.approve_trade(oversized_trade)
    assert result is False

@pytest.mark.asyncio
async def test_approve_trade_respects_cash_reserve(mock_redis, mock_db):
    rc = RiskController(mock_redis, mock_db)
    
    # 8 open trades worth 10,000 each = 80,000 open. 
    # Cash reserve left = 20,000 (20%)
    mock_db.get_open_paper_trades.return_value = [
        {"quantity": 100, "price": 100} for _ in range(8)
    ]
    
    # Any new trade will drop cash reserve below 20%
    new_trade = {"size": 10, "price": 100}  # value = 1,000
    
    result = await rc.approve_trade(new_trade)
    assert result is False
