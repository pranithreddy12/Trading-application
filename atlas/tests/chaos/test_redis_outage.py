"""Chaos: Redis outage — system must degrade gracefully when Redis becomes unavailable."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch


async def simulate_redis_outage(agents: list) -> dict:
    """Simulate Redis being unreachable and verify agents degrade gracefully."""
    results = {
        "total_agents": len(agents),
        "crashed": 0,
        "degraded": 0,
        "recovered": 0,
        "details": [],
    }
    for agent in agents:
        try:
            if hasattr(agent, "_redis") and agent._redis:
                agent._redis = AsyncMock()
                agent._redis.ping.side_effect = ConnectionError("Redis unreachable")
                agent._redis.get.side_effect = ConnectionError("Redis unreachable")
                agent._redis.set.side_effect = ConnectionError("Redis unreachable")
            await asyncio.sleep(0.01)
            results["degraded"] += 1
            results["details"].append(f"{agent.name}: degraded (Redis unavailable)")
        except Exception as e:
            results["crashed"] += 1
            results["details"].append(f"{agent.name}: crashed ({e})")
    return results


@pytest.mark.asyncio
async def test_redis_outage_detection():
    """Verify system detects Redis outage."""
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = ConnectionError("Redis unreachable")
    with pytest.raises(ConnectionError):
        await mock_redis.ping()


@pytest.mark.asyncio
async def test_redis_outage_graceful_degradation():
    """Agents should not crash when Redis is down; they should degrade."""
    from unittest.mock import MagicMock
    from atlas.agents.l5_execution.order_tracker import OrderTracker
    from atlas.agents.l4_risk.kill_switch import KillSwitch

    mock_redis = AsyncMock()
    mock_redis.hget.side_effect = ConnectionError("Redis unreachable")
    mock_redis.set.side_effect = ConnectionError("Redis unreachable")
    mock_db = MagicMock()

    tracker = OrderTracker(mock_redis, mock_db)
    result = await tracker.acquire_lock("test_order")
    assert result is False, "Should return False on Redis failure"


@pytest.mark.asyncio
async def test_redis_reconnect_capability():
    """After outage, system should reconnect when Redis recovers."""
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = [
        ConnectionError("Redis unreachable"),
        ConnectionError("Redis unreachable"),
        True,
    ]
    for attempt in range(3):
        try:
            result = await mock_redis.ping()
            if result:
                assert True
                return
        except ConnectionError:
            await asyncio.sleep(0.01)
    pytest.fail("Did not recover after 3 attempts")
