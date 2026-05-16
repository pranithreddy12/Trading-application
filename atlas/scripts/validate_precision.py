"""
atlas/scripts/validate_precision.py

Validates numerical precision in TimescaleDB tables after precision migration.
Run after migration_001_precision_rounding.sql has been applied.

Usage:
    python -m atlas.scripts.validate_precision

Expected precision:
    market_data_l1:  OHLC → 4dp, volume(crypto) → 6dp, volume(equity) → 4dp
    market_data_l2:  spread/mid_price → 6dp
    order_flow:      price → 6dp, size → 4dp
    features:        returns/log_returns → 8dp, others → 6dp
"""

import asyncio
import json
import sys
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import text
from loguru import logger

from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings


def _excess_precision(val, max_dp: int) -> int:
    """Return how many extra decimal digits beyond max_dp exist."""
    if val is None:
        return 0
    try:
        d = Decimal(str(val))
        if d == d.to_integral():
            return 0
        # count decimal places
        _, _, exp = d.as_tuple()
        actual_dp = -exp
        return max(0, actual_dp - max_dp)
    except Exception:
        return 0


async def check_table(
    db: TimescaleClient,
    label: str,
    query: str,
    checks: list[dict],
    sample_limit: int = 100,
) -> dict:
    """Run precision checks on a sample of rows from a table."""
    logger.info(f"Checking {label}...")
    async with db.engine.connect() as conn:
        rows = (await conn.execute(text(query + f" LIMIT {sample_limit}"))).fetchall()

    results = {"table": label, "rows_sampled": len(rows), "columns": {}}
    for check in checks:
        col = check["name"]
        max_dp = check["max_dp"]
        violations = 0
        max_excess = 0
        for row in rows:
            val = getattr(row, col, None) if hasattr(row, col) else None
            if val is None:
                continue
            excess = _excess_precision(val, max_dp)
            if excess > 0:
                violations += 1
                max_excess = max(max_excess, excess)
        results["columns"][col] = {
            "max_allowed_dp": max_dp,
            "violations": violations,
            "max_excess_dp": max_excess,
        }
        status = "PASS" if violations == 0 else f"FAIL ({violations} violations)"
        logger.info(f"  {col}: max_dp={max_dp} → {status}")

    return results


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    logger.info("Connected to TimescaleDB")

    all_results = []

    # ── market_data_l1 ──────────────────────────────────────────────
    r = await check_table(
        db,
        "market_data_l1",
        "SELECT open, high, low, close, volume, asset_class FROM market_data_l1",
        [
            {"name": "open", "max_dp": 4},
            {"name": "high", "max_dp": 4},
            {"name": "low", "max_dp": 4},
            {"name": "close", "max_dp": 4},
            {"name": "volume", "max_dp": 6},
        ],
    )
    all_results.append(r)

    # ── market_data_l2 ──────────────────────────────────────────────
    r = await check_table(
        db,
        "market_data_l2",
        "SELECT spread, mid_price FROM market_data_l2",
        [
            {"name": "spread", "max_dp": 6},
            {"name": "mid_price", "max_dp": 6},
        ],
    )
    all_results.append(r)

    # ── order_flow ──────────────────────────────────────────────────
    r = await check_table(
        db,
        "order_flow",
        "SELECT price, size FROM order_flow",
        [
            {"name": "price", "max_dp": 6},
            {"name": "size", "max_dp": 4},
        ],
    )
    all_results.append(r)

    # ── features ────────────────────────────────────────────────────
    logger.info("Checking features (by feature_name)...")
    async with db.engine.connect() as conn:
        rows = (
            await conn.execute(
                text("""
                    SELECT feature_name, value
                    FROM features
                    ORDER BY random()
                    LIMIT 1000
                """)
            )
        ).fetchall()

    feature_results = {
        "returns": {"violations": 0, "total": 0},
        "log_returns": {"violations": 0, "total": 0},
        "other": {"violations": 0, "total": 0},
    }
    for row in rows:
        name = row.feature_name
        val = row.value
        if name in ("returns", "log_returns"):
            max_dp = 8
            key = name
        else:
            max_dp = 6
            key = "other"
        feature_results[key]["total"] += 1
        excess = _excess_precision(val, max_dp)
        if excess > 0:
            feature_results[key]["violations"] += 1

    for key, res in feature_results.items():
        status = (
            "PASS"
            if res["violations"] == 0
            else f"FAIL ({res['violations']}/{res['total']})"
        )
        logger.info(f"  features.{key}: {status}")
    all_results.append(
        {
            "table": "features",
            "feature_precision": feature_results,
        }
    )

    # ── Summary ─────────────────────────────────────────────────────
    logger.info("=" * 60)
    all_pass = True
    for res in all_results:
        for col, info in res.get("columns", {}).items():
            if info["violations"] > 0:
                all_pass = False
    for res in all_results:
        for key, info in res.get("feature_precision", {}).items():
            if info.get("violations", 0) > 0:
                all_pass = False

    if all_pass:
        logger.success("PRECISION VALIDATION: ALL PASS")
    else:
        logger.error("PRECISION VALIDATION: SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
