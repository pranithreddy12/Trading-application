import asyncio
import math
from loguru import logger
from atlas.core.agent_base import BaseAgent
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from atlas.agents.l3_backtest.short_window_evaluator import (
    compute_composite_short_window_score,
    is_short_window,
)


class ValidatorAgent(BaseAgent):
    name = "ValidatorAgent"
    agent_type = "validator"
    layer = "L3"

    # Production thresholds (strict)
    PROD_RULES = {
        "min_sharpe": 1.0,
        "max_drawdown": -25.0,
        "min_trades": 30,
        "min_win_rate": 0.45,
        "min_profit_factor": 1.2,
        "overfit_ratio": 0.5,
    }

    # Dev/staging thresholds — tightened for demo credibility
    DEV_RULES = {
        "min_sharpe": 0.25,
        "max_drawdown": -80.0,
        "min_trades": 5,
        "min_win_rate": 0.25,
        "min_profit_factor": 0.75,
        "overfit_ratio": 0.0,
    }

    # Structural sanity — applied to EVERY strategy before scoring
    STRUCTURAL_RULES = {
        "min_entry_count": 5,
        "min_total_trades": 5,
        "max_entry_pct": 0.50,  # entries must not exceed 50% of bars
        "max_exit_pct": 0.95,  # exits must not exceed 95% of bars
    }

    @property
    def RULES(self):
        env = getattr(settings, "environment", "dev")
        return self.DEV_RULES if env in ("dev", "staging") else self.PROD_RULES

    def __init__(self, db_client: TimescaleClient):
        self.db = db_client

    async def run(self):
        print("=== VALIDATOR RUN LOOP ENTERED ===", flush=True)
        logger.info("ValidatorAgent polling for pending_validation strategies")
        while True:
            try:
                strategies = await self.db.get_strategies_by_status(
                    "pending_validation"
                )
                if strategies:
                    logger.info(f"Found {len(strategies)} to validate")
                for s in strategies:
                    await self._validate_one(s["id"], s.get("name", "unknown"))
            except Exception as e:
                logger.error(f"ValidatorAgent loop error: {e}")
            await asyncio.sleep(10)

    async def _validate_one(self, strategy_id: str, name: str):
        try:
            result = await self.db.get_backtest_result(strategy_id)
            if not result:
                logger.warning(f"No backtest result for {strategy_id}")
                return

            # Phase 1: Structural sanity gate — before scoring
            structural_fails = self._structural_sanity(result)
            if structural_fails:
                status = "failed_validation"
                notes = f"FAILED | Grade=F | Structural: {'; '.join(structural_fails)}"
                await self.db.update_strategy_status(strategy_id, status, notes)
                logger.info(f"{name} → {status} | {notes}")
                return

            # Phase 2 + 3 + 4: Composite scoring → tier
            passed, failed_tests = self._run_tests(result)
            score, grade = self._compute_composite_score(result)

            # Additional Day-4 metrics
            stab = self._compute_stability(result)
            train_sh = float(self._safe(self._extract(result, "train_sharpe")))
            test_sh = float(self._safe(self._extract(result, "test_sharpe")))
            holdout_sh = float(
                self._safe(
                    self._extract(result, "holdout_sharpe", "sharpe_ratio", "sharpe")
                )
            )
            ratio = self.RULES.get("overfit_ratio", 0.0)
            overfit_flag = False
            if train_sh > 0 and holdout_sh > 0 and ratio > 0:
                overfit_flag = holdout_sh < train_sh * ratio

            # Regime score if provided by backtest results (0-1), else neutral 0.5
            regime_score = float(self._safe(self._extract(result, "regime_score"), 0.5))

            status = self._assign_tier(score, passed)
            notes = self._build_notes(result, score, grade, status, failed_tests)

            # Persist validation metrics into strategy parameters via update (as validation_notes)
            metrics = {
                "train_sharpe": train_sh,
                "test_sharpe": test_sh,
                "holdout_sharpe": holdout_sh,
                "stability_score": round(stab, 3),
                "overfit_flag": bool(overfit_flag),
                "regime_score": regime_score,
                "composite_score": score,
                "tier": status,
            }

            # Compute short pass-rate snapshot (validated vs total)
            try:
                async with self.db.engine.connect() as conn:
                    res = await conn.execute(
                        "SELECT COUNT(*) FILTER (WHERE status IN ('validated','elite')) as passed, COUNT(*) as total FROM strategies"
                    )
                    row = res.fetchone()
                    if row and row[1] > 0:
                        pass_rate = round((row[0] / row[1]) * 100, 1)
                    else:
                        pass_rate = 0.0
                    metrics["pass_rate_pct"] = pass_rate
            except Exception:
                metrics["pass_rate_pct"] = None

            # Log and persist
            try:
                await self.db.log(
                    agent_id=self.name,
                    level="INFO",
                    message=f"Validation metrics for {strategy_id}",
                    metadata=metrics,
                )
            except Exception:
                pass

            try:
                # Store metrics as validation notes (JSON) and update status
                import json as _json

                await self.db.update_strategy_status(
                    strategy_id, status, _json.dumps(metrics)
                )
            except Exception as e:
                logger.warning(
                    f"Failed to persist validation notes for {strategy_id}: {e}"
                )

            logger.info(f"{name} → {status} | {notes} | metrics={metrics}")

        except Exception as e:
            logger.error(f"Error validating {strategy_id}: {e}")

    # ------------------------------------------------------------------
    # PHASE 1 — STRUCTURAL SANITY GATE
    # ------------------------------------------------------------------
    def _structural_sanity(self, result: dict) -> list[str]:
        fails = []
        entry_c = int(self._safe(self._extract(result, "entry_count")))
        exit_c = int(self._safe(self._extract(result, "exit_count")))
        trades = int(self._safe(self._extract(result, "total_trades")))
        bars = int(self._safe(self._extract(result, "bars_processed")))

        sr = self.STRUCTURAL_RULES

        if entry_c < sr["min_entry_count"]:
            fails.append(f"Entry count {entry_c} < {sr['min_entry_count']}")
        if trades < sr["min_total_trades"]:
            fails.append(f"Total trades {trades} < {sr['min_total_trades']}")
        if bars > 0 and entry_c > bars * sr["max_entry_pct"]:
            fails.append(
                f"Entry saturation {entry_c}/{bars} ({entry_c / bars * 100:.0f}%) "
                f"> {sr['max_entry_pct'] * 100:.0f}%"
            )
        if bars > 0 and exit_c > bars * sr["max_exit_pct"]:
            fails.append(
                f"Exit saturation {exit_c}/{bars} ({exit_c / bars * 100:.0f}%) "
                f"> {sr['max_exit_pct'] * 100:.0f}%"
            )

        return fails

    # ------------------------------------------------------------------
    # PHASE 4 — TIER ASSIGNMENT
    # ------------------------------------------------------------------
    def _assign_tier(self, score: float, passed: bool) -> str:
        # New Day-4 status buckets
        if not passed:
            return "failed_validation"

        if score >= 90:
            return "elite"
        if score >= 70:
            return "validated"
        if score >= 50:
            return "research_candidate"
        if score >= 30:
            return "repair_candidate"
        return "failed_validation"

    # ------------------------------------------------------------------
    # PHASE 5 — HUMAN-READABLE NOTES
    # ------------------------------------------------------------------
    def _build_notes(
        self, result: dict, score: float, grade: str, status: str, failed: list[str]
    ) -> str:
        parts = []
        if status.startswith("validated") or status == "research_candidate":
            parts.append(f"PASSED | Grade={grade} | Score={score}")
            parts.extend(self._summary_lines(result))
        else:
            parts.append(f"FAILED | Grade={grade} | Score={score}")
            if failed:
                parts.append(f"Failed: {'; '.join(failed)}")
            parts.extend(self._diagnose(score, result))
        return " | ".join(parts)

    def _diagnose(self, score: float, result: dict) -> list[str]:
        diag = []
        eval_mode = result.get("evaluation_mode", "institutional")
        trades = int(self._safe(self._extract(result, "total_trades")))
        win_rate = self._safe(self._extract(result, "win_rate"))
        pf = self._safe(self._extract(result, "profit_factor"), 1.0)
        entry_c = int(self._safe(self._extract(result, "entry_count")))
        exit_c = int(self._safe(self._extract(result, "exit_count")))
        bars = int(self._safe(self._extract(result, "bars_processed")))

        if eval_mode == "short_window":
            total_return = self._safe(self._extract(result, "total_return"))
            cost_burden = self._safe(self._extract(result, "cost_burden"))
            composite = self._safe(self._extract(result, "composite_score"))
            if score < 20:
                diag.append("Catastrophic: all short-window metrics negative")
            elif score < 40:
                low = []
                if total_return < 0 and cost_burden > abs(total_return):
                    low.append("Costs exceed edge")
                if trades < 5:
                    low.append("Low Trades")
                if win_rate < 0.3:
                    low.append("Low Win Rate")
                if composite < 30:
                    low.append(f"Low Composite ({composite:.0f})")
                diag.append(
                    " + ".join(low) if low else "Multiple metrics below threshold"
                )
            return diag

        sharpe = self._safe(self._extract(result, "sharpe_ratio", "sharpe"))
        if score < 20:
            diag.append("Catastrophic: all key metrics in negative territory")
        elif score < 40:
            low = []
            if sharpe < 0.5:
                low.append("Low Sharpe")
            if trades < 10:
                low.append("Low Trades")
            if win_rate < 0.3:
                low.append("Low Win Rate")
            if bars > 0 and exit_c > bars * 0.8:
                low.append("Exit Saturation")
            diag.append(" + ".join(low) if low else "Multiple metrics below threshold")
        return diag

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _safe(self, value, default=0.0):
        """Handle None / NaN / Inf safely."""
        if value is None:
            return default
        try:
            f = float(value)
            return default if (math.isnan(f) or math.isinf(f)) else f
        except Exception:
            return default

    def _extract(self, result: dict, *keys):
        """Try multiple key names — direct or nested under 'results'."""
        nested = result.get("results", {}) or {}
        for k in keys:
            v = result.get(k) or nested.get(k)
            if v is not None:
                return v
        return None

    def _summary_lines(self, result: dict) -> list[str]:
        sharpe = self._safe(self._extract(result, "sharpe_ratio", "sharpe"))
        win_rate = self._safe(self._extract(result, "win_rate"))
        trades = int(self._safe(self._extract(result, "total_trades")))
        drawdown = self._safe(self._extract(result, "max_drawdown"))
        pf = self._safe(self._extract(result, "profit_factor"), 1.0)
        return [
            f"Sharpe={sharpe:.2f}",
            f"WinRate={win_rate:.0%}",
            f"Trades={trades}",
            f"MaxDD={drawdown:.1f}%",
            f"PF={pf:.2f}",
        ]

    # ------------------------------------------------------------------
    # PASS / FAIL TESTS
    # ------------------------------------------------------------------
    def _run_tests(self, result: dict) -> tuple[bool, list[str]]:
        failed = []

        eval_mode = result.get("evaluation_mode", "institutional")
        drawdown = self._safe(self._extract(result, "max_drawdown"))
        trades = int(self._safe(self._extract(result, "total_trades")))
        win_rate = self._safe(self._extract(result, "win_rate"))
        pf = self._safe(self._extract(result, "profit_factor"), 1.0)

        if eval_mode == "short_window":
            composite = self._safe(self._extract(result, "composite_score"))
            if composite < 30:
                failed.append(f"composite_score {composite:.1f} < 30")
            if drawdown < -80.0:
                failed.append(f"drawdown {drawdown:.1f}% < -80%")
            if trades < 3:
                failed.append(f"trades {trades} < 3")
            if win_rate < 0.20:
                failed.append(f"win_rate {win_rate:.2f} < 0.20")
            if pf < 0.60:
                failed.append(f"profit_factor {pf:.2f} < 0.60")
            return len(failed) == 0, failed

        # INSTITUTIONAL MODE
        sharpe = self._safe(self._extract(result, "sharpe_ratio", "sharpe"))
        train_sh = self._safe(self._extract(result, "train_sharpe"))
        holdout_sh = self._safe(self._extract(result, "holdout_sharpe"))

        if sharpe < self.RULES["min_sharpe"]:
            failed.append(f"sharpe {sharpe:.2f} < {self.RULES['min_sharpe']}")
        if drawdown < self.RULES["max_drawdown"]:
            failed.append(f"drawdown {drawdown:.1f}% < {self.RULES['max_drawdown']}%")
        if trades < self.RULES["min_trades"]:
            failed.append(f"trades {trades} < {self.RULES['min_trades']}")
        if win_rate < self.RULES["min_win_rate"]:
            failed.append(f"win_rate {win_rate:.2f} < {self.RULES['min_win_rate']}")
        if pf < self.RULES["min_profit_factor"]:
            failed.append(f"profit_factor {pf:.2f} < {self.RULES['min_profit_factor']}")

        # Overfitting guard
        ratio = self.RULES["overfit_ratio"]
        if train_sh > 0 and holdout_sh > 0 and ratio > 0:
            if holdout_sh < train_sh * ratio:
                failed.append(
                    f"overfit: holdout {holdout_sh:.2f} < "
                    f"{ratio * 100:.0f}% of train {train_sh:.2f}"
                )

        return len(failed) == 0, failed

    # ------------------------------------------------------------------
    # COMPOSITE SCORE (0–100) + GRADE (A/B/C/F)
    # ------------------------------------------------------------------
    def _compute_stability(self, result: dict) -> float:
        """
        Stability score [0, 1] based on consistency across train/test/holdout.
        High variance between periods → low stability (overfitting).
        """
        train = self._safe(self._extract(result, "train_sharpe"))
        test = self._safe(self._extract(result, "test_sharpe"))
        holdout = self._safe(
            self._extract(result, "holdout_sharpe", "sharpe_ratio", "sharpe")
        )
        vals = [v for v in (train, test, holdout) if v > 0]
        if len(vals) < 2:
            return 0.5  # Phase 3: unknown ≠ perfect
        mean_v = sum(vals) / len(vals)
        if mean_v == 0:
            return 0.5
        max_dev = max(abs(v - mean_v) / mean_v for v in vals)
        stability = max(0.0, 1.0 - max_dev)
        return stability

    def _compute_composite_score(self, result: dict) -> tuple[float, str]:
        eval_mode = result.get("evaluation_mode", "institutional")

        if eval_mode == "short_window":
            raw_score = self._safe(self._extract(result, "composite_score"))
            if raw_score > 0:
                score = raw_score
            else:
                score = compute_composite_short_window_score(
                    {
                        "total_return": self._safe(
                            self._extract(result, "total_return")
                        ),
                        "profit_factor": self._safe(
                            self._extract(result, "profit_factor"), 1.0
                        ),
                        "win_rate": self._safe(self._extract(result, "win_rate")),
                        "max_drawdown": self._safe(
                            self._extract(result, "max_drawdown")
                        )
                        / 100.0,
                        "total_trades": int(
                            self._safe(self._extract(result, "total_trades"))
                        ),
                        "cost_burden": self._safe(self._extract(result, "cost_burden")),
                    }
                )
            score = round(score, 1)
            grade = (
                "A"
                if score >= 70
                else "B"
                if score >= 50
                else "C"
                if score >= 30
                else "F"
            )
            return score, grade

        # INSTITUTIONAL MODE — Sharpe-based composite
        sharpe = self._safe(self._extract(result, "sharpe_ratio", "sharpe"))
        win_rate = self._safe(self._extract(result, "win_rate"))
        trades = int(self._safe(self._extract(result, "total_trades")))
        drawdown = self._safe(self._extract(result, "max_drawdown"))  # negative %
        pf = self._safe(self._extract(result, "profit_factor"), 1.0)
        stab = self._compute_stability(result)

        s = min(max(sharpe / 2.5, 0.0), 1.0)  # 2.5 Sharpe  → 1.0
        w = min(max((win_rate - 0.4) / 0.3, 0.0), 1.0)  # 70% WR      → 1.0
        t = min(max((trades - 5) / 95.0, 0.0), 1.0)  # 100 trades  → 1.0
        d = min(max(1.0 + drawdown / 30.0, 0.0), 1.0)  # -30% DD     → 0.0
        p = min(max((pf - 0.8) / 2.2, 0.0), 1.0)  # PF 3.0      → 1.0

        score = (
            s * 0.30 + w * 0.15 + t * 0.10 + d * 0.10 + p * 0.15 + stab * 0.20
        ) * 100
        score = round(score, 1)
        grade = (
            "A" if score >= 70 else "B" if score >= 50 else "C" if score >= 30 else "F"
        )
        return score, grade


async def main():
    print("=== VALIDATOR MAIN STARTED ===", flush=True)

    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()

    agent = ValidatorAgent(db_client)

    print("=== STARTING VALIDATOR AGENT ===", flush=True)

    await agent.run()


if __name__ == "__main__":
    print("=== VALIDATOR EXECUTION HIT ===", flush=True)
    asyncio.run(main())
