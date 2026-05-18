#!/usr/bin/env python
"""Apply the updated Day 4 migration (with leader_orders table)"""
import asyncio
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    statements = [
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
        """CREATE TABLE IF NOT EXISTS leader_orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_ref TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty NUMERIC NOT NULL,
            price NUMERIC,
            status TEXT NOT NULL DEFAULT 'pending',
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );""",
        "CREATE INDEX IF NOT EXISTS idx_leader_orders_account_ref ON leader_orders (account_ref);",
        "CREATE INDEX IF NOT EXISTS idx_leader_orders_created_at ON leader_orders (created_at DESC);",
    ]

    print("Applying leader_orders table migration...")
    async with db.engine.begin() as conn:
        for stmt in statements:
            try:
                await conn.execute(text(stmt))
                print(f"✓ {stmt.split()[0:4]}...")
            except Exception as e:
                print(f"✗ Failed: {str(e)[:100]}")
    
    print("\nVerifying leader_orders table exists...")
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name = 'leader_orders'"))
        if res.fetchone():
            print("✓ leader_orders table confirmed")
        else:
            print("✗ leader_orders table NOT found")

    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(main())
