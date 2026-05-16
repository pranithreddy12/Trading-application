from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from atlas.api.services.auth_service import APIKey, APIRole

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int


class RateLimitService:
    """Role-aware rate limiting with Redis fixed-window counters."""

    ROLE_LIMITS = {
        APIRole.ADMIN.value: 600,
        APIRole.TRADER.value: 240,
        APIRole.READ_ONLY.value: 120,
        APIRole.FOLLOWER.value: 180,
        APIRole.MONITOR.value: 300,
    }

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url) if redis and redis_url else None
        self._local_store: dict[str, tuple[int, int]] = {}

    def _resolve_limit(self, api_key: APIKey) -> int:
        configured = int(api_key.rate_limit_per_min or 0)
        if configured > 0:
            return configured
        return self.ROLE_LIMITS.get(api_key.role.value, 100)

    def _window(self) -> tuple[int, int]:
        now = int(time.time())
        window_start = now - (now % 60)
        return window_start, window_start + 60

    async def check_and_consume(self, api_key: APIKey) -> RateLimitDecision:
        limit = self._resolve_limit(api_key)
        window_start, window_end = self._window()
        key = f"rl:{api_key.id}:{window_start}"

        if self.redis:
            try:
                current = await self.redis.incr(key)
                if current == 1:
                    await self.redis.expire(key, 65)
                remaining = max(limit - current, 0)
                return RateLimitDecision(
                    allowed=current <= limit,
                    limit=limit,
                    remaining=remaining,
                    reset_epoch=window_end,
                )
            except Exception as exc:
                logger.warning(f"Redis rate limit fallback to local store: {exc}")

        count, tracked_window = self._local_store.get(api_key.id, (0, window_start))
        if tracked_window != window_start:
            count = 0
            tracked_window = window_start
        count += 1
        self._local_store[api_key.id] = (count, tracked_window)
        remaining = max(limit - count, 0)
        return RateLimitDecision(
            allowed=count <= limit,
            limit=limit,
            remaining=remaining,
            reset_epoch=window_end,
        )

    @staticmethod
    def build_headers(decision: RateLimitDecision) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Reset": str(decision.reset_epoch),
        }
