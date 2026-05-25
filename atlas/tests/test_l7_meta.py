import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from atlas.agents.l7_meta.self_improvement_agent import SelfImprovementAgent
from atlas.agents.l7_meta.intelligence_brief_agent import IntelligenceBriefAgent


def _make_performance_row(**overrides):
    """Helper to build a performance data row for the self_improvement test."""
    row = {
        "id": "mock-uuid",
        "strategy_name": "test_strat",
        "tags": ["momentum"],
        "timeframe": "1m",
        "asset_class": "equity",
        "market_regime": "bullish",
        "score": 80.0,
        "win_rate": 0.6,
        "net_profit": 100.0,
        "sharpe_ratio": 1.5,
        "profit_factor": 2.0,
        "total_trades": 50,
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    return redis


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.log = AsyncMock()
    db._execute_insert = AsyncMock()
    return db


@pytest.fixture
def mock_claude():
    claude = AsyncMock()
    claude.complete = AsyncMock(return_value=(
        "## Market Regime\nbull_volatile\n"
        "## Portfolio Summary\n$15000.50\n"
        "## Top Strategies\nStratA\n"
        "## Risk Alerts\nNone\n"
        "## Recommended Focus Today\nmomentum"
    ))
    return claude


@pytest.mark.asyncio
async def test_self_improvement_publishes_insights_event(mock_redis, mock_db):
    mock_db.fetch = AsyncMock(return_value=[_make_performance_row() for _ in range(5)])
    agent = SelfImprovementAgent(redis_client=mock_redis, db_client=mock_db)

    await agent._analyze_and_feedback()

    # Check if redis publish was called with strategy_signals
    mock_redis.publish.assert_called_once()
    args, kwargs = mock_redis.publish.call_args
    assert args[0] == "strategy_signals"

    signal = json.loads(args[1])
    assert signal["type"] == "improvement_insights"
    assert "recommended_focus" in signal


@pytest.mark.asyncio
async def test_self_improvement_identifies_winning_patterns(mock_redis, mock_db):
    mock_db.fetch = AsyncMock(return_value=[_make_performance_row() for _ in range(5)])
    agent = SelfImprovementAgent(redis_client=mock_redis, db_client=mock_db)

    await agent._analyze_and_feedback()

    # Check if redis publish was called with strategy_signals
    args, kwargs = mock_redis.publish.call_args
    signal = json.loads(args[1])

    assert "winning_patterns" in signal
    assert isinstance(signal["winning_patterns"], list)
    assert len(signal["winning_patterns"]) > 0
    assert "losing_patterns" in signal


@pytest.mark.asyncio
async def test_intelligence_brief_calls_claude_and_saves(mock_redis, mock_db, mock_claude):
    with patch("atlas.agents.l7_meta.intelligence_brief_agent._claude", mock_claude):
        agent = IntelligenceBriefAgent(
            redis_client=mock_redis, db_client=mock_db, claude_client=mock_claude
        )

        await agent._generate_brief()

        # Check if claude API was called (via module-level _claude)
        mock_claude.complete.assert_called_once()

        # Check if it saves to DB
        mock_db._execute_insert.assert_called_once()
        query_args, query_kwargs = mock_db._execute_insert.call_args
        query = query_args[0]
        assert "INSERT INTO intelligence_briefs" in query

        params = query_args[1]
        assert "brief_text" in params


@pytest.mark.asyncio
async def test_intelligence_brief_contains_required_sections(mock_redis, mock_db, mock_claude):
    with patch("atlas.agents.l7_meta.intelligence_brief_agent._claude", mock_claude):
        agent = IntelligenceBriefAgent(
            redis_client=mock_redis, db_client=mock_db, claude_client=mock_claude
        )

        brief_text = await agent._generate_brief()

        # Verify the text returned by claude (or our mock) has required sections
        assert "## Market Regime" in brief_text
        assert "## Portfolio Summary" in brief_text
        assert "## Top Strategies" in brief_text
        assert "## Risk Alerts" in brief_text
        assert "## Recommended Focus Today" in brief_text
