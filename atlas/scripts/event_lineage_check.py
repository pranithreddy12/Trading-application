"""
Event Lineage Check — CLI tool for querying full lifecycle traceability.

Trace a strategy through: Ideator → Coder → Backtest → Pattern → Brief

Usage:
    python scripts/event_lineage_check.py --trace-id <trace_id>
    python scripts/event_lineage_check.py --strategy-id <strategy_id>
    python scripts/event_lineage_check.py --list-traces
    python scripts/event_lineage_check.py --list-traces --json
    python scripts/event_lineage_check.py --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ATLAS Event Lineage Check")
    parser.add_argument(
        "--trace-id", type=str, default=None, help="Trace ID to inspect"
    )
    parser.add_argument(
        "--strategy-id", type=str, default=None, help="Strategy ID to trace"
    )
    parser.add_argument("--list-traces", action="store_true", help="List recent traces")
    parser.add_argument("--stats", action="store_true", help="Show lineage statistics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=20, help="Limit results")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    import asyncio
    from atlas.config.settings import settings
    from atlas.data.storage.timescale_client import TimescaleClient
    from atlas.core.event_lineage import EventLineageClient

    async def run():
        db = TimescaleClient(settings.database_url)
        await db.connect()
        lineage = EventLineageClient(db)

        if args.trace_id:
            events = await lineage.get_lineage(args.trace_id)
            if not events:
                print(f"No events found for trace_id: {args.trace_id}")
                return
            summary = await lineage.get_lineage_summary(args.trace_id)
            if args.json:
                print(json.dumps(summary, indent=2, default=str))
            else:
                print(f"Lineage: {args.trace_id}")
                print(f"  Strategy: {summary['strategy_id']}")
                print(f"  Stages: {summary['stages_completed']}")
                print(f"  Status: {summary['status']}")
                print(f"  Period: {summary['first_event']} → {summary['last_event']}")
                print()
                for s in summary["stages"]:
                    meta_str = ""
                    if s["metadata"]:
                        meta_str = f" | {json.dumps(s['metadata'])}"
                    print(
                        f"  [{s['stage']:>8}] {s['status']:>10} by {s['actor']}{meta_str}"
                    )
                    print(f"             at {s['time']}")

        elif args.strategy_id:
            trace_id = await lineage.get_trace_by_strategy(args.strategy_id)
            if not trace_id:
                print(f"No trace found for strategy_id: {args.strategy_id}")
                return
            print(f"Strategy {args.strategy_id} → Trace: {trace_id}")
            events = await lineage.get_lineage(trace_id)
            summary = await lineage.get_lineage_summary(trace_id)
            if args.json:
                print(json.dumps(summary, indent=2, default=str))
            else:
                for s in summary["stages"]:
                    print(
                        f"  [{s['stage']:>8}] {s['status']:>10} by {s['actor']} at {s['time']}"
                    )

        elif args.list_traces:
            traces = await lineage.get_all_traces(limit=args.limit)
            if args.json:
                print(json.dumps(traces, indent=2, default=str))
            else:
                print(f"Recent traces ({len(traces)}):")
                for t in traces:
                    print(
                        f"  {t['trace_id']} — {t['event_count']} events, {t['strategy_count']} strategies"
                    )
                    print(f"             {t['first_event']} → {t['last_event']}")

        elif args.stats:
            traces = await lineage.get_all_traces(limit=1000)
            from sqlalchemy.sql import text

            async with db.engine.connect() as conn:
                r = await conn.execute(text("SELECT COUNT(*) FROM lifecycle_events"))
                total_events = r.scalar() or 0
                r = await conn.execute(
                    text("SELECT COUNT(DISTINCT trace_id) FROM lifecycle_events")
                )
                total_traces = r.scalar() or 0
                r = await conn.execute(
                    text(
                        "SELECT COUNT(DISTINCT strategy_id) FROM lifecycle_events WHERE strategy_id IS NOT NULL"
                    )
                )
                total_strategies = r.scalar() or 0
                r = await conn.execute(
                    text("""
                    SELECT stage, COUNT(*) as cnt FROM lifecycle_events
                    GROUP BY stage ORDER BY cnt DESC
                """)
                )
                stage_counts = {row[0]: row[1] for row in r.fetchall()}
                r = await conn.execute(
                    text("""
                    SELECT status, COUNT(*) as cnt FROM lifecycle_events
                    GROUP BY status ORDER BY cnt DESC
                """)
                )
                status_counts = {row[0]: row[1] for row in r.fetchall()}

            stats = {
                "total_events": total_events,
                "total_traces": total_traces,
                "total_strategies_tracked": total_strategies,
                "stages": stage_counts,
                "statuses": status_counts,
            }
            if args.json:
                print(json.dumps(stats, indent=2, default=str))
            else:
                print("Event Lineage Statistics:")
                print(f"  Total events: {total_events}")
                print(f"  Total traces: {total_traces}")
                print(f"  Strategies tracked: {total_strategies}")
                print(f"  Stages: {stage_counts}")
                print(f"  Statuses: {status_counts}")
        else:
            parser.print_help()

    asyncio.run(run())


if __name__ == "__main__":
    main()
