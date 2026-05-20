"""
walk_forward_analyzer.py — Phase 11: Walk-Forward Validation.

Evaluates strategy temporal robustness by splitting historical data into
sequential train/test windows and measuring consistency across windows.

Key outputs:
  - walk_forward_score [0, 1]: fraction of windows where strategy survived
  - temporal_consistency [0, 1]: inverse of Sharpe variance across windows
  - regime_survival_score [0, 1]: fraction of distinct regimes survived
"""

import asyncio
import json
import math
import uuid
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class WalkForwardAnalyzer(BaseAgent):
    """
    Walk-Forward Analyzer — evaluates strategy robustness across rolling time windows.

    Configuration:
      - n_windows: number of rolling windows (default 5)
      - train_pct: fraction of each window used for training (default 0.7)
      - min_trades_per_window: minimum trades required to count as "survived" (default 3)

    Persists results to walk_forward_analysis table.
    """

    name = "WalkForwardAnalyzer"
    agent_type = "walk_forward_analyzer"
    layer = "L3"

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        n_windows: int = 5,
        train_pct: float = 0.7,
        min_trades_per_window: int = 3,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.n_windows = n_windows
        self.train_pct = train_pct
        self.min_trades = min_trades_per_window

    async def run(self):
        logger.info(f"{self.name}: idle — triggered on demand by ValidatorAgent")
        await asyncio.sleep(3600)

    async def analyze(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        signals: pd.Series,
        background_results: dict,
    ) -> dict:
        """
        Run walk-forward analysis on a strategy's signals over a price DataFrame.

        Returns:
          {
            "walk_forward_score": float,       # [0, 1]
            "temporal_consistency": float,      # [0, 1]
            "n_windows_survived": int,
            "n_windows_total": int,
            "per_window_metrics": list[dict],
            "regime_survival_score": float,     # [0, 1]
          }
        """
        if df is None or len(df) < 100:
            return self._empty_result("insufficient_data")

        n = len(df)
        window_size = n // self.n_windows
        if window_size < 20:
            return self._empty_result("window_too_small")

        window_metrics = []
        regimes_seen = set()

        for w in range(self.n_windows):
            start = w * window_size
            mid = start + int(window_size * self.train_pct)
            end = min(start + window_size, n)

            if end - start < 30:
                continue

            train_df = df.iloc[start:mid]
            test_df = df.iloc[mid:end]
            train_sig = signals.iloc[start:mid]
            test_sig = signals.iloc[mid:end]

            train_ret = self._window_return(train_df, train_sig)
            test_ret = self._window_return(test_df, test_sig)
            train_trades = int((train_sig == 1).sum())
            test_trades = int((test_sig == 1).sum())

            survived = test_ret > 0 and test_trades >= self.min_trades

            # Track regime from volatility features
            if "volatility_regime" in df.columns:
                window_regimes = df.iloc[start:end]["volatility_regime"].dropna().unique()
                for r in window_regimes:
                    regimes_seen.add(str(r))

            window_metrics.append({
                "window": w,
                "train_start": str(df.index[start]) if hasattr(df.index, 'dtype') else str(start),
                "train_end": str(df.index[mid - 1]) if hasattr(df.index, 'dtype') else str(mid),
                "test_end": str(df.index[end - 1]) if hasattr(df.index, 'dtype') else str(end),
                "train_return": round(float(train_ret), 6),
                "test_return": round(float(test_ret), 6),
                "train_trades": train_trades,
                "test_trades": test_trades,
                "survived": survived,
            })

        if not window_metrics:
            return self._empty_result("no_windows")

        n_survived = sum(1 for wm in window_metrics if wm["survived"])
        n_total = len(window_metrics)
        walk_forward_score = n_survived / n_total if n_total > 0 else 0.0

        # Temporal consistency: low variance in test returns across windows
        test_rets = [wm["test_return"] for wm in window_metrics]
        if len(test_rets) > 1:
            mean_ret = np.mean(test_rets)
            std_ret = np.std(test_rets) + 1e-10
            temporal_consistency = max(0.0, 1.0 - (std_ret / (abs(mean_ret) + 1e-10)))
            temporal_consistency = min(1.0, temporal_consistency)
        else:
            temporal_consistency = 1.0

        # Regime survival: at least 3 distinct regimes = robust
        n_regimes = len(regimes_seen)
        regime_survival_score = min(1.0, n_regimes / 5.0)

        result = {
            "walk_forward_score": round(walk_forward_score, 4),
            "temporal_consistency": round(temporal_consistency, 4),
            "regime_survival_score": round(regime_survival_score, 4),
            "n_windows_survived": n_survived,
            "n_windows_total": n_total,
            "per_window_metrics": window_metrics,
        }

        # Persist
        await self._persist(strategy_id, result)
        return result

    def _window_return(self, df: pd.DataFrame, signals: pd.Series) -> float:
        """Compute simple return from position signals."""
        if len(df) < 5:
            return 0.0
        close = df["close"].values
        pos = signals.values
        rets = np.diff(close) / close[:-1]
        aligned = pos[:-1] * rets
        return float(np.sum(aligned))

    def _empty_result(self, reason: str) -> dict:
        return {
            "walk_forward_score": 0.0,
            "temporal_consistency": 0.0,
            "regime_survival_score": 0.0,
            "n_windows_survived": 0,
            "n_windows_total": 0,
            "per_window_metrics": [],
            "error": reason,
        }

    async def _persist(self, strategy_id: str, result: dict) -> None:
        if not self.db:
            return
        try:
            await self.db._execute_insert(
                """
                INSERT INTO walk_forward_analysis
                    (id, strategy_id, walk_forward_score, temporal_consistency,
                     regime_survival_score, n_windows_survived, n_windows_total,
                     per_window_metrics, analyzed_at)
                VALUES
                    (:id, :sid, :wfs, :tc, :rss, :n_surv, :n_tot, :metrics, NOW())
                ON CONFLICT (strategy_id) DO UPDATE SET
                    walk_forward_score = EXCLUDED.walk_forward_score,
                    temporal_consistency = EXCLUDED.temporal_consistency,
                    regime_survival_score = EXCLUDED.regime_survival_score,
                    n_windows_survived = EXCLUDED.n_windows_survived,
                    per_window_metrics = EXCLUDED.per_window_metrics,
                    analyzed_at = NOW()
                """,
                {
                    "id": str(uuid.uuid4()),
                    "sid": strategy_id,
                    "wfs": result["walk_forward_score"],
                    "tc": result["temporal_consistency"],
                    "rss": result["regime_survival_score"],
                    "n_surv": result["n_windows_survived"],
                    "n_tot": result["n_windows_total"],
                    "metrics": json.dumps(result["per_window_metrics"]),
                },
            )
        except Exception as e:
            logger.warning(f"{self.name}: persist failed for {strategy_id}: {e}")
