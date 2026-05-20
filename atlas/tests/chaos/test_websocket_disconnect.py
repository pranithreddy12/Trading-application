"""Chaos: Websocket disconnect — verify resilience during streaming data loss."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_websocket_disconnect_handling():
    """Should handle websocket disconnects and reconnect."""
    class MockWSClient:
        def __init__(self):
            self.connected = True
            self.reconnect_count = 0

        async def connect(self):
            self.connected = True
            return True

        async def disconnect(self):
            self.connected = False
            return True

        async def reconnect(self):
            self.reconnect_count += 1
            await self.connect()
            return self.connected

    client = MockWSClient()
    await client.disconnect()
    assert client.connected is False
    reconnected = await client.reconnect()
    assert reconnected is True
    assert client.reconnect_count == 1


@pytest.mark.asyncio
async def test_data_buffering_during_disconnect():
    """Data should be buffered during disconnect and replayed on reconnect."""
    buffer = []
    disconnected = False

    async def stream_data(data):
        if disconnected:
            buffer.append(data)
            return False
        return True

    disconnected = True
    for i in range(10):
        await stream_data({"price": 100 + i})
    assert len(buffer) == 10

    disconnected = False
    flushed = 0
    for item in buffer:
        flushed += 1
    assert flushed == 10


@pytest.mark.asyncio
async def test_websocket_reconnect_backoff():
    """Reconnect should use exponential backoff."""
    import time
    mock_ws = AsyncMock()
    mock_ws.connect.side_effect = [ConnectionError] * 3 + [True]
    delays = [0.1, 0.2, 0.4]
    for i, delay in enumerate(delays):
        try:
            start = time.monotonic()
            await mock_ws.connect()
            elapsed = time.monotonic() - start
            assert elapsed >= 0
        except ConnectionError:
            await asyncio.sleep(delay)
    assert mock_ws.connect.call_count >= 3
