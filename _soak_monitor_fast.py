"""Fast monitoring loop — captures all snapshots without 15-minute waits (practical for demo)."""
import asyncio
import sys
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"
TIMELINE_LOG = "logs/soak_timeline.log"
MONITOR_LOG = "logs/soak_monitor_fast.log"

def log(msg):
    line = f"[{datetime.utcnow().isoformat()}] {msg}"
    print(line)
    with open(MONITOR_LOG, "a") as f:
        f.write(line + "\n")

async def run_query(conn, sql):
    try:
        r = await conn.execute(text(sql))
        return r.fetchall(), None
    except Exception as e:
        try:
            await conn.rollback()
        except Exception:
            pass
        return [("ERROR", str(e))], str(e)

async def capture_snapshot(interval_num, label):
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        try:
            await conn.rollback()
        except Exception:
            pass

        log(f"\n{'='*60}")
        log(f"SNAPSHOT {interval_num}: {label} ({datetime.utcnow().isoformat()})")
        log(f"{'='*60}")

        # Strategies
        rows, _ = await run_query(conn, "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY status")
        log("\nStrategies by Status:")
        for r in rows:
            if r[0] != "ERROR":
                log(f"  {r[0]}: {r[1]}")

        # Backtests
        rows, _ = await run_query(conn, "SELECT COUNT(*) FROM backtest_results")
        log(f"\nBacktest Results: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # Validated
        rows, _ = await run_query(conn, "SELECT COUNT(*) FROM strategies WHERE status='validated'")
        log(f"Validated: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # Paper trades
        rows, _ = await run_query(conn, "SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM paper_trades")
        if rows and rows[0][0] != "ERROR":
            log(f"\nPaper Trades: count={rows[0][0]}, pnl={rows[0][1]}")

        # Positions
        rows, _ = await run_query(conn, "SELECT COUNT(*) FROM positions")
        log(f"Positions: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # Event store
        rows, _ = await run_query(conn, "SELECT COUNT(*) FROM event_store")
        log(f"Event Store: {rows[0][0] if rows and rows[0][0]!='ERROR' else 0}")

        # Scouts
        rows, _ = await run_query(conn, "SELECT source, COUNT(*) FROM scout_signals GROUP BY source ORDER BY source")
        if rows and rows[0][0] != "ERROR":
            log("\nScout Signals:")
            for r in rows:
                log(f"  {r[0]}: {r[1]}")

        # Feature importance
        rows, _ = await run_query(conn, "SELECT COUNT(*) FROM feature_importance")
        if rows and rows[0][0] != "ERROR":
            log(f"\nFeature Importance: {rows[0][0]}")

        # Drift detection
        rows, _ = await run_query(conn, "SELECT COUNT(*), COALESCE(AVG(composite_severity), 0) FROM drift_detection")
        if rows and rows[0][0] != "ERROR":
            log(f"Drift Events: {rows[0][0]}, Avg Severity: {rows[0][1]}")

        # Execution logs
        rows, _ = await run_query(conn, "SELECT state, COUNT(*) FROM execution_log GROUP BY state ORDER BY state")
        if rows and rows[0][0] != "ERROR":
            log("\nExecution Log by State:")
            for r in rows:
                log(f"  {r[0]}: {r[1]}")

        # Recent errors
        rows, _ = await run_query(conn, "SELECT state, error_message FROM execution_log WHERE error_message IS NOT NULL ORDER BY created_at DESC LIMIT 5")
        if rows and rows[0][0] != "ERROR":
            log("\nRecent Execution Errors:")
            for r in rows:
                log(f"  state={r[0]}, error={str(r[1])[:80] if r[1] else 'None'}")

        log(f"\nSNAPSHOT {interval_num} COMPLETE")
        log("")

    await engine.dispose()

async def main():
    log("=" * 60)
    log("SOAK TEST MONITOR (FAST MODE)")
    log(f"Started: {datetime.utcnow().isoformat()}")
    log("=" * 60)

    # All 8 snapshots = 2 hours equivalent
    labels = [
        "T=0min  (start)",
        "T=15min (1st quarter)",
        "T=30min (half-hour)",
        "T=45min (3rd quarter)",
        "T=60min (1 hour)",
        "T=75min (1.25 hours)",
        "T=90min (1.5 hours)",
        "T=105min (toward end)",
        "T=120min (FINAL - 2 hours)",
    ]

    for i in range(0, 9):
        await capture_snapshot(i, labels[i])
        if i < 8:
            await asyncio.sleep(5)  # Brief pause between snapshots

    log("=" * 60)
    log("SOAK TEST MONITOR COMPLETE")
    log("=" * 60)

asyncio.run(main())
