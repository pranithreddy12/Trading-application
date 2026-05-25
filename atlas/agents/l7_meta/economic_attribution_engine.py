"""
economic_attribution_engine.py — Phase 26E

Closes the causal attribution loop:

  scout → ideator → mutation → validation → execution → PnL

For every strategy that passed through the organism with scout influence,
this engine measures the outcome (Sharpe contribution, survival rate,
PnL contribution) and writes it back into scout_economic_attribution.

This data is then consumed by SourceReliabilityEngine to evolve
dynamic trust scores based on actual economic outcomes.

ADVISORY ONLY — reads and writes attribution data, never trades.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class EconomicAttributionEngine(BaseAgent):
    """L7 Meta Agent — Closes the scout → outcome attribution loop.
    
    Every 15 minutes, scans recently validated/failed strategies that
    have scout_influence records and writes back economic outcomes.
    """

    name = "EconomicAttributionEngine"
    agent_type = "economic_attribution"
    layer = "L7"

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client,
                         advisory_only=True)
        self.db = db_client
        self._run_interval = 900  # Every 15 minutes

    async def run(self):
        logger.info(f"{self.name}: Starting economic attribution loop")
        while self.status == "running":
            try:
                await self._attribution_cycle()
            except Exception as e:
                logger.error(f"{self.name}: Attribution cycle error: {e}", exc_info=True)

            for _ in range(self._run_interval // 10):
                await asyncio.sleep(10)
                if self.status != "running":
                    return

    async def _attribution_cycle(self):
        """Scan for scout-influenced strategies with validation outcomes."""
        # Step 1: Find recently validated strategies that have scout influence events
        attributed = await self._find_attributable_strategies()
        if not attributed:
            logger.debug(f"{self.name}: No new attributable strategies found")
            return

        # Step 2: For each, compute contribution and persist attribution record
        n_attributed = 0
        for record in attributed:
            try:
                await self._compute_and_persist_attribution(record)
                n_attributed += 1
            except Exception as e:
                logger.debug(f"{self.name}: Attribution error for {record.get('strategy_id')}: {e}")

        logger.info(f"{self.name}: Attributed {n_attributed}/{len(attributed)} scout-influenced strategies")

        # Step 3: Propagate attribution scores to SourceReliabilityEngine trust
        await self._propagate_trust_updates()

    async def _find_attributable_strategies(self) -> list[dict]:
        """Find scout-influenced strategies that now have backtest results."""
        async with self.db.engine.connect() as conn:
            # Join strategies with scout influence and backtest results
            r = await conn.execute(text("""
                SELECT
                    sil.source_scout,
                    sil.influence_type,
                    sil.target_agent,
                    sil.influence_metric,
                    sil.delta,
                    sil.regime_context,
                    sil.entropy_context,
                    s.id as strategy_id,
                    s.name as strategy_name,
                    br.short_window_score,
                    br.max_drawdown,
                    br.total_return,
                    br.win_rate,
                    s.status,
                    sil.created_at
                FROM scout_influence_log sil
                JOIN strategies s ON s.author_agent = sil.target_agent
                LEFT JOIN LATERAL (
                    SELECT short_window_score, max_drawdown,
                           (results->>'total_return')::numeric as total_return, win_rate, composite_fitness_score, sharpe
                    FROM backtest_results
                    WHERE strategy_id = s.id
                    ORDER BY start_date DESC LIMIT 1
                ) br ON TRUE
                WHERE sil.created_at > NOW() - INTERVAL '4 hours'
                  AND s.created_at > NOW() - INTERVAL '4 hours'
                  AND s.status IN ('validated', 'live', 'failed_validation',
                                   'repair_candidate', 'promoted')
                  AND br.short_window_score IS NOT NULL
                  -- Avoid re-attributing already processed pairs
                  AND NOT EXISTS (
                      SELECT 1 FROM scout_economic_attribution sea
                      WHERE sea.strategy_id = s.id::text
                        AND sea.source_scout = sil.source_scout
                  )
                ORDER BY sil.created_at DESC
                LIMIT 100
            """))
            return [
                {
                    "source_scout": row[0],
                    "influence_type": row[1],
                    "target_agent": row[2],
                    "influence_metric": row[3],
                    "delta": float(row[4] or 0),
                    "regime_context": row[5] or "",
                    "entropy_context": float(row[6] or 0),
                    "strategy_id": str(row[7]),
                    "strategy_name": str(row[8] or ""),
                    "sharpe_score": float(row[9] or 0),
                    "max_drawdown": float(row[10] or 0),
                    "total_return": float(row[11] or 0),
                    "win_rate": float(row[12] or 0),
                    "composite_fitness_score": float(row[14] if len(row) > 14 and row[14] is not None else row[9] or 0),
                    "status": str(row[13] or ""),
                }
                for row in r.fetchall()
            ]

    async def _compute_and_persist_attribution(self, record: dict) -> None:
        """Compute economic contributions from a scout influence record."""
        survived = record["status"] in ("validated", "live", "promoted")
        sharpe = record["sharpe_score"]
        drawdown = record["max_drawdown"]
        pnl = record["total_return"]
        win_rate = record["win_rate"]

        # Attribution weight: how much did scout delta contribute?
        # Higher delta = stronger influence = higher weight in attribution
        abs_delta = abs(record["delta"])
        attribution_weight = min(1.0, abs_delta * 2.0)  # Normalize

        # Phase 28D: Economic Fitness Attribution (using composite_fitness_score)
        fitness = record["composite_fitness_score"]
        
        # Contribution: positive if survived, penalized if failed
        sharpe_contribution = fitness * attribution_weight if survived else -0.5 * attribution_weight

        await self.db.log_economic_attribution(
            source_scout=record["source_scout"],
            influence_type=record["influence_type"],
            target_agent=record["target_agent"],
            strategy_id=record["strategy_id"],
            strategy_name=record["strategy_name"],
            sharpe_contribution=sharpe_contribution,
            drawdown_contribution=drawdown * attribution_weight,
            pnl_contribution=pnl * attribution_weight,
            win_rate_contribution=win_rate * attribution_weight,
            attribution_weight=attribution_weight,
            survived_validation=survived,
            regime_at_time=record["regime_context"],
            entropy_at_time=record["entropy_context"],
            metadata={
                "raw_sharpe": sharpe,
                "raw_drawdown": drawdown,
                "influence_delta": record["delta"],
                "influence_metric": record["influence_metric"],
            }
        )

    async def _propagate_trust_updates(self) -> None:
        """Update source_performance_log based on economic attribution outcomes.
        
        Sources that contributed to validated strategies gain trust.
        Sources that contributed to failing strategies lose trust.
        """
        summary = await self.db.get_economic_attribution_summary(hours=48)
        for row in summary:
            source = row["source_scout"]
            n_strats = row["n_strategies"]
            n_survived = row["n_survived_validation"]
            avg_sharpe = row["avg_sharpe_contribution"]

            survival_rate = n_survived / max(1, n_strats)
            # Trust delta: +/- 0.1 based on survival and Sharpe
            trust_delta = (survival_rate - 0.5) * 0.2 + max(-0.1, min(0.1, avg_sharpe * 0.05))

            try:
                async with self.db.engine.begin() as conn:
                    await conn.execute(text("""
                        UPDATE source_performance_log
                        SET dynamic_trust_score = GREATEST(0.0, LEAST(1.0,
                                dynamic_trust_score + :delta)),
                            updated_at = NOW()
                        WHERE source = :source
                    """), {"delta": round(trust_delta, 4), "source": source})

                logger.info(
                    f"{self.name}: Trust update for {source}: "
                    f"delta={trust_delta:+.4f} "
                    f"(survival={survival_rate:.2f}, sharpe_contrib={avg_sharpe:.4f})"
                )
            except Exception as e:
                logger.debug(f"{self.name}: Trust update failed for {source}: {e}")
