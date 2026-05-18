#!/usr/bin/env python
"""
Day 4 Copy Trader Smoke Test — Setup Test Data

Purpose:
  - Insert controlled test leader and follower accounts
  - Verify data persistence

Usage:
  python scripts/tests/day4/01_setup_test_data.py
"""
import asyncio
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    print("=== Day 4 Copy Trader Smoke Test — Setup ===\n")
    
    print("=== STEP 1: Insert Test Leader Account ===")
    async with db.engine.begin() as conn:
        result = await conn.execute(text("SELECT leader_id FROM copy_leader_accounts WHERE account_ref='SIM_LEADER_001';"))
        existing = result.scalar()
        
        if existing:
            print(f"✓ Leader already exists: leader_id={existing}")
            leader_id = existing
        else:
            result = await conn.execute(text("""
                INSERT INTO copy_leader_accounts (broker, account_ref, is_active)
                VALUES ('local', 'SIM_LEADER_001', true)
                RETURNING leader_id, account_ref;
            """))
            row = result.fetchone()
            print(f"✓ Leader inserted: leader_id={row[0]}, account_ref={row[1]}")
            leader_id = row[0]
    
    print("\n=== STEP 2: Insert Test Follower Account ===")
    async with db.engine.begin() as conn:
        result = await conn.execute(text("SELECT follower_id FROM copy_follower_accounts WHERE account_ref='SIM_FOLLOWER_001';"))
        existing = result.scalar()
        
        if existing:
            print(f"✓ Follower already exists: follower_id={existing}")
        else:
            result = await conn.execute(text("""
                INSERT INTO copy_follower_accounts (leader_id, broker, account_ref, allocation_ratio, max_position_pct, is_active)
                VALUES (:leader_id, 'local', 'SIM_FOLLOWER_001', 0.5, 0.10, true)
                RETURNING follower_id, account_ref;
            """), {"leader_id": leader_id})
            row = result.fetchone()
            print(f"✓ Follower inserted: follower_id={row[0]}, account_ref={row[1]}")

    print("\n=== Verification ===")
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM copy_leader_accounts WHERE account_ref='SIM_LEADER_001';"))
        leaders = res.scalar()
        
        res = await conn.execute(text("SELECT COUNT(*) FROM copy_follower_accounts WHERE account_ref='SIM_FOLLOWER_001';"))
        followers = res.scalar()
        
        print(f"Leaders: {leaders}, Followers: {followers}")

    print("\n✓ Test data ready!")


if __name__ == "__main__":
    asyncio.run(main())
