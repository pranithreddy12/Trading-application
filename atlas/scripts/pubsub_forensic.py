"""
Redis PubSub Forensic Audit — replicate ExecutionGateway EXACT configuration.

Tests: decode_responses=False, get_message(timeout=1.0), ignore_subscribe_messages=True
"""

import asyncio
import json
import time
from redis.asyncio import Redis


async def main():
    print("=== Replicating ExecutionGateway pubsub config ===")
    print("decode_responses=False")
    print()

    # EXACT same as full_autonomous_cycle.py: Redis.from_url(settings.redis_url)
    r = Redis.from_url("redis://localhost:6380")  # decode_responses=False

    pubsub = r.pubsub()
    await pubsub.subscribe("strategy_signals")

    # Publisher (separate connection)
    pub = Redis.from_url("redis://localhost:6380")

    print("Subscribed. Now draining subscribe ack (like run() does)...")
    print()

    # Phase 1: Initial drain (first N calls return None due to subscribe ack)
    for i in range(5):
        t0 = time.monotonic()
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        elapsed = time.monotonic() - t0
        print(f"  Drain call {i}: got={msg is not None}, elapsed={elapsed:.3f}s")
        if msg:
            print(
                f"    type field: type={type(msg['type']).__name__} value={msg['type']}"
            )
            print(f"    data field: type={type(msg['data']).__name__}")
            if isinstance(msg["data"], bytes):
                print(f"    data bytes: {msg['data'][:100]}")
            else:
                print(f"    data str: {msg['data'][:100]}")

    # Phase 2: Now listening, publish a message
    print()
    print("Publishing test signal...")
    payload = json.dumps(
        {
            "type": "validated",
            "strategy_id": "test-123",
            "symbol": "BTCUSDT",
            "side": "buy",
            "qty": 0.01,
        }
    )
    num_subs = await pub.publish("strategy_signals", payload)
    print(f"Published to {num_subs} subscriber(s)")
    print(f"Payload type={type(payload).__name__}, len={len(payload)}")
    print()

    # Phase 3: Try to receive
    for i in range(10):
        t0 = time.monotonic()
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        elapsed = time.monotonic() - t0
        print(f"  Receive call {i}: got={msg is not None}, elapsed={elapsed:.3f}s")
        if msg:
            print(
                f"    CHANNEL: {msg.get('channel', 'MISSING')} "
                f"(type={type(msg.get('channel', '')).__name__})"
            )
            print(
                f"    TYPE field: type={type(msg['type']).__name__} value={msg['type']}"
            )
            print(f"    msg['type'] == 'message': {msg['type'] == 'message'}")
            data_raw = msg["data"]
            print(f"    DATA field: type={type(data_raw).__name__}")
            if isinstance(data_raw, bytes):
                print(f"    data bytes: {data_raw[:100]}")
                decoded = json.loads(data_raw)
            else:
                print(f"    data str: {data_raw[:100]}")
                decoded = json.loads(data_raw)
            print(
                f"    decoded: type={decoded.get('type')} "
                f"strategy_id={decoded.get('strategy_id')}"
            )

            # This is the EXACT check in execution_gateway.py line 219-221
            type_check = (
                decoded.get("type") == "validated" or decoded.get("type") == "signal"
            )
            print(
                f"    EXACT gateway filter check (type=='validated' or 'signal'): "
                f"{type_check}"
            )
            break

    print()
    print("=== Test complete ===")

    await r.aclose()
    await pub.aclose()


if __name__ == "__main__":
    asyncio.run(main())
