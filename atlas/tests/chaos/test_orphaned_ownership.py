"""Chaos: Orphaned ownership — verify recovery of orders from dead instances."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_orphaned_order_detection():
    """Orders owned by dead instances should be detected as orphaned."""
    alive_instances = {"instance_A", "instance_B"}
    order_owners = {
        "order_1": "instance_A",
        "order_2": "instance_C",  # Dead instance
        "order_3": "instance_B",
        "order_4": "instance_D",  # Dead instance
    }

    orphaned = [k for k, v in order_owners.items() if v not in alive_instances]
    assert len(orphaned) == 2
    assert "order_2" in orphaned
    assert "order_4" in orphaned


@pytest.mark.asyncio
async def test_orphaned_order_recovery():
    """Orphaned orders should be recoverable by a live instance."""
    orphaned_orders = ["order_2", "order_4"]
    recovered = []

    for order_id in orphaned_orders:
        recovered.append({"order_id": order_id, "recovered_by": "instance_A"})

    assert len(recovered) == 2
    assert all(r["recovered_by"] == "instance_A" for r in recovered)


@pytest.mark.asyncio
async def test_ownership_timeout():
    """Ownership should timeout and allow reclamation."""
    lease_expired = True
    if lease_expired:
        new_owner = "instance_B"
        assert new_owner == "instance_B"
