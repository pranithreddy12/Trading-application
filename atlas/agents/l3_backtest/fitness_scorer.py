"""
FitnessScorer — Multi-component composite fitness scoring (DEPRECATED).

NOTE: This class is no longer called by the pipeline. The primary scoring
is now computed in BacktestRunner._run_backtest() via composite_fitness_score
and in score_contract.compute_institutional_score(). Kept for reference.

Replaces short_window_score as the primary selection signal.
Computes a 0-100 composite score from normalized components:

  • Sharpe ratio (30%)     — Risk-adjusted return
  • Win rate (20%)         — Consistency
  • Profit factor (20%)    — Edge quality (gross_profit / gross_loss)
  • Drawdown penalty (15%) — Capital preservation
  • Trade frequency (15%)  — Statistical significance

All components are normalized to 0-100 before weighting.
"""


class FitnessScorer:
    """Computes composite fitness scores for backtest results.

    Weights sum to 1.0:
        sharpe:           0.30  — Risk-adjusted return (most important)
        win_rate:         0.20  — Consistency
        profit_factor:    0.20  — Edge quality
        drawdown_penalty: 0.15  — Capital preservation
        trade_frequency:  0.15  — Statistical significance
    """

    WEIGHTS = {
        "sharpe": 0.30,
        "win_rate": 0.20,
        "profit_factor": 0.20,
        "drawdown_penalty": 0.15,
        "trade_frequency": 0.15,
    }

    def score(self, backtest_result: dict) -> float:
        """Compute composite fitness score (0-100).

        Parameters
        ----------
        backtest_result : dict
            Must contain keys: sharpe_ratio, win_rate, max_drawdown,
            total_trades. Optionally profit_factor (defaults to 1.0).

        Returns
        -------
        float — Composite fitness score rounded to 2 decimals.
        """
        scores = {}

        # 1. Sharpe ratio (0-100, capped at Sharpe=3 for full score)
        sharpe = float(backtest_result.get("sharpe_ratio") or 0)
        scores["sharpe"] = min(100.0, max(0.0, (sharpe / 3.0) * 100))

        # 2. Win rate (0-100, 45% WR = 0pts, 50% = 25pts, 65%+ = 100pts)
        wr = float(backtest_result.get("win_rate") or 0)
        scores["win_rate"] = min(100.0, max(0.0, ((wr - 0.45) / 0.20) * 100))

        # 3. Profit factor (0-100, PF=1.0 = 0pts, PF=2.0 = 100pts)
        pf = float(backtest_result.get("profit_factor") or 1.0)
        scores["profit_factor"] = min(100.0, max(0.0, (pf - 1.0) * 100))

        # 4. Drawdown penalty (0-100, 0% dd = 100pts, 30% dd = 0pts)
        dd = abs(float(backtest_result.get("max_drawdown") or 0))
        scores["drawdown_penalty"] = min(100.0, max(0.0, 100.0 - (dd / 0.30) * 100))

        # 5. Trade frequency (0-100, need >30 trades for full score)
        trades = int(backtest_result.get("total_trades") or 0)
        scores["trade_frequency"] = min(100.0, (trades / 30.0) * 100)

        # Weighted composite
        composite = sum(
            scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        return round(composite, 2)

    def score_batch(self, results: list[dict]) -> list[dict]:
        """Score a batch of backtest results and sort by fitness descending.

        Each result dict is augmented with a ``composite_fitness`` key.

        Parameters
        ----------
        results : list[dict]
            List of backtest result dicts.

        Returns
        -------
        list[dict] — Same dicts with ``composite_fitness`` added, sorted
                      by fitness descending.
        """
        for r in results:
            r["composite_fitness"] = self.score(r)
        return sorted(results, key=lambda x: x["composite_fitness"], reverse=True)
