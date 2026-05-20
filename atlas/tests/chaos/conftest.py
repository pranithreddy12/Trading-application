"""
conftest.py — Chaos Test Fixtures (Phase 13.4)

Reusable fixtures for chaos engineering tests.
Provides: Redis mock/outage, DB mock/outage, simulated failures, and recovery helpers.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

import pytest
import pytest_asyncio

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

class MockRedisFailover:
    """Simulates Redis with controlled failure modes for chaos testing."""

    def __init__(self):
        self._data: dict = {}
        self._pubsub_channels: dict = {}
        self._is_available = True
        self._fail_after_ops: Optional[int] = None
        self._op_count = 0
        self._latency_ms: float = 0.0
        self._error_rate: float = 0.0

    def set_fail_after(self, ops: int):
        self._fail_after_ops = ops

    def set_error_rate(self, rate: float):
        self._error_rate = min(1.0, max(0.0, rate))

    def set_latency(self, ms: float):
        self._latency_ms = ms

    def set_availability(self, available: bool):
        self._is_available = available

    async def _check(self):
        self._op_count += 1
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)
        if self._fail_after_ops and self._op_count >= self._fail_after_ops:
            self._is_available = False
        if not self._is_available:
            raise ConnectionError("MockRedis: connection refused")
        if random.random() < self._error_rate:
            raise RuntimeError("MockRedis: random operation error")

    async def get(self, key: str) -> Optional[str]:
        await self._check()
        val = self._data.get(key)
        return val.decode() if isinstance(val, bytes) else val

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        await self._check()
        self._data[key] = value

    async def delete(self, key: str):
        await self._check()
        self._data.pop(key, None)

    async def keys(self, pattern: str) -> list[str]:
        await self._check()
        import fnmatch
        return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

    async def hget(self, key: str, field: str) -> Optional[str]:
        await self._check()
        h = self._data.get(key, {})
        if isinstance(h, dict):
            val = h.get(field)
            return val.decode() if isinstance(val, bytes) else val
        return None

    async def hset(self, key: str, field: str, value: str):
        await self._check()
        if key not in self._data:
            self._data[key] = {}
        if isinstance(self._data[key], dict):
            self._data[key][field] = value

    async def hgetall(self, key: str) -> dict:
        await self._check()
        h = self._data.get(key, {})
        return h if isinstance(h, dict) else {}

    async def publish(self, channel: str, message: str):
        await self._check()
        if channel not in self._pubsub_channels:
            self._pubsub_channels[channel] = []
        self._pubsub_channels[channel].append(message)

    async def ping(self) -> bool:
        return self._is_available

    async def aclose(self):
        self._data.clear()


class MockDBFailover:
    """Simulates DB with controlled failure modes for chaos testing."""

    def __init__(self):
        self._is_available = True
        self._fail_after_ops: Optional[int] = None
        self._op_count = 0
        self._latency_ms: float = 0.0

    def set_fail_after(self, ops: int):
        self._fail_after_ops = ops

    def set_latency(self, ms: float):
        self._latency_ms = ms

    def set_availability(self, available: bool):
        self._is_available = available

    async def _check(self):
        self._op_count += 1
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)
        if self._fail_after_ops and self._op_count >= self._fail_after_ops:
            self._is_available = False
        if not self._is_available:
            raise RuntimeError("MockDB: connection refused")

    async def execute(self, query: str, params: Optional[dict] = None) -> list:
        await self._check()
        return [{"mock": True}]

    async def fetchval(self, query: str, params: Optional[dict] = None):
        await self._check()
        return True

    async def connect(self):
        pass

    async def engine_dispose(self):
        pass


# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Provides a MockRedisFailover instance for chaos testing."""
    return MockRedisFailover()


@pytest.fixture
def mock_db():
    """Provides a MockDBFailover instance for chaos testing."""
    return MockDBFailover()


@pytest_asyncio.fixture
async def db_client() -> AsyncGenerator[TimescaleClient, None]:
    """Provides a real TimescaleClient connected to the database."""
    db = TimescaleClient(settings.database_url)
    await db.connect()
    yield db
    await db.engine.dispose()


@pytest.fixture
def chaos_order():
    """Generate a mock order for chaos testing."""
    return {
        "order_id": str(uuid.uuid4()),
        "strategy_id": str(uuid.uuid4()),
        "symbol": "SPY",
        "side": random.choice(["buy", "sell"]),
        "qty": round(random.uniform(1, 100), 2),
        "price": round(random.uniform(400, 500), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def chaos_strategy():
    """Generate a mock strategy for chaos testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": f"chaos_strat_{uuid.uuid4().hex[:6]}",
        "status": "validated",
        "code": "def execute(data): return {'signal': 1}",
        "parameters": json.dumps({"period": 14, "threshold": 0.02}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
