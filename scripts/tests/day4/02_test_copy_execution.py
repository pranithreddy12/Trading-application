#!/usr/bin/env python
"""
Day 4 Copy Trader Smoke Test — Execution Verification

Purpose:
  - Insert test leader order
  - Verify copy execution was logged
  - Verify allocation ratio applied

Usage:
  python scripts/tests/day4/02_test_copy_execution.py
"""
import asyncio
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    print("=== Day 4 Copy Trader — Execution Test ===\n")
    
    print("=== STEP 1: Insert Test Leader Order ===")
    async with db.engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO leader_orders (account_ref, symbol, side, qty, price, status)
            VALUES ('SIM_LEADER_001', 'NVDA', 'buy', 10, 150.0, 'filled')
            RETURNING id, account_ref, symbol, side, qty;
        """))
        row = result.fetchone()
        print(f"✓ Leader order inserted: {row}")

    print("\n=== STEP 2: Wait for copy_trader polling (5 seconds) ===")
    await asyncio.sleep(5)

    print("\n=== STEP 3: Check Copy Execution Log ===")
    async with db.engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT 
                leader_order_id, follower_id, symbol, side, 
                leader_qty, follower_qty, status, failure_reason, latency_ms, created_at
            FROM copy_execution_log
            ORDER BY created_at DESC
            LIMIT 10;
        """))
        logs = result.fetchall()
        
        if logs:
            print(f"✓ Found {len(logs)} execution log(s):")
            for i, log in enumerate(logs, 1):
                print(f"\n  Entry {i}:")
                print(f"    - leader_order_id: {log[0]}")
                print(f"    - follower_id: {log[1]}")
                print(f"    - symbol: {log[2]}, side: {log[3]}")
                print(f"    - leader_qty: {log[4]}, follower_qty: {log[5]}")
                print(f"    - status: {log[6]}, failure_reason: {log[7]}")
                print(f"    - latency_ms: {log[8]}")
                
                if log[6] == 'filled' and float(log[5]) == 5.0:
                    print(f"    ✓ PASS: follower_qty=5 (0.5 ratio of leader_qty=10)")
        else:
            print("✗ No copy execution log entries found yet.")

    print("\n=== Summary ===")
    async with db.engine.connect() as conn:
        count = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log;"))
        total = count.scalar()
        print(f"Total copy_execution_log entries: {total}")


if __name__ == "__main__":
    asyncio.run(main())
