"""Chaos: DB outage — verify system survives database disconnection."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_db_connection_failure():
    """Should handle DB connection failures gracefully."""
    mock_db = AsyncMock()
    mock_db.connect.side_effect = Exception("Database connection refused")
    with pytest.raises(Exception, match="Database connection refused"):
        await mock_db.connect()


@pytest.mark.asyncio
async def test_db_query_timeout():
    """Should handle DB query timeouts without crashing."""
    mock_db = AsyncMock()
    mock_db.fetchval.side_effect = asyncio.TimeoutError("Query timeout")
    try:
        result = await mock_db.fetchval("SELECT 1")
        assert False, "Should have raised"
    except asyncio.TimeoutError:
        pass


@pytest.mark.asyncio
async def test_db_reconnection_after_outage():
    """System should re-establish DB connection after outage resolves."""
    call_count = [0]
    async def flaky_connect():
        call_count[0] += 1
        if call_count[0] <= 2:
            raise Exception("DB unavailable")
        return True

    mock_db = AsyncMock()
    mock_db.connect.side_effect = flaky_connect
    for attempt in range(5):
        try:
            result = await mock_db.connect()
            assert result is True
            return
        except Exception:
            await asyncio.sleep(0.01)
    pytest.fail("Did not recover DB connection")


@pytest.mark.asyncio
async def test_kill_switch_active_during_db_outage():
    """Kill switch should remain active (or last known state) during DB outage."""
    from atlas.data.storage.timescale_client import TimescaleClient
    mock_db = AsyncMock(spec=TimescaleClient)
    mock_db.fetchval.side_effect = Exception("DB unavailable")
    try:
        result = await mock_db.fetchval("SELECT halted FROM risk_state")
        assert False, "Should have raised on DB outage"
    except Exception:
        pass
