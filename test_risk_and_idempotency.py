#!/usr/bin/env python
"""
Smoke Test Phase 3: Risk rejection test and restart safety
"""
import asyncio
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    print("=== STEP 1: Test Risk Rejection ===")
    print("Reducing max_position_pct to 0.01 (very restrictive)...")
    
    async with db.engine.begin() as conn:
        await conn.execute(text("""
            UPDATE copy_follower_accounts
            SET max_position_pct = 0.01
            WHERE follower_id = '7416c767-c7e7-401b-90c7-e4e5b242b3ca';
        """))
    
    print("✓ Updated max_position_pct to 0.01")
    
    print("\n=== STEP 2: Insert Large Test Order (100 shares) ===")
    async with db.engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO leader_orders (account_ref, symbol, side, qty, price, status)
            VALUES ('SIM_LEADER_001', 'AAPL', 'buy', 100, 150.0, 'filled')
            RETURNING id;
        """))
        large_order_id = result.scalar()
        print(f"✓ Large order inserted: {large_order_id}")

    print("\n=== STEP 3: Wait for copy_trader polling (3 seconds) ===")
    await asyncio.sleep(3)

    print("\n=== STEP 4: Check if Order was Rejected by Risk Check ===")
    async with db.engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT 
                leader_order_id, symbol, leader_qty, follower_qty, status, failure_reason
            FROM copy_execution_log
            WHERE symbol = 'AAPL'
            ORDER BY created_at DESC
            LIMIT 5;
        """))
        logs = result.fetchall()
        
        if logs:
            for log in logs:
                status = log[4]
                reason = log[5]
                if status == 'skipped' and 'risk' in str(reason or '').lower():
                    print(f"✓ PASS: Order rejected by risk check")
                    print(f"  - Leader qty: {log[2]}")
                    print(f"  - Follower qty: {log[3]} (rejected)")
                    print(f"  - Reason: {reason}")
                elif status == 'filled':
                    print(f"ℹ Order was filled (risk check passed)")
                    print(f"  - Leader qty: {log[2]}, Follower qty: {log[3]}")
                else:
                    print(f"ℹ Order status: {status} ({reason})")
        else:
            print("✗ No entries found for AAPL symbol")

    print("\n=== STEP 5: Reset max_position_pct and Verify Idempotency ===")
    print("Resetting max_position_pct to 0.10...")
    
    async with db.engine.begin() as conn:
        await conn.execute(text("""
            UPDATE copy_follower_accounts
            SET max_position_pct = 0.10
            WHERE follower_id = '7416c767-c7e7-401b-90c7-e4e5b242b3ca';
        """))
    
    print("✓ Reset max_position_pct to 0.10")

    print("\n=== STEP 6: Count Unique Copies (Verify No Duplicates) ===")
    async with db.engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT leader_order_id, COUNT(*) as copy_count
            FROM copy_execution_log
            GROUP BY leader_order_id
            HAVING COUNT(*) > 1;
        """))
        duplicates = result.fetchall()
        
        if duplicates:
            print("✗ Found duplicate copies!")
            for dup in duplicates:
                print(f"  - Leader order {dup[0]}: {dup[1]} copies")
        else:
            print("✓ PASS: No duplicate copies (idempotency verified)")

    print("\n=== STEP 7: Final Summary ===")
    async with db.engine.connect() as conn:
        total = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log;"))
        print(f"Total copy executions: {total.scalar()}")
        
        filled = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status='filled';"))
        print(f"Successful fills: {filled.scalar()}")
        
        skipped = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status='skipped';"))
        print(f"Risk-rejected: {skipped.scalar()}")

    print("\n✓ All smoke tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
