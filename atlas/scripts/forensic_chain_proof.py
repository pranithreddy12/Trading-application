"""
Forensic chain proof: Start system → inject signal → verify forensic markers appear in logs.

Proves: GATEWAY_LOOP_ITERATION → SIGNAL_RECEIVED_RAW → SIGNAL_DECODED → SIGNAL_EXECUTE_START
"""

import asyncio
import json
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.asyncio import Redis
from atlas.config.settings import get_settings
from loguru import logger

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


async def inject_after_delay(settings, delay: float):
    """Wait for startup then inject the signal."""
    await asyncio.sleep(delay)
    redis = Redis.from_url(settings.redis_url)
    payload = json.dumps(SIGNAL)
    print(f"\n{'=' * 60}")
    print(f"[FORENSIC] Injecting signal to '{CHANNEL}' at +{delay}s")
    print(f"  payload: {json.dumps(SIGNAL, indent=2)}")
    count = await redis.publish(CHANNEL, payload)
    print(f"[FORENSIC] Redis reports {count} subscriber(s)")
    print(f"{'=' * 60}\n")
    await redis.aclose()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--duration", type=int, default=5, help="System runtime in minutes"
    )
    parser.add_argument(
        "--inject-after",
        type=int,
        default=90,
        help="Seconds to wait before injecting signal",
    )
    args = parser.parse_args()

    settings = get_settings()

    # Start system and injector concurrently
    from atlas.scripts.full_autonomous_cycle import main as system_main

    # Override system args
    sys.argv = ["full_autonomous_cycle.py", f"--duration-minutes={args.duration}"]

    injector = asyncio.create_task(inject_after_delay(settings, args.inject_after))

    # Run the system (it will block until duration expires)
    await system_main()

    # Ensure injector completed
    await injector

    print("\n[DONE] Check log file for forensic markers:")
    print(
        "  grep -n 'GATEWAY_LOOP_ITERATION\\|SIGNAL_RECEIVED\\|SIGNAL_DECODED\\|SIGNAL_EXECUTE_START' logs/*.log"
    )


if __name__ == "__main__":
    asyncio.run(main())
