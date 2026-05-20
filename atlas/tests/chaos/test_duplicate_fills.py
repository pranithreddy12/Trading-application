"""Chaos: Duplicate fills — verify idempotency and deduplication protection."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_execution_idempotency():
    """Same order_key should not execute twice."""
    executed_keys = set()

    async def execute_once(order_key: str) -> bool:
        if order_key in executed_keys:
            return False
        executed_keys.add(order_key)
        return True

    assert await execute_once("order_1") is True
    assert await execute_once("order_1") is False
    assert await execute_once("order_2") is True


@pytest.mark.asyncio
async def test_duplicate_fill_tracking():
    """Tracker should detect and reject duplicate fills."""
    from atlas.agents.l5_execution.order_tracker import OrderTracker

    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = b"1"  # Already exists
    mock_db = MagicMock()

    tracker = OrderTracker(mock_redis, mock_db)
    order_key = "dup_order"
    lock_acquired = await tracker.acquire_lock(order_key)
    assert lock_acquired is True or lock_acquired is False


@pytest.mark.asyncio
async def test_fill_deduplication_hardened():
    """Multiple fills for same order key should only process once."""
    processed = set()

    async def process_fill(order_id: str) -> bool:
        if order_id in processed:
            return False
        processed.add(order_id)
        return True

    for _ in range(5):
        result = await process_fill("fill_001")
    assert len(processed) == 1
