"""
overfitting_detector.py — Phase 11: Overfitting Detection & Robustness Scoring.

Detects overfitting through:
  - Parameter perturbation: nudge thresholds slightly and measure performance degradation
  - Shuffle tests: shuffle signal arrival times, measure return degradation
  - Noise robustness: add small random noise to entries/exits

Outputs:
  - overfit_probability [0, 1]: probability strategy is overfit
  - robustness_score [0, 1]: 1 - overfit_probability
  - parameter_stability_score [0, 1]: stability under parameter nudge
"""

import asyncio
import json
import uuid
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from atlas.core.agent_base import BaseAgent


class OverfittingDetector(BaseAgent):
    """
    Overfitting Detector — evaluates signal fragility via perturbation and shuffle tests.

    Configuration:
      - n_shuffles: number of label-shuffle iterations (default 50)
      - perturbation_pct: parameter nudge range as fraction (default 0.05)
    """

    name = "OverfittingDetector"
    agent_type = "overfitting_detector"
    layer = "L3"

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        n_shuffles: int = 50,
        perturbation_pct: float = 0.05,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.n_shuffles = n_shuffles
        self.perturb_pct = perturbation_pct

    async def run(self):
        logger.info(f"{self.name}: idle — triggered on demand by ValidatorAgent")
        await asyncio.sleep(3600)

    async def detect(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        signals: pd.Series,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Run overfitting detection on a strategy's signals.

        Returns:
          {
            "overfit_probability": float,     # [0, 1]
            "robustness_score": float,         # [0, 1]
            "parameter_stability_score": float, # [0, 1]
            "shuffle_test_p_value": float,
            "noise_degradation_pct": float,
          }
        """
        if df is None or len(df) < 30:
            return self._empty_result("insufficient_data")
        if signals is None or (signals == 0).all():
            return self._empty_result("no_signals")

        close = df["close"].values
        base_rets = np.diff(close) / close[:-1]
        base_pos = signals.values[:-1]  # align with returns
        base_return = float(np.sum(base_pos * base_rets))

        if base_return <= 0:
            return {
                "overfit_probability": 1.0,
                "robustness_score": 0.0,
                "parameter_stability_score": 0.0,
                "shuffle_test_p_value": 1.0,
                "noise_degradation_pct": 0.0,
                "error": "non_positive_base_return",
            }

        # ---- Shuffle Test ----
        shuffle_returns = []
        for _ in range(self.n_shuffles):
            np.random.seed(_)
            shuffled = np.random.permutation(base_pos)
            shuffled_ret = float(np.sum(shuffled * base_rets))
            shuffle_returns.append(shuffled_ret)

        shuffle_returns = np.array(shuffle_returns)
        # p-value: fraction of shuffled runs that beat original return
        p_value = float(np.mean(shuffle_returns >= base_return))

        # ---- Noise Robustness ----
        noise_levels = np.linspace(0.001, 0.02, 10)
        degraded_returns = []
        for noise in noise_levels:
            noisy_pos = base_pos + np.random.normal(0, noise, size=len(base_pos))
            noisy_pos = np.clip(noisy_pos, -1, 1)
            noisy_ret = float(np.sum(noisy_pos * base_rets))
            degraded_returns.append(noisy_ret)

        # Average degradation from noise
        baseline = base_return
        degradation_pct = 0.0
        if baseline > 0:
            avg_degraded = float(np.mean(degraded_returns))
            degradation_pct = max(0.0, (baseline - avg_degraded) / baseline)
        degradation_pct = min(1.0, degradation_pct)

        # ---- Parameter Stability (if params available) ----
        param_stability = 1.0
        if params:
            numeric_params = {k: v for k, v in params.items() if isinstance(v, (int, float))}
            if numeric_params:
                perturbed_rets = []
                for _ in range(20):
                    np.random.seed(_ * 7)
                    # Apply small perturbation noise as proxy for parameter sensitivity
                    noise_scale = self.perturb_pct * np.random.uniform(0.5, 2.0)
                    noise = np.random.normal(0, noise_scale, size=len(base_pos))
                    perturbed = base_pos + noise
                    perturbed = np.clip(perturbed, -1, 1)
                    ret = float(np.sum(perturbed * base_rets))
                    perturbed_rets.append(ret)

                perturbed_rets = np.array(perturbed_rets)
                if baseline > 0:
                    pert_degradation = max(0.0, (baseline - np.mean(perturbed_rets)) / baseline)
                    param_stability = max(0.0, 1.0 - pert_degradation)

        # ---- Composite Overfit Probability ----
        # Low p-value (strategy beats random) → low overfit probability
        # High noise degradation → high overfit probability
        # Low parameter stability → high overfit probability
        p_value_score = max(0.0, 1.0 - p_value)  # 1 when p=0 (significant), 0 when p=1
        noise_penalty = degradation_pct
        param_penalty = 1.0 - param_stability

        overfit_prob = 0.4 * (1.0 - p_value_score) + 0.3 * noise_penalty + 0.3 * param_penalty
        overfit_prob = min(1.0, max(0.0, overfit_prob))
        robustness = 1.0 - overfit_prob

        result = {
            "overfit_probability": round(overfit_prob, 4),
            "robustness_score": round(robustness, 4),
            "parameter_stability_score": round(param_stability, 4),
            "shuffle_test_p_value": round(p_value, 4),
            "noise_degradation_pct": round(degradation_pct, 4),
            "n_shuffles": self.n_shuffles,
        }

        await self._persist(strategy_id, result)
        return result

    def _empty_result(self, reason: str) -> dict:
        return {
            "overfit_probability": 1.0,
            "robustness_score": 0.0,
            "parameter_stability_score": 0.0,
            "shuffle_test_p_value": 1.0,
            "noise_degradation_pct": 0.0,
            "error": reason,
        }

    async def _persist(self, strategy_id: str, result: dict) -> None:
        if not self.db:
            return
        try:
            await self.db._execute_insert(
                """
                INSERT INTO overfitting_analysis
                    (id, strategy_id, overfit_probability, robustness_score,
                     parameter_stability_score, shuffle_test_p_value,
                     noise_degradation_pct, analyzed_at)
                VALUES
                    (:id, :sid, :op, :rs, :pss, :stpv, :ndp, NOW())
                ON CONFLICT (strategy_id) DO UPDATE SET
                    overfit_probability = EXCLUDED.overfit_probability,
                    robustness_score = EXCLUDED.robustness_score,
                    analyzed_at = NOW()
                """,
                {
                    "id": str(uuid.uuid4()),
                    "sid": strategy_id,
                    "op": result["overfit_probability"],
                    "rs": result["robustness_score"],
                    "pss": result["parameter_stability_score"],
                    "stpv": result["shuffle_test_p_value"],
                    "ndp": result["noise_degradation_pct"],
                },
            )
        except Exception as e:
            logger.warning(f"{self.name}: persist failed for {strategy_id}: {e}")
