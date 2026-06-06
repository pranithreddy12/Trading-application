"""
Test whether redis-py async get_message() returns early when a message arrives
DURING the timeout window — replicating ExecutionGateway config.
"""

import asyncio
import json
import time
from redis.asyncio import Redis


async def main():
    print(
        "=== Test: get_message(timeout) returns early when message arrives mid-wait ==="
    )
    print()

    r = Redis.from_url("redis://localhost:6380")  # decode_responses=False
    pubsub = r.pubsub()
    await pubsub.subscribe("strategy_signals")
    pub = Redis.from_url("redis://localhost:6380")

    # Drain subscribe ack
    for _ in range(3):
        await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)

    # Now start a long get_message() call and publish WHILE it's waiting
    print("Starting get_message(timeout=5.0) at", time.strftime("%H:%M:%S"))
    t0 = time.monotonic()

    async def publish_after_delay():
        await asyncio.sleep(1.5)
        print(f"Publishing at +{time.monotonic() - t0:.1f}s")
        payload = json.dumps({"type": "validated", "ts": time.time()})
        n = await pub.publish("strategy_signals", payload)
        print(f"Published to {n} subscribers at +{time.monotonic() - t0:.1f}s")

    async def listener():
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
        elapsed = time.monotonic() - t0
        if msg:
            print(f"GOT message at +{elapsed:.3f}s (returned early: {elapsed < 4.5})")
            print(f"  type={msg['type']}, data={msg['data']}")
        else:
            print(f"No message (timeout) at +{elapsed:.3f}s")

    await asyncio.gather(publish_after_delay(), listener())

    print()
    print("=== Test: publish BEFORE get_message ===")
    # Verify it also works when message is pre-published
    payload = json.dumps({"type": "validated", "ts": time.time()})
    await pub.publish("strategy_signals", payload)
    print("Published before get_message")
    t0 = time.monotonic()
    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
    elapsed = time.monotonic() - t0
    if msg:
        print(f"GOT at +{elapsed:.3f}s: data={msg['data'][:60]}")
    else:
        print(f"NOTHING at +{elapsed:.3f}s")

    await r.aclose()
    await pub.aclose()


if __name__ == "__main__":
    asyncio.run(main())
