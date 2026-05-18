import asyncio
import os
import sys
from datetime import datetime

# Add the project root to sys.path
project_root = r'C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS'
if project_root not in sys.path:
    sys.path.append(project_root)

from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy.sql import text

async def main():
    db_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas"
    client = TimescaleClient(db_url)
    
    # 1. Insert test leader order
    insert_query = text(\"\"\"
        INSERT INTO leader_orders (id, account_ref, symbol, side, qty, price, status, created_at)
        VALUES ('test_order_001', 'SIM_LEADER_001', 'NVDA', 'buy', 10, 150.0, 'filled', NOW())
        ON CONFLICT (id) DO UPDATE SET
            account_ref = EXCLUDED.account_ref,
            symbol = EXCLUDED.symbol,
            side = EXCLUDED.side,
            qty = EXCLUDED.qty,
            price = EXCLUDED.price,
            status = EXCLUDED.status,
            created_at = EXCLUDED.created_at;
    \"\"\")
    
    async with client.engine.begin() as conn:
        print("Inserting leader order...")
        await conn.execute(insert_query)
        print("Inserted.")

    print("Waiting 3 seconds for copy_trader...")
    await asyncio.sleep(3)

    async with client.engine.connect() as conn:
        # 2. Query copy_execution_log
        print("\n--- copy_execution_log ---")
        log_query = text(\"\"\"
            SELECT id, leader_order_id, follower_order_id, follower_id, symbol, side, leader_qty, follower_qty, status, failure_reason, latency_ms 
            FROM copy_execution_log ORDER BY created_at DESC LIMIT 5;
        \"\"\")
        logs = await conn.execute(log_query)
        for row in logs:
            print(row)

        # 3. Verify follower accounts
        print("\n--- copy_follower_accounts ---")
        follower_query = text("SELECT follower_id, leader_id, account_ref, allocation_ratio FROM copy_follower_accounts;")
        followers = await conn.execute(follower_query)
        followers_list = list(followers)
        for row in followers_list:
            print(row)
        if not followers_list:
            print("No followers found.")

        # 4. Verify leader accounts
        print("\n--- copy_leader_accounts ---")
        leader_query = text("SELECT leader_id, account_ref FROM copy_leader_accounts;")
        leaders = await conn.execute(leader_query)
        leaders_list = list(leaders)
        for row in leaders_list:
            print(row)
        if not leaders_list:
            print("No leaders found.")

if __name__ == '__main__':
    asyncio.run(main())
