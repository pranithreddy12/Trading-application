"""Phase 1: Pre-test database snapshot for 2-hour soak test."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"

def safe_query(r):
    """Return rows or empty list."""
    try:
        return r.fetchall()
    except Exception:
        return []

async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        print("=" * 60)
        print("PHASE 1: PRE-TEST SNAPSHOT")
        print("=" * 60)

        tables_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        r = await conn.execute(tables_query)
        existing = {row[0] for row in r.fetchall()}
        print(f"\nExisting tables ({len(existing)}): {sorted(existing)}")

        # 1. Strategies by status
        print("\n--- Strategies by Status ---")
        r = await conn.execute(text("SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY status"))
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 2. Paper trades
        print("\n--- Paper Trades ---")
        r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
        print(f"  Total: {r.scalar()}")

        if "paper_trades" in existing:
            r = await conn.execute(text("SELECT * FROM paper_trades LIMIT 1"))
            cols = list(r.keys())
            print(f"  Columns: {cols}")

            for group_col in ["origin", "source", "type", "direction", "status"]:
                if group_col in cols:
                    try:
                        r = await conn.execute(text(f"SELECT {group_col}, COUNT(*) FROM paper_trades GROUP BY {group_col} ORDER BY {group_col}"))
                        rows = r.fetchall()
                        if rows:
                            print(f"  By {group_col}:")
                            for row in rows:
                                print(f"    {row[0]}: {row[1]}")
                    except Exception:
                        pass

            if "pnl" in cols:
                r = await conn.execute(text("SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM paper_trades"))
                row = r.fetchone()
                print(f"  Total PnL: {row[1]}")

            if "entry_price" in cols:
                r = await conn.execute(text("SELECT COUNT(*), COALESCE(SUM((exit_price - entry_price) * quantity), 0) FROM paper_trades WHERE exit_price IS NOT NULL"))
                row = r.fetchone()
                print(f"  Computed PnL: {row[1]}")

        # 3. Deployments (if exists)
        if "deployments" in existing:
            print("\n--- Deployments by Mode ---")
            try:
                r = await conn.execute(text("SELECT mode, COUNT(*) FROM deployments GROUP BY mode ORDER BY mode"))
                for row in r.fetchall():
                    print(f"  {row[0]}: {row[1]}")
                r = await conn.execute(text("SELECT COUNT(*) FROM deployments"))
                print(f"  Total: {r.scalar()}")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print("\n--- Deployments ---")
            print("  Table 'deployments' does not exist")

        # Check if deployment_records exists
        if "deployment_records" in existing:
            print("\n--- Deployment Records by Mode ---")
            try:
                r = await conn.execute(text("SELECT mode, COUNT(*) FROM deployment_records GROUP BY mode ORDER BY mode"))
                for row in r.fetchall():
                    print(f"  {row[0]}: {row[1]}")
                r = await conn.execute(text("SELECT COUNT(*) FROM deployment_records"))
                print(f"  Total: {r.scalar()}")
            except Exception as e:
                print(f"  Error: {e}")

        # 4. Positions
        print("\n--- Positions ---")
        if "positions" in existing:
            r = await conn.execute(text("SELECT COUNT(*) FROM positions"))
            print(f"  Total: {r.scalar()}")
        else:
            print("  Table 'positions' does not exist")

        # 5. Event lineage
        print("\n--- Event Store ---")
        if "event_store" in existing:
            r = await conn.execute(text("SELECT COUNT(*) FROM event_store"))
            print(f"  Total: {r.scalar()}")
        else:
            print("  Table 'event_store' does not exist")

        # 6. Scout signals
        print("\n--- Scout Signals by Source ---")
        if "scout_signals" in existing:
            try:
                r = await conn.execute(text("SELECT source, COUNT(*) FROM scout_signals GROUP BY source ORDER BY source"))
                for row in r.fetchall():
                    print(f"  {row[0]}: {row[1]}")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print("  Table 'scout_signals' does not exist")

        # 7. Backtest results count
        print("\n--- Backtest Results ---")
        if "backtest_results" in existing:
            r = await conn.execute(text("SELECT COUNT(*) FROM backtest_results"))
            print(f"  Total: {r.scalar()}")
        else:
            print("  Table 'backtest_results' does not exist")

        # 8. Validated strategies
        print("\n--- Validated Strategies ---")
        r = await conn.execute(text("SELECT COUNT(*) FROM strategies WHERE status='validated'"))
        print(f"  Total: {r.scalar()}")

        # 9. Feature importance count
        print("\n--- Feature Importance ---")
        if "feature_importance" in existing:
            r = await conn.execute(text("SELECT COUNT(*) FROM feature_importance"))
            print(f"  Total: {r.scalar()}")
        else:
            print("  Table 'feature_importance' does not exist")

        # 10. Drift detection
        print("\n--- Drift Detection ---")
        if "drift_detection" in existing:
            r = await conn.execute(text("SELECT COUNT(*) FROM drift_detection"))
            print(f"  Total: {r.scalar()}")
        else:
            print("  Table 'drift_detection' does not exist")

    await engine.dispose()
    print("\n" + "=" * 60)
    print("PHASE 1: PRE-TEST SNAPSHOT COMPLETE")
    print("=" * 60)

asyncio.run(main())
