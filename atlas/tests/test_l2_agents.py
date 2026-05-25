import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from atlas.agents.l2_strategy.ideator_agent import IdeatorAgent
from atlas.agents.l2_strategy.coder_agent import CoderAgent
from atlas.agents.l2_strategy.combiner_agent import CombinerAgent


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    return redis


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_latest_features.return_value = {"BTC/USD": {"rsi": 50}}
    db.get_recent_backtest_results.return_value = []
    db.get_recent_strategy_names.return_value = []
    db.save_strategy.return_value = "mock_uuid"
    db.update_strategy_code = AsyncMock()
    db.get_strategies_by_status.return_value = [
        {"id": "mock_uuid", "name": "test_strat", "parameters": {}}
    ]
    db.get_top_strategies_by_sharpe.return_value = [
        {"id": "uuid1", "name": "strat1", "sharpe": 1.5, "parameters": {}},
        {"id": "uuid2", "name": "strat2", "sharpe": 1.6, "parameters": {}},
    ]
    return db


@pytest.fixture
def valid_strategy_json():
    return """
    {
      "strategy_name": "test_strat",
      "hypothesis": "test",
      "entry_conditions": ["rsi_14 < 30", "relative_volume > 1.5"],
      "exit_conditions": ["rsi_14 > 70"],
      "stop_loss": "1%",
      "take_profit": "2%",
      "position_sizing": "1%",
      "timeframe": "1h",
      "asset_class": "crypto",
      "expected_sharpe": 1.5,
      "expected_win_rate": 0.55,
      "risk_level": "low",
      "tags": []
    }
    """


@pytest.mark.asyncio
async def test_ideator_parses_valid_claude_json(
    mock_redis, mock_db, valid_strategy_json
):
    agent = IdeatorAgent(1, 0.7, mock_redis, mock_db)

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=valid_strategy_json)]
    agent.client.messages.create = AsyncMock(return_value=mock_message)

    with patch("atlas.agents.l2_strategy.ideator_agent.MessagingClient") as MockMsg:
        mock_msg_instance = MockMsg.return_value
        mock_msg_instance.publish = AsyncMock()

        context = {
            "asset_class": "crypto",
            "archetype": "momentum",
            "market_snapshot": {"rsi": 50},
            "regime": "neutral",
            "failed_patterns": [],
            "successful_patterns": [],
            "recent_names": [],
            "bars_available": {},
            "primary_symbol": "BTC/USD",
        }
        spec, prompt, raw = await agent._generate_strategy(context)

        assert spec["strategy_name"] == "test_strat"


@pytest.mark.asyncio
async def test_ideator_handles_malformed_json_with_retry(mock_redis, mock_db):
    agent = IdeatorAgent(1, 0.7, mock_redis, mock_db)

    mock_message_invalid = MagicMock()
    mock_message_invalid.content = [MagicMock(text="not json")]

    agent.client.messages.create = AsyncMock(return_value=mock_message_invalid)

    context = {
        "asset_class": "crypto",
        "archetype": "momentum",
        "market_snapshot": {"rsi": 50},
        "regime": "neutral",
        "failed_patterns": [],
        "successful_patterns": [],
        "recent_names": [],
        "bars_available": {},
        "primary_symbol": "BTC/USD",
    }
    with patch("atlas.agents.l2_strategy.ideator_agent.MessagingClient"):
        spec, prompt, raw = await agent._generate_strategy(context)

        assert agent.client.messages.create.call_count == 3
        assert spec["strategy_name"] is not None


@pytest.mark.asyncio
async def test_ideator_gives_up_after_3_failures(mock_redis, mock_db):
    agent = IdeatorAgent(1, 0.7, mock_redis, mock_db)

    mock_message_invalid = MagicMock()
    mock_message_invalid.content = [MagicMock(text="not json")]

    agent.client.messages.create = AsyncMock(return_value=mock_message_invalid)

    context = {
        "asset_class": "crypto",
        "archetype": "momentum",
        "market_snapshot": {"rsi": 50},
        "regime": "neutral",
        "failed_patterns": [],
        "successful_patterns": [],
        "recent_names": [],
        "bars_available": {},
        "primary_symbol": "BTC/USD",
    }
    spec, prompt, raw = await agent._generate_strategy(context)

    assert agent.client.messages.create.call_count == 3
    assert spec["strategy_name"] is not None


@pytest.mark.asyncio
async def test_coder_saves_valid_code_to_db(mock_redis, mock_db):
    agent = CoderAgent(mock_redis, mock_db)

    strategy_record = {
        "id": "mock_uuid",
        "name": "test_strat",
        "code": "",
        "parameters": {
            "entry_conditions": ["rsi_14 < 30"],
            "exit_conditions": ["rsi_14 > 70"],
            "strategy_name": "test_strat",
        },
    }
    with patch("atlas.agents.l2_strategy.coder_agent.MessagingClient") as MockMsg:
        mock_msg_instance = MockMsg.return_value
        mock_msg_instance.publish = AsyncMock()
        await agent._code_strategy(strategy_record)

        mock_db.update_strategy_code.assert_called_once()
        assert mock_db.update_strategy_code.call_args[0][0] == "mock_uuid"


@pytest.mark.asyncio
async def test_coder_saves_code_from_normalized_conditions(mock_redis, mock_db):
    agent = CoderAgent(mock_redis, mock_db)

    strategy_record = {
        "id": "mock_uuid",
        "name": "test_strat",
        "code": "",
        "parameters": {
            "entry_conditions": ["rsi_14 < 30"],
            "exit_conditions": ["rsi_14 > 70"],
            "strategy_name": "test_strat",
        },
    }
    with patch("atlas.agents.l2_strategy.coder_agent.MessagingClient") as MockMsg:
        mock_msg_instance = MockMsg.return_value
        mock_msg_instance.publish = AsyncMock()
        await agent._code_strategy(strategy_record)

        assert mock_db.update_strategy_code.call_args[0][0] == "mock_uuid"


@pytest.mark.asyncio
async def test_combiner_skips_when_fewer_than_2_strategies(mock_redis, mock_db):
    mock_db.get_top_strategies_by_sharpe.return_value = [
        {"id": "uuid1", "name": "strat1", "sharpe": 1.5, "parameters": {}}
    ]
    agent = CombinerAgent(mock_redis, mock_db)

    with patch("atlas.agents.l2_strategy.combiner_agent._claude") as mock_claude:
        mock_claude.complete = AsyncMock()
        await agent._combine_top_strategies()

        mock_claude.complete.assert_not_called()
