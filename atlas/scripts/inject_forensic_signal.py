"""
Inject a signal into Redis and verify ExecutionGateway receives it.
Matches the exact signal format expected by ExecutionGateway.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.asyncio import Redis
from atlas.config.settings import get_settings

CHANNEL = "strategy_signals"

SIGNAL = {
    "type": "validated",
    "strategy_id": "18b1354c-a39a-49f6-a21b-c38d141bc825",
    "symbol": "BTCUSDT",
    "side": "buy",
    "qty": 0.01,
    "deployment_id": "forensic-injection",
    "mode": "paper",
    "feature_snapshot_id": None,
}


async def main():
    settings = get_settings()
    redis = Redis.from_url(
        settings.redis_url
    )  # decode_responses=False (same as system)

    print(f"[FORENSIC] Publishing to '{CHANNEL}':")
    print(f"  payload: {json.dumps(SIGNAL, indent=2)}")

    count = await redis.publish(CHANNEL, json.dumps(SIGNAL))
    print(f"[FORENSIC] Redis reports {count} subscriber(s) received the message")

    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
