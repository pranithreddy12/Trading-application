"""P6 T8 — Reconciliation export command.

READ-ONLY. Builds the four legacy-vs-shadow reports and exports them as CSV +
prints a console summary. Modifies nothing.

Usage:
  python -m atlas.scripts.run_reconciliation [--out scratch/reconciliation]
"""
import argparse
import asyncio
import csv
import os

from loguru import logger

from atlas.config.settings import settings
from atlas.core.reconciliation import (
    ReconciliationService,
    build_console_report,
    build_csv_tables,
)
from atlas.data.storage.timescale_client import TimescaleClient


async def main() -> None:
    ap = argparse.ArgumentParser(description="Reconcile legacy vs v1 shadow outputs (read-only).")
    ap.add_argument("--out", default="scratch/reconciliation", help="CSV output directory")
    ap.add_argument("--top", type=int, default=10, help="top-N strategies in console fitness ranking")
    args = ap.parse_args()

    db = TimescaleClient(settings.database_url)
    await db.connect()

    report = await ReconciliationService(db).generate()

    # console summary
    print(build_console_report(report, top_n=args.top))

    # CSV export
    os.makedirs(args.out, exist_ok=True)
    tables = build_csv_tables(report)
    for fname, (header, rows) in tables.items():
        path = os.path.join(args.out, fname)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        logger.info(f"wrote {path} ({len(rows)} rows)")


if __name__ == "__main__":
    asyncio.run(main())
