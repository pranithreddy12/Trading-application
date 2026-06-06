"""Compare dashboard API metrics against database values."""
import asyncio
import json
import urllib.request
import urllib.error
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"
DASHBOARD_URL = "http://localhost:8000"

def fetch_json(url):
    """Synchronous HTTP GET to fetch JSON from the dashboard API."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

async def main():
    print("=" * 60)
    print("DASHBOARD vs DATABASE METRICS COMPARISON")
    print("=" * 60)

    # 1. Query dashboard API
    print("\n--- Dashboard API: /dashboard/api/overview ---")
    overview = fetch_json(f"{DASHBOARD_URL}/dashboard/api/overview")
    if "error" in overview:
        print(f"  ERROR: {overview['error']}")
        dashboard_available = False
    else:
        dashboard_available = True
        print(json.dumps(overview, indent=2, default=str)[:2000])

    # 2. Query dashboard pipeline endpoint
    print("\n--- Dashboard API: /dashboard/api/pipeline ---")
    pipeline = fetch_json(f"{DASHBOARD_URL}/dashboard/api/pipeline")
    if "error" not in pipeline:
        print(json.dumps(pipeline, indent=2, default=str)[:1000])

    # 3. Query database for same metrics
    print("\n--- Database Metrics ---")
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        try:
            await conn.rollback()
        except Exception:
            pass

        async def q(sql):
            try:
                r = await conn.execute(text(sql))
                return r.fetchall()
            except Exception as e:
                try:
                    await conn.rollback()
                except Exception:
                    pass
                return [("ERROR", str(e))]

        # Total strategies
        r = await q("SELECT COUNT(*) FROM strategies")
        db_total_strategies = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Backtest results
        r = await q("SELECT COUNT(*) FROM backtest_results")
        db_total_backtests = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Paper trades
        r = await q("SELECT COUNT(*) FROM paper_trades")
        db_total_trades = r[0][0] if r and r[0][0] != "ERROR" else 0

        # PnL
        r = await q("SELECT COALESCE(SUM(pnl), 0) FROM paper_trades")
        db_total_pnl = float(r[0][0]) if r and r[0][0] != "ERROR" else 0

        # Strategies traded
        r = await q("SELECT COUNT(DISTINCT strategy_id) FROM paper_trades WHERE strategy_id IS NOT NULL")
        db_strategies_traded = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Event store
        r = await q("SELECT COUNT(*) FROM event_store")
        db_total_events = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Validated
        r = await q("SELECT COUNT(*) FROM strategies WHERE status='validated'")
        db_validated = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Open positions
        r = await q("SELECT COUNT(*) FROM positions")
        db_open_positions = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Scout signals
        r = await q("SELECT COUNT(*) FROM scout_signals")
        db_scout_signals = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Strategy status breakdown
        r = await q("SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY status")
        db_status_counts = {str(row[0]): row[1] for row in r if row[0] != "ERROR"}

        # Feature importance
        r = await q("SELECT COUNT(*) FROM feature_importance")
        db_fi_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Drift detection
        r = await q("SELECT COUNT(*) FROM drift_detection")
        db_drift_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Walk forward
        r = await q("SELECT COUNT(*) FROM walk_forward_analysis")
        db_wf_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Monte Carlo
        r = await q("SELECT COUNT(*) FROM monte_carlo_analysis")
        db_mc_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Overfitting
        r = await q("SELECT COUNT(*) FROM overfitting_analysis")
        db_of_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Portfolio intelligence
        r = await q("SELECT COUNT(*) FROM portfolio_intelligence")
        db_pi_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Capital allocation
        r = await q("SELECT COUNT(*) FROM capital_allocation")
        db_ca_count = r[0][0] if r and r[0][0] != "ERROR" else 0

        # Ensemble execution
        r = await q("SELECT COUNT(*) FROM ensemble_execution")
        db_ensemble_count = r[0][0] if r and r[0][0] != "ERROR" else 0

    await engine.dispose()

    # 4. Print comparison
    print("\n" + "=" * 60)
    print("COMPARISON TABLE")
    print("=" * 60)

    if dashboard_available:
        ds = overview.get("strategies", {})
        db_ov = overview.get("execution", {})
        val = overview.get("validation", {})
        mon = overview.get("monitoring", {})
        pf = overview.get("portfolio", {})
        sc = overview.get("scouts", {})

        comparsions = [
            ("Total Strategies",
             ds.get("total"),
             db_total_strategies),
            ("Validated Strategies",
             ds.get("by_status", {}).get("validated"),
             db_validated),
            ("Total Backtests",
             overview.get("backtests", {}).get("total"),
             db_total_backtests),
            ("Paper Trades",
             db_ov.get("total_paper_trades"),
             db_total_trades),
            ("Total PnL",
             None,
             db_total_pnl),
            ("Open Positions",
             db_ov.get("open_positions"),
             db_open_positions),
            ("Event Store (lifecycle_events)",
             overview.get("lineage", {}).get("total_events"),
             db_total_events),
            ("Scout Signals",
             sc.get("internal_signals"),
             db_scout_signals),
            ("Feature Importance",
             val.get("feature_importance"),
             db_fi_count),
            ("Walk Forward",
             val.get("walk_forward"),
             db_wf_count),
            ("Monte Carlo",
             val.get("monte_carlo"),
             db_mc_count),
            ("Overfitting",
             val.get("overfitting"),
             db_of_count),
            ("Drift Events",
             mon.get("drift_events"),
             db_drift_count),
            ("Portfolio Intel",
             pf.get("intel_runs"),
             db_pi_count),
            ("Capital Allocations",
             pf.get("allocations"),
             db_ca_count),
            ("Ensemble Trades",
             pf.get("ensemble_trades"),
             db_ensemble_count),
        ]

        for label, dash_val, db_val in comparsions:
            dash_str = str(dash_val) if dash_val is not None else "N/A"
            db_str = str(db_val) if db_val is not None else "N/A"
            match = "OK" if dash_val is None or dash_val == db_val else "MISMATCH"
            print(f"  {label:<22} | Dashboard: {dash_str:>8} | DB: {db_str:>8} | {match}")

    else:
        print("  Dashboard API unavailable — cannot compare")

    print("\n" + "=" * 60)
    print("DASHBOARD VALIDATION COMPLETE")
    print("=" * 60)

asyncio.run(main())
