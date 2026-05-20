"""
cost_stress_tester.py — Phase 11: Transaction Cost Stress Testing.

Simulates strategy performance under elevated transaction costs:
  - 2x cost: moderate stress
  - 3x cost: high stress
  - 5x cost: extreme stress

Measures:
  - Profit factor degradation curve
  - Expectancy degradation (return per trade)
  - Execution survivability (survive at 5x cost?)

Rejects:
  - Strategies that cannot survive 3x realistic costs
  - Hyperfragile scalpers (zero edge after fees)
"""

import asyncio
import json
import uuid
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from atlas.core.agent_base import BaseAgent


class CostStressTester(BaseAgent):
    """
    Cost Stress Tester — evaluates strategy fragility under elevated transaction costs.

    Configuration:
      - base_cost_bps: baseline round-trip cost in bps (default 15)
      - cost_multipliers: list of multipliers to test (default [2.0, 3.0, 5.0])
      - min_survive_multiplier: max multiplier that strategy must survive (default 3.0)
    """

    name = "CostStressTester"
    agent_type = "cost_stress_tester"
    layer = "L3"

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        base_cost_bps: float = 15.0,
        cost_multipliers: Optional[list[float]] = None,
        min_survive_multiplier: float = 3.0,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.base_cost_bps = base_cost_bps
        self.multipliers = cost_multipliers or [1.0, 2.0, 3.0, 5.0]
        self.min_survive = min_survive_multiplier

    async def run(self):
        logger.info(f"{self.name}: idle — triggered on demand by ValidatorAgent")
        await asyncio.sleep(3600)

    async def stress_test(
        self,
        strategy_id: str,
        trades: list[dict],
        background_results: dict,
    ) -> dict:
        """
        Run cost stress test on a strategy's trade records.

        Each trade should have: entry_price, exit_price, side ('long'/'short').
        Returns cost survival metrics.
        """
        if not trades or len(trades) < 5:
            return self._empty_result("insufficient_trades")

        # Extract per-trade raw returns (before costs)
        raw_returns = []
        for trade in trades:
            entry = float(trade.get("entry_price", 0))
            exit_p = float(trade.get("exit_price", 0))
            side = trade.get("side", "long")
            if entry <= 0 or exit_p <= 0:
                continue
            ret = (exit_p - entry) / entry
            if side == "short":
                ret = -ret
            raw_returns.append(ret)

        raw_returns = np.array(raw_returns)
        if len(raw_returns) < 5:
            return self._empty_result("insufficient_valid_trades")

        cost_per_trade_bps = self.base_cost_bps / 10000  # convert bps to decimal

        multiplier_results = []
        for mult in self.multipliers:
            cost = cost_per_trade_bps * mult
            net_returns = raw_returns - cost
            gross_returns = raw_returns  # gross = raw

            pf_gross = self._profit_factor(gross_returns)
            pf_net = self._profit_factor(net_returns)
            total_net = float(np.sum(net_returns))
            avg_net = float(np.mean(net_returns))
            win_rate = float(np.mean(net_returns > 0))
            survived = total_net > 0 and pf_net >= 0.8

            multiplier_results.append({
                "multiplier": mult,
                "cost_bps": round(self.base_cost_bps * mult, 1),
                "total_return_net": round(total_net, 6),
                "avg_return_per_trade": round(avg_net, 6),
                "profit_factor_gross": round(pf_gross, 4),
                "profit_factor_net": round(pf_net, 4),
                "win_rate": round(win_rate, 4),
                "survived": survived,
            })

        # Determine maximum survivable multiplier
        max_survived = 1.0
        for mr in multiplier_results:
            if mr["survived"]:
                max_survived = mr["multiplier"]

        # PF degradation: PF at 1x vs PF at 5x
        pf_at_1x = next((mr["profit_factor_net"] for mr in multiplier_results if mr["multiplier"] == 1.0), 1.0)
        pf_at_5x = next((mr["profit_factor_net"] for mr in multiplier_results if mr["multiplier"] == 5.0), 0.0)
        pf_degradation = 1.0 - (pf_at_5x / pf_at_1x) if pf_at_1x > 0 else 1.0
        pf_degradation = min(1.0, max(0.0, pf_degradation))

        # Cost survival score [0, 1]: survives min_survive? partial credit for lower
        cost_survival_score = max_survived / max(self.multipliers)
        cost_survival_score = min(1.0, cost_survival_score)

        # Expectancy degradation
        exp_at_1x = next((mr["avg_return_per_trade"] for mr in multiplier_results if mr["multiplier"] == 1.0), 0.0)
        exp_at_5x = next((mr["avg_return_per_trade"] for mr in multiplier_results if mr["multiplier"] == 5.0), 0.0)
        exp_degradation = 1.0 - (exp_at_5x / exp_at_1x) if exp_at_1x > 0 else 1.0
        exp_degradation = min(1.0, max(0.0, exp_degradation))

        # Fragile scalper detection
        fragile_scalper = False
        base_pf = next((mr["profit_factor_net"] for mr in multiplier_results if mr["multiplier"] == 1.0), 0.0)
        if base_pf >= 1.2:
            # If PF collapses from 1.2+ to below 0.8 at 3x, it's fragile
            pf_at_3x = next((mr["profit_factor_net"] for mr in multiplier_results if mr["multiplier"] == 3.0), 0.0)
            if pf_at_3x < 0.8:
                fragile_scalper = True

        result = {
            "cost_survival_score": round(cost_survival_score, 4),
            "max_survivable_multiplier": max_survived,
            "profit_factor_degradation": round(pf_degradation, 4),
            "expectancy_degradation": round(exp_degradation, 4),
            "passes_min_survival": max_survived >= self.min_survive,
            "fragile_scalper_detected": fragile_scalper,
            "n_trades_input": len(raw_returns),
            "per_multiplier_results": multiplier_results,
        }

        await self._persist(strategy_id, result)
        return result

    def _profit_factor(self, returns: np.ndarray) -> float:
        wins = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        if losses == 0:
            return 10.0 if wins > 0 else 1.0
        return wins / losses

    def _empty_result(self, reason: str) -> dict:
        return {
            "cost_survival_score": 0.0,
            "max_survivable_multiplier": 0.0,
            "profit_factor_degradation": 1.0,
            "expectancy_degradation": 1.0,
            "passes_min_survival": False,
            "fragile_scalper_detected": False,
            "n_trades_input": 0,
            "per_multiplier_results": [],
            "error": reason,
        }

    async def _persist(self, strategy_id: str, result: dict) -> None:
        if not self.db:
            return
        try:
            await self.db._execute_insert(
                """
                INSERT INTO cost_stress_analysis
                    (id, strategy_id, cost_survival_score, max_survivable_multiplier,
                     profit_factor_degradation, expectancy_degradation,
                     passes_min_survival, fragile_scalper_detected, tested_at)
                VALUES
                    (:id, :sid, :css, :msm, :pfd, :ed, :pms, :fsd, NOW())
                ON CONFLICT (strategy_id) DO UPDATE SET
                    cost_survival_score = EXCLUDED.cost_survival_score,
                    passes_min_survival = EXCLUDED.passes_min_survival,
                    tested_at = NOW()
                """,
                {
                    "id": str(uuid.uuid4()),
                    "sid": strategy_id,
                    "css": result["cost_survival_score"],
                    "msm": result["max_survivable_multiplier"],
                    "pfd": result["profit_factor_degradation"],
                    "ed": result["expectancy_degradation"],
                    "pms": result["passes_min_survival"],
                    "fsd": result["fragile_scalper_detected"],
                },
            )
        except Exception as e:
            logger.warning(f"{self.name}: persist failed for {strategy_id}: {e}")
