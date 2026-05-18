"""
run_copy_trader_test.py
Standalone test for CopyTraderAgent — seeds a simulated leader order,
runs the agent for a few seconds, then prints latency from copy_execution_log.

Usage:
    python atlas/scripts/run_copy_trader_test.py
"""
import sys
import io
import asyncio
import uuid
from datetime import datetime

# Force UTF-8 output on Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.sql import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l5_execution.copy_trader import CopyTraderAgent, LocalSimulatorAdapter


# ─── Seed helpers ────────────────────────────────────────────────────────────

async def seed_copy_tables(db: TimescaleClient):
    """
    Create the copy trading tables if they don't exist and seed one
    leader + one follower so the agent has something to mirror.
    """
    async with db.engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_leader_accounts (
                leader_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_ref TEXT NOT NULL UNIQUE,
                broker      TEXT NOT NULL DEFAULT 'alpaca_paper',
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_follower_accounts (
                follower_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                leader_id        UUID NOT NULL REFERENCES copy_leader_accounts(leader_id),
                account_ref      TEXT NOT NULL,
                broker           TEXT NOT NULL DEFAULT 'alpaca_paper',
                allocation_ratio NUMERIC NOT NULL DEFAULT 1.0,
                max_position_pct NUMERIC NOT NULL DEFAULT 0.10,
                is_active        BOOLEAN NOT NULL DEFAULT TRUE,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_execution_log (
                id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                leader_order_id   TEXT NOT NULL,
                follower_order_id TEXT,
                leader_id         UUID,
                follower_id       UUID,
                symbol            TEXT NOT NULL,
                side              TEXT NOT NULL,
                leader_qty        NUMERIC,
                follower_qty      NUMERIC,
                latency_ms        INT,
                status            TEXT NOT NULL,
                failure_reason    TEXT,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS leader_orders (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_ref TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                qty         NUMERIC NOT NULL,
                price       NUMERIC,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

    logger.info("Copy tables ensured")

    # Seed leader + follower (idempotent)
    async with db.engine.begin() as conn:
        # Leader
        leader_ref = "leader_atlas_001"
        res = await conn.execute(
            text("SELECT leader_id FROM copy_leader_accounts WHERE account_ref = :ref"),
            {"ref": leader_ref}
        )
        row = res.fetchone()
        if not row:
            leader_id = str(uuid.uuid4())
            await conn.execute(text(
                "INSERT INTO copy_leader_accounts (leader_id, account_ref, broker) "
                "VALUES (:lid, :ref, 'alpaca_paper')"
            ), {"lid": leader_id, "ref": leader_ref})
            logger.info(f"Seeded leader: {leader_ref} ({leader_id})")
        else:
            leader_id = str(row[0])
            logger.info(f"Leader already exists: {leader_ref} ({leader_id})")

        # Follower
        res2 = await conn.execute(
            text("SELECT follower_id FROM copy_follower_accounts WHERE leader_id = :lid"),
            {"lid": leader_id}
        )
        if not res2.fetchone():
            await conn.execute(text(
                "INSERT INTO copy_follower_accounts "
                "(leader_id, account_ref, broker, allocation_ratio, max_position_pct) "
                "VALUES (:lid, 'follower_atlas_001', 'alpaca_paper', 1.0, 0.10)"
            ), {"lid": leader_id})
            logger.info("Seeded follower: follower_atlas_001")

    return leader_ref


async def inject_leader_order(db: TimescaleClient, leader_ref: str) -> str:
    """Insert a fake leader order and return its id."""
    order_id = str(uuid.uuid4())
    async with db.engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO leader_orders (id, account_ref, symbol, side, qty, price) "
            "VALUES (:id, :ref, 'SPY', 'buy', 10, 530.25)"
        ), {"id": order_id, "ref": leader_ref})
    logger.info(f"Injected leader order {order_id} for {leader_ref}")
    return order_id


async def print_latency_results(db: TimescaleClient):
    async with db.engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT leader_order_id, follower_order_id, latency_ms, status, created_at
            FROM copy_execution_log
            ORDER BY created_at DESC
            LIMIT 5
        """))
        rows = res.fetchall()

    print("\n" + "=" * 60)
    print("COPY EXECUTION LOG -- Last 5 rows")
    print("=" * 60)
    if not rows:
        print("  [WARN] No rows found -- agent may not have processed order yet")
    for r in rows:
        status_icon = "[OK]" if r.status == "filled" else "[FAIL]"
        latency = r.latency_ms if r.latency_ms is not None else "N/A"
        threshold = "PASS (<5000ms)" if isinstance(r.latency_ms, int) and r.latency_ms < 5000 else "FAIL"
        print(
            f"  {status_icon} leader={str(r.leader_order_id)[:8]}... "
            f"follower={str(r.follower_order_id or '')[:8]}... "
            f"latency={latency}ms [{threshold}] "
            f"status={r.status} at={r.created_at}"
        )
    print("=" * 60)


async def main():
    db = TimescaleClient(db_url=settings.database_url)
    await db.connect()
    redis = Redis.from_url(settings.redis_url)

    # 0. Clear the idempotency set so previous test orders don't block
    await redis.delete("copy:processed_leader_orders")
    logger.info("Cleared idempotency set")

    # 1. Ensure tables + seed data
    leader_ref = await seed_copy_tables(db)

    # 2. Inject a test leader order (triggers polling path)
    order_id = await inject_leader_order(db, leader_ref)

    # 3. Spin up agent with local simulator (no real broker calls)
    agent = CopyTraderAgent(
        redis_client=redis,
        db_client=db,
        broker=LocalSimulatorAdapter()
    )
    agent.status = "running"

    # 4. Run for 5 seconds (polling interval is 1s, so it will process the order)
    logger.info("Running CopyTraderAgent for 5 seconds...")
    try:
        await asyncio.wait_for(agent.run(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.info("5s timeout reached — checking results")

    # 5. Show latency results
    await print_latency_results(db)

    await redis.aclose()
    await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
