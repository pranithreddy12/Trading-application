#!/usr/bin/env python
"""
Copy Trader Smoke Test — Step 2: Insert test leader order and verify copy execution
"""
import asyncio
import time
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    print("\n=== STEP 1: Verify Leader & Follower Accounts ===")
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT leader_id, account_ref, is_active FROM copy_leader_accounts;"))
        leaders = res.fetchall()
        print(f"Leaders in DB: {leaders}")

        res = await conn.execute(text("SELECT follower_id, leader_id, account_ref, allocation_ratio FROM copy_follower_accounts;"))
        followers = res.fetchall()
        print(f"Followers in DB: {followers}")

    print("\n=== STEP 2: Insert Test Leader Order ===")
    async with db.engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO leader_orders (id, account_ref, symbol, side, qty, price, status, created_at)
            VALUES ('test_order_001', 'SIM_LEADER_001', 'NVDA', 'buy', 10, 150.0, 'filled', NOW())
            ON CONFLICT DO NOTHING;
        """))
    print("✓ Test leader order inserted (test_order_001, NVDA, 10 shares buy)")

    print("\n=== STEP 3: Wait for copy_trader polling (3 seconds) ===")
    await asyncio.sleep(3)

    print("\n=== STEP 4: Verify Copy Execution Log ===")
    async with db.engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT id, leader_order_id, follower_order_id, follower_id, symbol, side, 
                   leader_qty, follower_qty, status, failure_reason, latency_ms, created_at
            FROM copy_execution_log
            ORDER BY created_at DESC
            LIMIT 10;
        """))
        logs = res.fetchall()
        if logs:
            print(f"✓ Found {len(logs)} copy execution log entries:")
            for log in logs:
                print(f"  - leader_order_id={log[1]}, follower_id={log[3]}, symbol={log[4]}, "
                      f"leader_qty={log[6]}, follower_qty={log[7]}, status={log[8]}, "
                      f"failure_reason={log[9]}, latency_ms={log[10]}")
        else:
            print("✗ No copy execution log entries found. Check if polling worked.")

    print("\n=== STEP 5: Summary ===")
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log;"))
        count = res.scalar()
        print(f"Total copy_execution_log entries: {count}")

        res = await conn.execute(text("SELECT COUNT(*) FROM leader_orders WHERE account_ref='SIM_LEADER_001';"))
        order_count = res.scalar()
        print(f"Leader orders for SIM_LEADER_001: {order_count}")

    await db.disconnect()
    print("\n=== SMOKE TEST COMPLETE ===\n")


if __name__ == "__main__":
    asyncio.run(main())
