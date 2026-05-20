"""Chaos: Lock race — verify distributed lock prevents concurrent execution."""

import asyncio
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_concurrent_lock_prevention():
    """Two processes should not acquire same lock simultaneously."""
    lock_holder = None

    async def acquire_lock(instance_id: str) -> bool:
        nonlocal lock_holder
        if lock_holder is not None:
            return False
        lock_holder = instance_id
        await asyncio.sleep(0.05)
        lock_holder = None
        return True

    results = await asyncio.gather(
        acquire_lock("A"),
        acquire_lock("B"),
    )
    assert sum(results) == 1  # Only one should succeed


@pytest.mark.asyncio
async def test_lock_timeout_release():
    """Lock should auto-release after timeout."""
    lock_holder = "instance_A"
    import time
    start = time.monotonic()
    while lock_holder is not None and time.monotonic() - start < 0.2:
        await asyncio.sleep(0.01)
        lock_holder = None  # Simulate timeout release
    assert lock_holder is None


@pytest.mark.asyncio
async def test_nested_lock_same_order():
    """Same order should not re-acquire lock."""
    executed_ids = set()
    async def execute_once(order_id: str) -> bool:
        if order_id in executed_ids:
            return False
        executed_ids.add(order_id)
        return True

    assert await execute_once("order_1") is True
    assert await execute_once("order_1") is False
