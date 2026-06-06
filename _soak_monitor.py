"""Phase 4-10: Soak test monitoring — captures metrics every 15 minutes."""
import asyncio
import sys
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"
TIMELINE_LOG = "logs/soak_timeline.log"
MONITOR_LOG = "logs/soak_monitor.log"

def log(msg):
    line = f"[{datetime.utcnow().isoformat()}] {msg}"
    print(line)
    with open(MONITOR_LOG, "a") as f:
        f.write(line + "\n")

async def run_query(conn, sql, params=None):
    """Execute a query and return fetchall results.
    Rolls back on error to prevent InFailedSQLTransactionError cascading.
    """
    try:
        r = await conn.execute(text(sql), params or {})
        return r.fetchall()
    except Exception as e:
        try:
            await conn.rollback()
        except Exception:
            pass
        return [("ERROR", str(e))]

async def capture_snapshot(interval_num):
    """Capture a full monitoring snapshot."""
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        # Use a savepoint-style approach: rollback after any error to keep tx alive
        try:
            await conn.execute(text("SELECT 1"))
        except Exception:
            pass  # connection fresh

        timestamp = f"T={interval_num * 15}min ({(datetime.utcnow().isoformat())})"
        log(f"\n{'='*60}")
        log(f"SNAPSHOT {interval_num}: {timestamp}")
        log(f"{'='*60}")

        # 1. Strategy Pipeline
        log("\n--- Strategies by Status ---")
        rows = await run_query(conn, "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY status")
        for row in rows:
            log(f"  {row[0]}: {row[1]}")

        # 2. Backtest Throughput
        log("\n--- Backtest Results ---")
        rows = await run_query(conn, "SELECT COUNT(*) FROM backtest_results")
        log(f"  Total: {rows[0][0] if rows else 0}")

        # 3. Validated Strategies
        log("\n--- Validated Strategies ---")
        rows = await run_query(conn, "SELECT COUNT(*) FROM strategies WHERE status='validated'")
        log(f"  Total: {rows[0][0] if rows else 0}")

        # 4. Deployments (any mode) - use fresh connection for each table
        for tbl in ["deployment_governance", "deployments", "deployment_records"]:
            rows = await run_query(conn, f"SELECT mode, COUNT(*) FROM {tbl} GROUP BY mode ORDER BY mode")
            if rows and rows[0][0] != "ERROR":
                log(f"\n--- {tbl} by Mode ---")
                for row in rows:
                    log(f"  {row[0]}: {row[1]}")

        # 5. Paper Trading - use run_query (wraps in try/except) for column discovery
        log("\n--- Paper Trades Summary ---")
        cols_result = await run_query(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='paper_trades'")
        cols = [r[0] for r in cols_result if r[0] != "ERROR"]
        
        if "origin" in cols:
            rows = await run_query(conn, "SELECT origin, COUNT(*), COALESCE(SUM(pnl), 0) FROM paper_trades GROUP BY origin ORDER BY origin")
        elif "source" in cols:
            rows = await run_query(conn, "SELECT source, COUNT(*), COALESCE(SUM(pnl), 0) FROM paper_trades GROUP BY source ORDER BY source")
        else:
            rows = await run_query(conn, "SELECT 'total' as grp, COUNT(*), COALESCE(SUM(pnl), 0) FROM paper_trades")
        
        for row in rows:
            if row[0] != "ERROR":
                log(f"  {row[0]}: count={row[1]}, pnl={row[2]}")
        
        # 6. Positions
        log("\n--- Positions ---")
        rows = await run_query(conn, "SELECT COUNT(*) FROM positions")
        log(f"  Total: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # 7. Scout Activity
        log("\n--- Scout Signals by Source ---")
        tables_result = await run_query(conn, "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        existing_tables = {r[0] for r in tables_result if r[0] != "ERROR"}
        if "scout_signals" in existing_tables:
            rows = await run_query(conn, "SELECT source, COUNT(*) FROM scout_signals GROUP BY source ORDER BY source")
            for row in rows:
                if row[0] != "ERROR":
                    log(f"  {row[0]}: {row[1]}")

        # 8. Event Lineage
        log("\n--- Event Store ---")
        rows = await run_query(conn, "SELECT COUNT(*) FROM event_store")
        log(f"  Total: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # 9. Feature Importance
        log("\n--- Feature Importance ---")
        if "feature_importance" in existing_tables:
            rows = await run_query(conn, "SELECT COUNT(*), COUNT(DISTINCT feature_importance_score) FROM feature_importance")
            if rows and rows[0][0] != "ERROR":
                log(f"  Features: {rows[0][0]}, Unique scores: {rows[0][1]}")

        # 10. Drift Detection
        log("\n--- Drift Detection ---")
        if "drift_detection" in existing_tables:
            rows = await run_query(conn, "SELECT COUNT(*), COALESCE(AVG(composite_severity), 0) FROM drift_detection")
            if rows and rows[0][0] != "ERROR":
                log(f"  Total: {rows[0][0]}, Avg severity: {rows[0][1]}")

        # 11. Execution logs (recent errors)
        log("\n--- Execution Errors (last 5) ---")
        if "execution_log" in existing_tables:
            rows = await run_query(conn, "SELECT state, error_message, created_at FROM execution_log WHERE error_message IS NOT NULL ORDER BY created_at DESC LIMIT 5")
            for row in rows:
                if row[0] != "ERROR":
                    log(f"  state={row[0]}, error={str(row[1])[:80] if row[1] else 'None'}, at={row[2]}")

        # 12. Copy execution log
        log("\n--- Copy Execution Log ---")
        if "copy_execution_log" in existing_tables:
            rows = await run_query(conn, "SELECT status, COUNT(*) FROM copy_execution_log GROUP BY status ORDER BY status")
            for row in rows:
                if row[0] != "ERROR":
                    log(f"  {row[0]}: {row[1]}")

        # Write to timeline
        with open(TIMELINE_LOG, "a") as f:
            f.write(f"\n--- SNAPSHOT {interval_num} ({timestamp}) ---\n")
            f.write(f"Strategies: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}\n")

    await engine.dispose()
    log(f"\nSNAPSHOT {interval_num} COMPLETE\n")

async def main():
    log("SOAK TEST MONITOR STARTED")
    log(f"Start time: {datetime.utcnow().isoformat()}")
    
    # Run interval number from command line or 0
    interval_start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n_intervals = int(sys.argv[2]) if len(sys.argv) > 2 else 8  # 8 x 15min = 2 hours
    
    for i in range(interval_start, interval_start + n_intervals):
        await capture_snapshot(i)
        if i < interval_start + n_intervals - 1:
            log(f"Waiting 15 minutes until next snapshot...")
            await asyncio.sleep(15 * 60)  # 15 minutes
    
    log("SOAK TEST MONITOR COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
