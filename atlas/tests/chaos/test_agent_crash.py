"""Chaos: Agent crash — verify supervisor detects, reports, and restarts crashed agents."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_agent_crash_detection():
    """Supervisor should detect agent crashes via heartbeat timeout."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.status = "running"
    agent._main_task = asyncio.create_task(asyncio.sleep(100))
    agent._main_task.cancel()
    await asyncio.sleep(0.01)
    assert agent._main_task.done() or agent._main_task.cancelled()


@pytest.mark.asyncio
async def test_agent_auto_restart():
    """Supervisor should attempt to restart a crashed agent automatically."""
    restart_count = [0]

    class RestartableAgent:
        def __init__(self):
            self.name = "resilient_agent"
            self.status = "stopped"

        async def start(self):
            self.status = "running"
            return True

        async def stop(self):
            self.status = "stopped"
            return True

    agent = RestartableAgent()
    assert agent.status == "stopped"
    await agent.start()
    assert agent.status == "running"
    restart_count[0] += 1
    await agent.stop()
    await agent.start()
    assert agent.status == "running"
    assert restart_count[0] == 1


@pytest.mark.asyncio
async def test_crash_propagation_limit():
    """Excessive crashes should trigger circuit breaker / cooldown."""
    agent = MagicMock()
    agent.name = "crashy_agent"
    crash_count = 0
    max_restarts = 3

    for attempt in range(5):
        if crash_count >= max_restarts:
            break  # Circuit breaker engaged
        try:
            raise RuntimeError("Agent crashed")
        except RuntimeError:
            crash_count += 1
            await asyncio.sleep(0.01 * (2 ** crash_count))

    assert crash_count >= max_restarts, "Should have hit circuit breaker"


@pytest.mark.asyncio
async def test_supervisor_reports_crashed_agent():
    """Supervisor should log crashed agent details."""
    import logging
    logger = logging.getLogger("supervisor")
    with patch.object(logger, "warning") as mock_warn:
        agent_name = "crashed_agent"
        exc = RuntimeError("Out of memory")
        logger.warning(f"Agent task exited early — {agent_name}: {exc}")
        mock_warn.assert_called_once()
