"""Phase 2: Verify clean state for soak test."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"

async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        print("=" * 60)
        print("PHASE 2: VERIFY CLEAN STATE")
        print("=" * 60)

        # 1. Check existing tables
        r = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        existing = {row[0] for row in r.fetchall()}
        print(f"\nTables in database: {len(existing)}")

        # 2. Paper trades: all rows sample
        print("\n--- Paper Trades Sample (3 rows) ---")
        r = await conn.execute(text("SELECT * FROM paper_trades LIMIT 3"))
        cols = list(r.keys())
        print(f"  Columns: {cols}")
        for row in r.fetchall():
            d = dict(row._mapping)
            print(f"  {d}")

        # 3. Check status distribution of all paper trades
        print("\n--- Paper Trades Status Distribution ---")
        for group_col in ["status", "direction", "strategy_id", "symbol"]:
            if group_col in cols:
                try:
                    r = await conn.execute(text(f"SELECT {group_col}, COUNT(*) FROM paper_trades GROUP BY {group_col} ORDER BY {group_col}"))
                    rows = r.fetchall()
                    if rows:
                        print(f"  By {group_col}:")
                        for row in rows:
                            print(f"    {row[0]}: {row[1]}")
                except Exception as e:
                    print(f"  Error on {group_col}: {e}")

        # 4. Check for demo/seed origins in event_store
        print("\n--- Event Store: Cleanliness Check ---")
        r = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='event_store'"))
        event_cols = {row[0] for row in r.fetchall()}
        print(f"  Event store columns: {event_cols}")

        if "event_type" in event_cols:
            r = await conn.execute(text("SELECT event_type, COUNT(*) FROM event_store GROUP BY event_type ORDER BY COUNT(*) DESC"))
            print("  Event type distribution:")
            for row in r.fetchall():
                print(f"    {row[0]}: {row[1]}")

        # 5. Check for demo/seed references in metadata
        if "metadata" in event_cols:
            r = await conn.execute(text("SELECT COUNT(*) FROM event_store WHERE metadata::text ILIKE '%demo%' OR metadata::text ILIKE '%seed%'"))
            count = r.scalar()
            print(f"\n  Events with 'demo' or 'seed' in metadata: {count}")

        # 6. Positions check
        if "positions" in existing:
            print("\n--- Positions ---")
            r = await conn.execute(text("SELECT * FROM positions LIMIT 5"))
            pos_cols = list(r.keys())
            rows = r.fetchall()
            print(f"  Total: {len(rows)}")
            for row in rows:
                d = dict(row._mapping)
                print(f"  {d}")

        # 7. Recent strategies
        print("\n--- Latest 5 Strategies ---")
        r = await conn.execute(text("SELECT id, name, status, created_at FROM strategies ORDER BY created_at DESC LIMIT 5"))
        for row in r.fetchall():
            sid = str(row[0])[:8]
            print(f"  {sid}... | {str(row[1]):<30} | {row[2]:<20} | {row[3]}")

        # 8. Backtest results count by strategy
        if "backtest_results" in existing:
            print("\n--- Backtest Results ---")
            r = await conn.execute(text("SELECT COUNT(*) FROM backtest_results"))
            print(f"  Total: {r.scalar()}")

        # 9. Feature importance
        if "feature_importance" in existing:
            print("\n--- Feature Importance ---")
            r = await conn.execute(text("SELECT feature_name, feature_importance_score, n_uses FROM feature_importance ORDER BY feature_importance_score DESC LIMIT 5"))
            for row in r.fetchall():
                print(f"  {str(row[0]):<20} | importance={float(row[1]):.4f} | uses={row[2]}")

        # 10. Drift detection
        if "drift_detection" in existing:
            print("\n--- Drift Detection ---")
            r = await conn.execute(text("SELECT * FROM drift_detection ORDER BY detected_at DESC LIMIT 3"))
            cols = list(r.keys())
            for row in r.fetchall():
                d = dict(row._mapping)
                print(f"  {d}")

        print("\n" + "=" * 60)
        print("PHASE 2: VERIFY CLEAN STATE COMPLETE")
        print("=" * 60)

    await engine.dispose()

asyncio.run(main())
