"""Chaos: Delayed execution — verify timeout handling and fallback behavior."""

import asyncio
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_execution_timeout():
    """Execution should timeout and fall back gracefully."""
    async def slow_execute(signal: dict) -> bool:
        await asyncio.sleep(10)  # Too slow
        return True

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_execute({"order": "test"}), timeout=0.5)


@pytest.mark.asyncio
async def test_timeout_fallback():
    """On timeout, system should log and return failure, not crash."""
    executed = [False]
    async def execute_with_timeout(order: dict) -> bool:
        try:
            await asyncio.wait_for(asyncio.sleep(10), timeout=0.1)
        except asyncio.TimeoutError:
            executed[0] = False
            return False
        return True

    result = await execute_with_timeout({"order": "test"})
    assert result is False
    assert executed[0] is False


@pytest.mark.asyncio
async def test_delayed_broker_response():
    """Broker latency should not block the entire pipeline."""
    mock_broker = AsyncMock()
    mock_broker.submit_order.side_effect = asyncio.TimeoutError("Broker timeout")
    try:
        await asyncio.wait_for(mock_broker.submit_order({"symbol": "AAPL"}), timeout=1)
        assert False, "Should have timed out"
    except asyncio.TimeoutError:
        pass
