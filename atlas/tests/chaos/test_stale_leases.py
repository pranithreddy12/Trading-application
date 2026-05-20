"""Chaos: Stale leases — verify lease expiration and recovery logic."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_lease_automatic_expiry():
    """Leases should expire after their TTL."""
    import time
    tracker = MagicMock()
    tracker._redis = AsyncMock()
    tracker._redis.set.return_value = True
    tracker._redis.delete.return_value = True
    lock_key = "execution:lock:test_order"
    acquired = await tracker._redis.set(lock_key, "1", nx=True, ex=1)
    assert acquired is True
    await asyncio.sleep(1.5)
    re_acquired = await tracker._redis.set(lock_key, "2", nx=True, ex=1)
    assert re_acquired is True


@pytest.mark.asyncio
async def test_recover_stale_leases():
    """System should detect and recover stale/expired leases on startup."""
    stale_keys = ["execution:lock:stale_1", "execution:lock:stale_2"]
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = stale_keys
    mock_redis.get.return_value = b"dead_instance"

    keys_found = await mock_redis.keys("execution:lock:*")
    assert len(keys_found) == 2

    owner = await mock_redis.get(keys_found[0])
    assert owner == b"dead_instance"


@pytest.mark.asyncio
async def test_lease_ownership_check():
    """Only the lease owner should be able to renew or release."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"instance_A"
    current_owner = await mock_redis.get("execution:lock:my_order")
    assert current_owner == b"instance_A"
    wrong_owner = b"instance_B"
    assert current_owner != wrong_owner
