"""
Direct proof that save_paper_trade() persists data.

1. Calls save_paper_trade() directly via TimescaleClient
2. Verifies the row appears in paper_trades
3. Reports exact values
"""

import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from datetime import datetime, timezone

DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"
TRACE_ID = str(uuid.uuid4())
STRATEGY_ID = "18b1354c-a39a-49f6-a21b-c38d141bc825"


async def main():
    print("=" * 70)
    print("PERSISTENCE PROOF: save_paper_trade() Direct Test")
    print("=" * 70)

    # First try using the TimescaleClient directly
    from atlas.data.storage.timescale_client import TimescaleClient

    client = TimescaleClient(DATABASE_URL)
    await client.connect()

    trade_payload = {
        "strategy_id": STRATEGY_ID,
        "symbol": "PROOFCOIN",
        "side": "buy",
        "quantity": 0.05,
        "price": 123.45,
        "fill_price": 123.45,
        "status": "filled",
        "pnl": 0.0,
        "trace_id": TRACE_ID,
        "feature_snapshot_id": None,
        "origin": "execution",
    }

    print(f"\nTrace ID: {TRACE_ID}")
    print(f"Payload: {trade_payload}")

    # Count before
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM paper_trades WHERE trace_id = :t"),
            {"t": TRACE_ID},
        )
        before = result.scalar()

    print(f"\nRows with this trace_id BEFORE: {before}")

    # Call save_paper_trade
    print("\n--- Calling save_paper_trade() ---")
    await client.save_paper_trade(trade_payload)
    print("--- save_paper_trade() returned ---")

    # Count after
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM paper_trades WHERE trace_id = :t"),
            {"t": TRACE_ID},
        )
        after = result.scalar()

    print(f"\nRows with this trace_id AFTER: {after}")
    print(f"Persisted: {'YES' if after > before else 'NO'}")

    if after > before:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT * FROM paper_trades WHERE trace_id = :t ORDER BY time DESC LIMIT 1"
                ),
                {"t": TRACE_ID},
            )
            row = result.fetchone()
            if row:
                d = dict(row._mapping)
                print(f"\nVerified row in paper_trades:")
                for k, v in d.items():
                    print(f"  {k}: {v}")
    else:
        print("\nFAILED: No row appeared in paper_trades")
        # Fallback: try direct INSERT like save_paper_trade does
        print("\n--- Fallback: direct INSERT (same SQL as save_paper_trade) ---")
        async with client.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO paper_trades
                    (time, strategy_id, symbol, side, quantity, price, fill_price, status, pnl, trace_id, feature_snapshot_id)
                    VALUES (NOW(), :strategy_id, :symbol, :side, :quantity,
                            :price, :fill_price, :status, :pnl, :trace_id, :feature_snapshot_id)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "strategy_id": STRATEGY_ID,
                    "symbol": "FALLBACKCOIN",
                    "side": "sell",
                    "quantity": 0.01,
                    "price": 99.99,
                    "fill_price": 99.99,
                    "status": "filled",
                    "pnl": 0.0,
                    "trace_id": TRACE_ID + "-fallback",
                    "feature_snapshot_id": None,
                },
            )
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM paper_trades WHERE trace_id = :t"),
                {"t": TRACE_ID + "-fallback"},
            )
            row = result.fetchone()
            if row:
                d = dict(row._mapping)
                print(f"Fallback INSERT succeeded:")
                for k, v in d.items():
                    print(f"  {k}: {v}")
            else:
                print("Fallback INSERT also failed!")

    await client.close()
    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
