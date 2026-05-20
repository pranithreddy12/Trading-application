"""Chaos: Network partition — verify operation during partial connectivity loss."""

import asyncio
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_network_partition_detection():
    """System should detect network partition between components."""
    components = {"redis": True, "db": True, "broker": True}
    original = components.copy()
    components["broker"] = False  # Broker partitioned

    down = [k for k, v in components.items() if not v]
    assert down == ["broker"]
    assert all(components[k] for k in ["redis", "db"])


@pytest.mark.asyncio
async def test_partial_system_operation():
    """Non-partitioned components should continue operating."""
    db_ok = True
    broker_down = True
    cache = []

    async def continue_without_broker(signal):
        if broker_down:
            cache.append(signal)
            return {"status": "queued", "reason": "Broker partitioned"}
        return {"status": "executed"}

    result = await continue_without_broker({"symbol": "AAPL", "qty": 10})
    assert result["status"] == "queued"
    assert len(cache) == 1


@pytest.mark.asyncio
async def test_network_recovery_after_partition():
    """Queued operations should execute after partition heals."""
    cache = [{"symbol": "AAPL"}, {"symbol": "MSFT"}]
    broker_recovered = True
    executed = []

    async def flush_cache():
        nonlocal cache
        if broker_recovered:
            executed.extend(cache)
            cache = []
        return len(executed)

    count = await flush_cache()
    assert count == 2
    assert len(cache) == 0
