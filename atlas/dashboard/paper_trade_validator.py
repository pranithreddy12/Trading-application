"""
paper_trade_validator.py — Paper Trade Data Validation Utility.

Provides a validation report for the dashboard:
  - Total, closed, open, winning, losing, flat trades
  - Total realized PnL
  - Duplicate trade pair detection
  - Win rate calculation

Can be called as a standalone script or integrated into the dashboard.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy.sql import text


async def compute_paper_trade_validation_report(db) -> dict[str, Any]:
    """Compute a comprehensive validation report from paper_trades.

    Args:
        db: TimescaleClient instance with an active connection.

    Returns:
        Dict with total_trades, closed_trades, open_trades, winning_trades,
        losing_trades, flat_trades, total_pnl, win_rate_pct, duplicate_pairs.
    """
    try:
        async with db.engine.connect() as conn:
            # Total counts
            r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
            total_trades = r.scalar() or 0

            r = await conn.execute(
                text("""
                SELECT status, COUNT(*) as cnt
                FROM paper_trades
                GROUP BY status
                """)
            )
            status_counts = {str(row[0]): row[1] for row in r.fetchall()}
            closed = status_counts.get("filled", 0) + status_counts.get("closed", 0)
            open_trades = status_counts.get("open", 0)

            # Win/Loss breakdown
            r = await conn.execute(
                text("""
                SELECT
                    COUNT(*) as total_filled,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing,
                    SUM(CASE WHEN pnl = 0 OR pnl IS NULL THEN 1 ELSE 0 END) as flat,
                    COALESCE(SUM(pnl), 0) as total_pnl
                FROM paper_trades
                WHERE status IN ('filled', 'closed')
                """)
            )
            row = r.fetchone()
            total_filled = int(row[0]) if row and row[0] else 0
            winning = int(row[1]) if row and row[1] else 0
            losing = int(row[2]) if row and row[2] else 0
            flat = int(row[3]) if row and row[3] else 0
            total_pnl = float(row[4]) if row and row[4] else 0.0

            # Duplicate detection: same strategy_id + symbol + side + quantity
            r = await conn.execute(
                text("""
                SELECT strategy_id, symbol, side, quantity, COUNT(*) as dup_count
                FROM paper_trades
                GROUP BY strategy_id, symbol, side, quantity
                HAVING COUNT(*) > 1
                ORDER BY dup_count DESC
                LIMIT 20
                """)
            )
            duplicates = [
                {
                    "strategy_id": str(row[0]),
                    "symbol": row[1],
                    "side": row[2],
                    "quantity": float(row[3]) if row[3] else 0,
                    "count": row[4],
                }
                for row in r.fetchall()
            ]

        report = {
            "total_trades": total_trades,
            "closed_trades": closed,
            "open_trades": open_trades,
            "winning_trades": winning,
            "losing_trades": losing,
            "flat_trades": flat,
            "total_pnl": round(total_pnl, 2),
            "win_rate_pct": round(winning / total_filled * 100, 1)
            if total_filled > 0
            else 0.0,
            "duplicate_pairs": duplicates,
            "n_duplicates": len(duplicates),
        }

        logger.info(
            f"Paper trade validation: {report['total_trades']} total, "
            f"{report['closed_trades']} closed, ${report['total_pnl']} PnL, "
            f"{report['n_duplicates']} duplicate pairs"
        )
        return report

    except Exception as exc:
        logger.error(f"Paper trade validation failed: {exc}")
        return {
            "total_trades": 0,
            "closed_trades": 0,
            "open_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "flat_trades": 0,
            "total_pnl": 0.0,
            "win_rate_pct": 0.0,
            "duplicate_pairs": [],
            "n_duplicates": 0,
            "error": str(exc),
        }
