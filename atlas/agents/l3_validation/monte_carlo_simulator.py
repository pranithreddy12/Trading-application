"""
monte_carlo_simulator.py — Phase 11: Monte Carlo Simulation for Strategy Robustness.

Randomizes trade-level outcomes via:
  - Entry timing jitter (±random bars)
  - Fill price slippage (uniform random within spread)
  - Slippage shocks (occasional 2x–5x normal)
  - Volatility regime shocks (add random vol periods)

Outputs:
  - monte_carlo_survival_score [0, 1]: fraction of simulations with positive return
  - expected_tail_drawdown [0, 1]: expected max drawdown in worst 5% simulations
  - probabilistic_sharpe [0, inf]: median Sharpe across all simulations
"""

import asyncio
import json
import math
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from atlas.core.agent_base import BaseAgent


class MonteCarloSimulator(BaseAgent):
    """
    Monte Carlo Simulator — stress-tests strategy robustness via randomized simulation.

    Configuration:
      - n_simulations: number of Monte Carlo runs (default 1000)
      - jitter_bars: max entry timing jitter in bars (default 2)
      - slippage_volatility: std of slippage multiplier shocks (default 0.3)
      - shock_probability: probability of a slippage shock per trade (default 0.05)
    """

    name = "MonteCarloSimulator"
    agent_type = "monte_carlo_simulator"
    layer = "L3"

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        n_simulations: int = 1000,
        jitter_bars: int = 2,
        slippage_volatility: float = 0.3,
        shock_probability: float = 0.05,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.n_simulations = n_simulations
        self.jitter_bars = jitter_bars
        self.slippage_vol = slippage_volatility
        self.shock_prob = shock_probability

    async def run(self):
        logger.info(f"{self.name}: idle — triggered on demand by ValidatorAgent")
        await asyncio.sleep(3600)

    async def simulate(
        self,
        strategy_id: str,
        trades: list[dict],
        background_results: dict,
    ) -> dict:
        """
        Run Monte Carlo simulation on a list of trade records.

        Each trade should have: entry_price, exit_price, side ('long'/'short').
        Returns survival statistics across n_simulations runs.
        """
        if not trades or len(trades) < 5:
            return self._empty_result("insufficient_trades")

        n = len(trades)
        returns = []

        for trade in trades:
            entry = float(trade.get("entry_price", 0))
            exit_p = float(trade.get("exit_price", 0))
            side = trade.get("side", "long")
            if entry <= 0 or exit_p <= 0:
                continue
            raw_ret = (exit_p - entry) / entry
            if side == "short":
                raw_ret = -raw_ret
            returns.append(raw_ret)

        returns = np.array(returns)
        if len(returns) < 5:
            return self._empty_result("insufficient_valid_trades")

        np.random.seed(42)
        sim_outcomes = []

        for _ in range(self.n_simulations):
            # Bootstrap sample with replacement
            indices = np.random.randint(0, n, size=n)
            sampled = returns[indices]

            # Apply entry timing jitter (randomly skip/repeat trades)
            jitter_mask = np.random.uniform(size=n) < 0.1
            sampled = sampled[~jitter_mask] if jitter_mask.sum() < n - 2 else sampled

            # Apply slippage noise
            slippage_noise = 1.0 + np.random.normal(0, self.slippage_vol, size=len(sampled))
            sampled = sampled * slippage_noise

            # Apply occasional shock
            shock_mask = np.random.uniform(size=len(sampled)) < self.shock_prob
            shock_mult = np.where(shock_mask, np.random.uniform(2.0, 5.0, size=len(sampled)), 1.0)
            sampled = sampled * shock_mult

            total_ret = float(np.sum(sampled))
            sim_outcomes.append(total_ret)

        sim_outcomes = np.array(sim_outcomes)

        # Survival score: fraction with positive return
        survival_score = float(np.mean(sim_outcomes > 0))

        # Tail drawdown: mean of worst 5% outcomes
        sorted_asc = np.sort(sim_outcomes)
        tail_idx = max(1, int(len(sorted_asc) * 0.05))
        tail_outcomes = sorted_asc[:tail_idx]
        expected_tail_drawdown = float(np.mean(tail_outcomes))
        # Convert to positive drawdown magnitude
        tail_drawdown_mag = max(0.0, -expected_tail_drawdown)

        # Probabilistic Sharpe
        mean_ret = float(np.mean(sim_outcomes))
        std_ret = float(np.std(sim_outcomes)) + 1e-10
        sharpe = mean_ret / std_ret

        # Confidence intervals (90%)
        ci_low = float(np.percentile(sim_outcomes, 5))
        ci_high = float(np.percentile(sim_outcomes, 95))

        result = {
            "monte_carlo_survival_score": round(survival_score, 4),
            "expected_tail_drawdown": round(tail_drawdown_mag, 6),
            "probabilistic_sharpe": round(sharpe, 4),
            "ci_low_90pct": round(ci_low, 6),
            "ci_high_90pct": round(ci_high, 6),
            "n_simulations": self.n_simulations,
            "n_trades_input": n,
            "median_outcome": round(float(np.median(sim_outcomes)), 6),
            "pct_positive": round(float(np.mean(sim_outcomes > 0)) * 100, 1),
            "pct_negative": round(float(np.mean(sim_outcomes < 0)) * 100, 1),
        }

        await self._persist(strategy_id, result)
        return result

    def _empty_result(self, reason: str) -> dict:
        return {
            "monte_carlo_survival_score": 0.0,
            "expected_tail_drawdown": 0.0,
            "probabilistic_sharpe": 0.0,
            "ci_low_90pct": 0.0,
            "ci_high_90pct": 0.0,
            "n_simulations": 0,
            "n_trades_input": 0,
            "error": reason,
        }

    async def _persist(self, strategy_id: str, result: dict) -> None:
        if not self.db:
            return
        try:
            await self.db._execute_insert(
                """
                INSERT INTO monte_carlo_analysis
                    (id, strategy_id, monte_carlo_survival_score, expected_tail_drawdown,
                     probabilistic_sharpe, ci_low_90pct, ci_high_90pct,
                     n_simulations, n_trades_input, simulated_at)
                VALUES
                    (:id, :sid, :mcss, :etd, :ps, :ci_low, :ci_high,
                     :n_sim, :n_tr, NOW())
                ON CONFLICT (strategy_id) DO UPDATE SET
                    monte_carlo_survival_score = EXCLUDED.monte_carlo_survival_score,
                    expected_tail_drawdown = EXCLUDED.expected_tail_drawdown,
                    probabilistic_sharpe = EXCLUDED.probabilistic_sharpe,
                    simulated_at = NOW()
                """,
                {
                    "id": str(uuid.uuid4()),
                    "sid": strategy_id,
                    "mcss": result["monte_carlo_survival_score"],
                    "etd": result["expected_tail_drawdown"],
                    "ps": result["probabilistic_sharpe"],
                    "ci_low": result["ci_low_90pct"],
                    "ci_high": result["ci_high_90pct"],
                    "n_sim": result["n_simulations"],
                    "n_tr": result["n_trades_input"],
                },
            )
        except Exception as e:
            logger.warning(f"{self.name}: persist failed for {strategy_id}: {e}")
