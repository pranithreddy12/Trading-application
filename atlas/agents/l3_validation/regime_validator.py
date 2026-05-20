"""
regime_validator.py — Phase 11: Regime-Segmented Validation.

Validates strategies across distinct market regimes:
  - bull / bear / choppy (trend-based)
  - high_vol / low_vol (volatility-based)

Requirements:
  - Must survive >= 3 regimes to pass
  - Detects regime over-specialization (strategy only works in one condition)

Outputs:
  - regime_survival_map: { regime: { return, trades, survived } }
  - regime_dependency_score [0, 1]: 1 = works in all regimes, 0 = single-regime only
  - regime_survival_score [0, 1]: fraction of regimes survived
"""

import asyncio
import json
import uuid
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from atlas.core.agent_base import BaseAgent


class RegimeValidator(BaseAgent):
    """
    Regime Validator — segmented strategy validation across distinct market regimes.

    Configuration:
      - min_trades_per_regime: minimum trades to count as active in a regime (default 2)
      - min_regimes_survived: minimum regimes required to pass (default 3)
    """

    name = "RegimeValidator"
    agent_type = "regime_validator"
    layer = "L3"

    REGIME_DEFINITIONS = ["bull", "bear", "choppy", "high_vol", "low_vol"]

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        min_trades_per_regime: int = 2,
        min_regimes_survived: int = 3,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.min_trades = min_trades_per_regime
        self.min_regimes = min_regimes_survived

    async def run(self):
        logger.info(f"{self.name}: idle — triggered on demand by ValidatorAgent")
        await asyncio.sleep(3600)

    async def validate(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        signals: pd.Series,
    ) -> dict:
        """
        Run regime-segmented validation.

        Returns:
          {
            "regime_survival_map": dict,
            "regime_dependency_score": float,   # [0, 1]
            "regime_survival_score": float,      # [0, 1]
            "n_regimes_survived": int,
            "passes_min_regimes": bool,
          }
        """
        if df is None or len(df) < 50:
            return self._empty_result("insufficient_data")

        close = df["close"].values
        rets = np.diff(close) / close[:-1]
        pos = signals.values[:-1] if len(signals) > 1 else np.zeros_like(rets)

        # Classify each bar into a regime
        vol = df.get("volatility_regime", pd.Series(np.ones(len(df))))
        ema = df.get("ema_spread_pct", pd.Series(np.zeros(len(df))))
        trend = df.get("trend_strength", pd.Series(np.zeros(len(df))))

        # Align to returns length (n-1)
        vol_arr = vol.values[:-1] if len(vol) > 1 else np.ones_like(rets)
        ema_arr = ema.values[:-1] if len(ema) > 1 else np.zeros_like(rets)
        trend_arr = trend.values[:-1] if len(trend) > 1 else np.zeros_like(rets)

        regimes = np.full(len(rets), "unknown", dtype=object)

        # Bull: trending_up + positive EMA spread
        regimes[(trend_arr > 0.001) & (ema_arr > 0.0005)] = "bull"
        # Bear: trending_down + negative EMA spread
        regimes[(trend_arr > 0.001) & (ema_arr < -0.0005)] = "bear"
        # Choppy: low trend strength
        regimes[abs(trend_arr) <= 0.001] = "choppy"
        # High vol
        if np.issubdtype(vol_arr.dtype, np.number):
            vol_median = np.nanmedian(vol_arr[vol_arr > 0]) or 1.0
            regimes[(vol_arr > vol_median * 1.5)] = "high_vol"
            regimes[(vol_arr < vol_median * 0.5)] = "low_vol"
        else:
            # String-based volatility_regime column
            regimes[vol_arr == "high_vol"] = "high_vol"
            regimes[vol_arr == "low_vol"] = "low_vol"

        regime_map = {}
        for regime_name in self.REGIME_DEFINITIONS:
            mask = regimes == regime_name
            if mask.sum() < 5:
                regime_map[regime_name] = {
                    "return": 0.0,
                    "trades": 0,
                    "bars": int(mask.sum()),
                    "survived": False,
                }
                continue

            regime_ret = float(np.sum(pos[mask] * rets[mask]))
            regime_trades = int(np.sum(pos[mask] != 0))
            survived = regime_trades >= self.min_trades and regime_ret > 0

            regime_map[regime_name] = {
                "return": round(regime_ret, 6),
                "trades": regime_trades,
                "bars": int(mask.sum()),
                "survived": survived,
            }

        n_survived = sum(1 for r in regime_map.values() if r["survived"])
        n_regimes = len(self.REGIME_DEFINITIONS)
        regime_survival_score = n_survived / n_regimes if n_regimes > 0 else 0.0
        regime_dependency_score = max(0.0, n_survived / max(1, n_regimes))
        passes = n_survived >= self.min_regimes

        # Identify over-specialization
        over_specialized = n_survived <= 1 and n_regimes >= 3

        result = {
            "regime_survival_map": regime_map,
            "regime_dependency_score": round(regime_dependency_score, 4),
            "regime_survival_score": round(regime_survival_score, 4),
            "n_regimes_survived": n_survived,
            "n_regimes_total": n_regimes,
            "passes_min_regimes": passes,
            "over_specialized": over_specialized,
        }

        await self._persist(strategy_id, result)
        return result

    def _empty_result(self, reason: str) -> dict:
        return {
            "regime_survival_map": {},
            "regime_dependency_score": 0.0,
            "regime_survival_score": 0.0,
            "n_regimes_survived": 0,
            "n_regimes_total": len(self.REGIME_DEFINITIONS),
            "passes_min_regimes": False,
            "over_specialized": True,
            "error": reason,
        }

    async def _persist(self, strategy_id: str, result: dict) -> None:
        if not self.db:
            return
        try:
            await self.db._execute_insert(
                """
                INSERT INTO regime_validation
                    (id, strategy_id, regime_survival_map, regime_dependency_score,
                     regime_survival_score, n_regimes_survived, passes_min_regimes,
                     over_specialized, validated_at)
                VALUES
                    (:id, :sid, :rsm, :rds, :rss, :nrs, :pmr, :os, NOW())
                ON CONFLICT (strategy_id) DO UPDATE SET
                    regime_dependency_score = EXCLUDED.regime_dependency_score,
                    regime_survival_score = EXCLUDED.regime_survival_score,
                    validated_at = NOW()
                """,
                {
                    "id": str(uuid.uuid4()),
                    "sid": strategy_id,
                    "rsm": json.dumps(result["regime_survival_map"]),
                    "rds": result["regime_dependency_score"],
                    "rss": result["regime_survival_score"],
                    "nrs": result["n_regimes_survived"],
                    "pmr": result["passes_min_regimes"],
                    "os": result["over_specialized"],
                },
            )
        except Exception as e:
            logger.warning(f"{self.name}: persist failed for {strategy_id}: {e}")
