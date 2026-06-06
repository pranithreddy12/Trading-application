import math
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger
from sqlalchemy import text


class PaperPerformanceMetrics:
    """
    Computes paper trading performance metrics for a single strategy
    and persists them to the strategy_performance table.
    """

    def __init__(self, db_client):
        self.db = db_client

    async def compute_and_store(self, strategy_id: str) -> dict:
        metrics = await self._compute_metrics(strategy_id)
        if metrics:
            await self._store(strategy_id, metrics)
            qualified = await self.qualify_strategy_for_promotion(strategy_id)
            metrics["is_qualified"] = qualified
        return metrics

    async def compute_all(self) -> list[dict]:
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("SELECT DISTINCT strategy_id FROM paper_trades")
            )
            sids = [str(row[0]) for row in r.fetchall()]

        results = []
        for sid in sids:
            try:
                m = await self.compute_and_store(sid)
                if m:
                    results.append(m)
            except Exception as e:
                logger.error(f"Metrics failed for {sid}: {e}")
        return results

    async def _compute_metrics(self, strategy_id: str) -> Optional[dict]:
        async with self.db.engine.connect() as conn:
            # All closed/filled trades for this strategy
            r = await conn.execute(
                text("""
                    SELECT pnl, time, side, quantity, fill_price, status
                    FROM paper_trades
                    WHERE strategy_id = :sid
                    ORDER BY time ASC
                """),
                {"sid": strategy_id},
            )
            rows = r.fetchall()
            if not rows:
                return None

            total_trades = len(rows)
            closed = [
                (float(row[0]), row[1])
                for row in rows
                if row[0] is not None and row[5] in ("filled", "closed")
            ]
            all_pnls = [pnl for pnl, _ in closed]

            # Total realized PnL
            realized_pnl = sum(all_pnls) if all_pnls else 0.0

            # Unrealized PnL (open positions)
            open_rows = [row for row in rows if row[5] == "open"]
            unrealized_pnl = (
                sum(
                    float(row[4] or 0) - float(row[3] or 0) * float(row[2] or 0)
                    for row in open_rows
                )
                if open_rows
                else 0.0
            )

            # Win rate
            winning = sum(1 for p in all_pnls if p > 0)
            losing = sum(1 for p in all_pnls if p < 0)
            win_rate = winning / total_trades if total_trades > 0 else 0.0

            # Profit factor
            gross_profit = sum(p for p in all_pnls if p > 0)
            gross_loss = abs(sum(p for p in all_pnls if p < 0))
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else (gross_profit if gross_profit > 0 else 0.0)
            )

            # Average trade
            avg_trade_pnl = realized_pnl / total_trades if total_trades > 0 else 0.0

            # Max drawdown (from cumulative PnL)
            cum_pnl = 0.0
            peak = 0.0
            max_dd = 0.0
            for pnl, _ in closed:
                cum_pnl += pnl
                if cum_pnl > peak:
                    peak = cum_pnl
                dd = (peak - cum_pnl) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd

            # Time-based return windows
            now = datetime.now(timezone.utc)

            def _return_pct(trades, since):
                relevant = [
                    (float(r[0]), float(r[3] or 0) * float(r[4] or 0))
                    for r in trades
                    if r[0] is not None
                    and r[1] >= since
                    and r[5] in ("filled", "closed")
                ]
                if not relevant:
                    return 0.0
                total_pnl = sum(r[0] for r in relevant)
                total_exposure = sum(abs(r[1]) for r in relevant)
                if total_exposure == 0:
                    return 0.0
                return 100.0 * total_pnl / total_exposure

            daily_return_pct = _return_pct(rows, now - timedelta(days=1))
            weekly_return_pct = _return_pct(rows, now - timedelta(days=7))
            monthly_return_pct = _return_pct(rows, now - timedelta(days=30))
            rolling_30d_return_pct = monthly_return_pct
            total_return_pct = _return_pct(
                rows, datetime.min.replace(tzinfo=timezone.utc)
            )

            # Sharpe ratio (daily returns approximation)
            if len(all_pnls) >= 2:
                avg_pnl = sum(all_pnls) / len(all_pnls)
                variance = sum((p - avg_pnl) ** 2 for p in all_pnls) / (
                    len(all_pnls) - 1
                )
                std_dev = math.sqrt(variance) if variance > 0 else 0.0
                sharpe_ratio = (
                    (avg_pnl / std_dev) * math.sqrt(252) if std_dev > 0 else 0.0
                )
            else:
                sharpe_ratio = 0.0

            return {
                "daily_return_pct": round(daily_return_pct, 4),
                "weekly_return_pct": round(weekly_return_pct, 4),
                "monthly_return_pct": round(monthly_return_pct, 4),
                "rolling_30d_return_pct": round(rolling_30d_return_pct, 4),
                "total_return_pct": round(total_return_pct, 4),
                "realized_pnl": round(realized_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "profit_factor": round(profit_factor, 4),
                "win_rate": round(win_rate, 4),
                "max_drawdown_pct": round(max_dd * 100, 4),
                "avg_trade_pnl": round(avg_trade_pnl, 2),
                "total_trades": total_trades,
            }

    async def _store(self, strategy_id: str, metrics: dict) -> None:
        async with self.db.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO strategy_performance (
                        strategy_id, computed_at,
                        daily_return_pct, weekly_return_pct, monthly_return_pct,
                        rolling_30d_return_pct, total_return_pct,
                        realized_pnl, unrealized_pnl,
                        sharpe_ratio, profit_factor, win_rate, max_drawdown_pct,
                        avg_trade_pnl, total_trades
                    ) VALUES (
                        :sid, NOW(),
                        :dr, :wr, :mr,
                        :r30, :tr,
                        :rp, :up,
                        :sh, :pf, :wr2, :mdd,
                        :avg, :tt
                    )
                    ON CONFLICT (strategy_id)
                    DO UPDATE SET
                        computed_at = NOW(),
                        daily_return_pct = EXCLUDED.daily_return_pct,
                        weekly_return_pct = EXCLUDED.weekly_return_pct,
                        monthly_return_pct = EXCLUDED.monthly_return_pct,
                        rolling_30d_return_pct = EXCLUDED.rolling_30d_return_pct,
                        total_return_pct = EXCLUDED.total_return_pct,
                        realized_pnl = EXCLUDED.realized_pnl,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        sharpe_ratio = EXCLUDED.sharpe_ratio,
                        profit_factor = EXCLUDED.profit_factor,
                        win_rate = EXCLUDED.win_rate,
                        max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                        avg_trade_pnl = EXCLUDED.avg_trade_pnl,
                        total_trades = EXCLUDED.total_trades
                """),
                {
                    "sid": strategy_id,
                    "dr": metrics["daily_return_pct"],
                    "wr": metrics["weekly_return_pct"],
                    "mr": metrics["monthly_return_pct"],
                    "r30": metrics["rolling_30d_return_pct"],
                    "tr": metrics["total_return_pct"],
                    "rp": metrics["realized_pnl"],
                    "up": metrics["unrealized_pnl"],
                    "sh": metrics["sharpe_ratio"],
                    "pf": metrics["profit_factor"],
                    "wr2": metrics["win_rate"],
                    "mdd": metrics["max_drawdown_pct"],
                    "avg": metrics["avg_trade_pnl"],
                    "tt": metrics["total_trades"],
                },
            )

    async def qualify_strategy_for_promotion(self, strategy_id: str) -> dict:
        result = await self._check_qualification(strategy_id)
        await self._audit_qualification(strategy_id, result)
        await self._update_qualification_flag(strategy_id, result["passed"])
        return result

    async def _check_qualification(self, strategy_id: str) -> dict:
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT monthly_return_pct, sharpe_ratio, profit_factor,
                           max_drawdown_pct, total_trades
                    FROM strategy_performance
                    WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            if not row:
                return {"passed": False, "fail_reasons": ["No performance data"]}

            monthly_return_pct = float(row[0]) if row[0] is not None else 0.0
            sharpe_ratio = float(row[1]) if row[1] is not None else 0.0
            profit_factor = float(row[2]) if row[2] is not None else 0.0
            max_drawdown_pct = float(row[3]) if row[3] is not None else 100.0
            total_trades = int(row[4]) if row[4] is not None else 0

            fail_reasons = []
            if monthly_return_pct < 20:
                fail_reasons.append(f"Monthly return {monthly_return_pct:.2f}% < 20%")
            if sharpe_ratio < 1.5:
                fail_reasons.append(f"Sharpe {sharpe_ratio:.2f} < 1.5")
            if profit_factor < 1.3:
                fail_reasons.append(f"Profit factor {profit_factor:.2f} < 1.3")
            if max_drawdown_pct > 15:
                fail_reasons.append(f"Max drawdown {max_drawdown_pct:.2f}% > 15%")
            if total_trades < 30:
                fail_reasons.append(f"Trades {total_trades} < 30")

            passed = len(fail_reasons) == 0

            return {
                "passed": passed,
                "monthly_return_pct": monthly_return_pct,
                "sharpe_ratio": sharpe_ratio,
                "profit_factor": profit_factor,
                "max_drawdown_pct": max_drawdown_pct,
                "total_trades": total_trades,
                "fail_reasons": fail_reasons,
            }

    async def _audit_qualification(self, strategy_id: str, result: dict) -> None:
        async with self.db.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO strategy_promotion_audit (
                        strategy_id, result,
                        monthly_return_pct, sharpe_ratio, profit_factor,
                        max_drawdown_pct, total_trades, fail_reasons, details
                    ) VALUES (
                        :sid, :result,
                        :mr, :sh, :pf,
                        :mdd, :tt, :reasons, :details
                    )
                """),
                {
                    "sid": strategy_id,
                    "result": "PASS" if result["passed"] else "FAIL",
                    "mr": result["monthly_return_pct"],
                    "sh": result["sharpe_ratio"],
                    "pf": result["profit_factor"],
                    "mdd": result["max_drawdown_pct"],
                    "tt": result["total_trades"],
                    "reasons": str(result["fail_reasons"]),
                    "details": f"Qualification check at {datetime.now(timezone.utc).isoformat()}",
                },
            )

    async def _update_qualification_flag(self, strategy_id: str, passed: bool) -> None:
        async with self.db.engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE strategy_performance
                    SET is_qualified = :passed,
                        qualified_at = CASE WHEN :passed THEN NOW() ELSE qualified_at END
                    WHERE strategy_id = :sid
                """),
                {"sid": strategy_id, "passed": passed},
            )

    async def get_ranked(
        self, sort_by: str = "monthly_return_pct", limit: int = 20
    ) -> list[dict]:
        allowed_sorts = {
            "monthly_return_pct",
            "sharpe_ratio",
            "profit_factor",
            "win_rate",
            "total_return_pct",
            "realized_pnl",
        }
        sort_col = sort_by if sort_by in allowed_sorts else "monthly_return_pct"

        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text(f"""
                    SELECT sp.strategy_id, s.name,
                           sp.monthly_return_pct, sp.sharpe_ratio, sp.profit_factor,
                           sp.win_rate, sp.max_drawdown_pct, sp.total_trades,
                           sp.realized_pnl, sp.total_return_pct,
                           sp.is_qualified
                    FROM strategy_performance sp
                    JOIN strategies s ON s.id = sp.strategy_id
                    ORDER BY sp.{sort_col} DESC NULLS LAST
                    LIMIT :lim
                """),
                {"lim": limit},
            )
            return [
                {
                    "strategy_id": str(row[0]),
                    "name": str(row[1]),
                    "monthly_return_pct": float(row[2]) if row[2] is not None else 0.0,
                    "sharpe_ratio": float(row[3]) if row[3] is not None else 0.0,
                    "profit_factor": float(row[4]) if row[4] is not None else 0.0,
                    "win_rate": float(row[5]) if row[5] is not None else 0.0,
                    "max_drawdown_pct": float(row[6]) if row[6] is not None else 0.0,
                    "total_trades": int(row[7]) if row[7] is not None else 0,
                    "realized_pnl": float(row[8]) if row[8] is not None else 0.0,
                    "total_return_pct": float(row[9]) if row[9] is not None else 0.0,
                    "is_qualified": bool(row[10]) if row[10] is not None else False,
                }
                for row in r.fetchall()
            ]
