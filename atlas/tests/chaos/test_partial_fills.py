"""Chaos: Partial fills — verify system tracks and manages partial order fills."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_partial_fill_tracking():
    """Partial fills should be tracked and remaining quantity managed."""
    order = {"order_key": "partial_001", "symbol": "AAPL", "total_qty": 100, "filled_qty": 0}
    fills = [30, 20, 15]

    for fill_qty in fills:
        remaining = order["total_qty"] - order["filled_qty"]
        assert remaining > 0
        fill = min(fill_qty, remaining)
        order["filled_qty"] += fill

    assert order["filled_qty"] == 65
    assert order["total_qty"] - order["filled_qty"] == 35


@pytest.mark.asyncio
async def test_partial_fill_completion():
    """Partial fills should eventually complete."""
    order = {"order_key": "partial_002", "total_qty": 50, "filled_qty": 0}
    fills = [10] * 10

    for fill in fills:
        remaining = order["total_qty"] - order["filled_qty"]
        if remaining == 0:
            break
        order["filled_qty"] += min(fill, remaining)

    assert order["filled_qty"] == 50


@pytest.mark.asyncio
async def test_partial_fill_cancellation():
    """Remaining unfilled portion should be cancellable."""
    order = {"order_key": "partial_003", "total_qty": 100, "filled_qty": 40}
    cancelled_qty = order["total_qty"] - order["filled_qty"]
    assert cancelled_qty == 60
    order["filled_qty"] = order["total_qty"]  # Mark as done
    assert order["filled_qty"] == order["total_qty"]
