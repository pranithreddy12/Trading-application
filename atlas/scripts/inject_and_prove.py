"""
Direct signal injection: prove the execution → save_paper_trade chain.

1. Start the full autonomous cycle
2. Wait for initialization
3. Inject a validated signal into Redis
4. Monitor log for instrumentation markers
5. Check paper_trades in DB for the new row
"""

import asyncio
import json
import sys
import os
import time
import signal as signal_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text


REDIS_URL = "redis://localhost:6380"
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"
STRATEGY_SIGNAL_CHANNEL = "strategy_signals"
LOG_FILE = "logs/inject_proof.log"

# Use a known validated strategy ID from the DB
STRATEGY_ID = "18b1354c-a39a-49f6-a21b-c38d141bc825"


async def inject_signal(redis: Redis):
    payload = {
        "type": "validated",
        "strategy_id": STRATEGY_ID,
        "symbol": "BTCUSDT",
        "side": "buy",
        "qty": 0.01,
        "feature_snapshot_id": None,
        "deployment_id": "manual-injection",
        "mode": "paper",
    }
    print(
        f"[INJECT] Publishing to {STRATEGY_SIGNAL_CHANNEL}: {json.dumps(payload, indent=2)}"
    )
    await redis.publish(STRATEGY_SIGNAL_CHANNEL, json.dumps(payload))
    print("[INJECT] Signal published")


async def count_paper_trades(engine) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
        return result.scalar()


async def get_last_paper_trade(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM paper_trades ORDER BY time DESC LIMIT 1")
        )
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        return None


async def main():
    print("=" * 60)
    print("EXECUTION CHAIN PROOF: Signal Injection Test")
    print("=" * 60)

    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    engine = create_async_engine(DATABASE_URL)

    # Count paper_trades before
    before_count = await count_paper_trades(engine)
    print(f"\n[DB] Paper trades BEFORE: {before_count}")

    # Get last trade before
    last_before = await get_last_paper_trade(engine)
    if last_before:
        print(
            f"[DB] Last trade before: strategy={last_before.get('strategy_id')} symbol={last_before.get('symbol')} time={last_before.get('time')}"
        )

    # Inject the signal
    print(f"\n[ACTION] Injecting signal for strategy {STRATEGY_ID}...")
    await inject_signal(redis)

    # Wait for execution pipeline to complete
    print("[WAIT] Waiting 15s for execution pipeline...")
    await asyncio.sleep(15)

    # Count paper_trades after
    after_count = await count_paper_trades(engine)
    print(f"\n[DB] Paper trades AFTER: {after_count}")
    print(f"[DB] New trades: {after_count - before_count}")

    if after_count > before_count:
        last_after = await get_last_paper_trade(engine)
        print(f"\n[SUCCESS] New paper trade detected:")
        if last_after:
            for k, v in last_after.items():
                print(f"  {k}: {v}")
    else:
        print("\n[FAILURE] No new paper trade was created.")
        print("The execution pipeline likely failed before save_paper_trade().")

    # Check order_flow for state transitions
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT strategy_id, state, created_at
                FROM order_flow
                WHERE strategy_id::text = :sid
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {"sid": STRATEGY_ID},
        )
        rows = result.fetchall()
        if rows:
            print(f"\n[ORDER FLOW] Last transitions for {STRATEGY_ID}:")
            for r in rows:
                print(f"  {r[1]} at {r[2]}")
        else:
            print(f"\n[ORDER FLOW] No transitions found for {STRATEGY_ID}")

    await redis.close()
    await engine.dispose()

    print("\n[DONE] Check atlas/logs/inject_proof.log for detailed output")
    print(
        "Also check: grep -n 'PERSISTING\\|SAVE_PAPER\\|PAPER_TRADE\\|Triggering execution\\|open_position' atlas/logs/runtime_audit.log atlas/logs/inject_proof.log 2>/dev/null"
    )


if __name__ == "__main__":
    asyncio.run(main())
