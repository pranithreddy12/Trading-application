"""
economic_efficiency_engine.py — PHASE 29: Economic Efficiency, Survival Quality & Real Evolutionary Fitness

This engine is the organism's economic self-awareness layer. It continuously answers:

    Does ATLAS actually evolve economically effective behavior?

DOMAINS:
    29A — Economic Efficiency Analyzer (trade quality, capital efficiency, survival quality, scout quality)
    29B — Long-Horizon Fitness Learning (rolling windows: 1h, 6h, 24h, multi-regime)
    29C — Capital Preservation Analysis (drawdown persistence, recovery, cascading failure, contagion)
    29D — Regime Specialization Detection (specialists, fragile, cross-regime survivors)
    29E — Mutation Fitness Evolution (family dominance, collapse rates, lineage survival)
    29F — Scout Predictive Value Analysis (economic ranking, contradiction penalties)
    29G — Execution Realism Analysis (slippage, latency, fill quality, liquidity degradation)

ADVISORY ONLY — reads, analyzes, and persists findings; never trades.
"""

from __future__ import annotations

import asyncio
import json
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import numpy as np
from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent
from atlas.core.serialization import safe_json_dumps


class EconomicEfficiencyEngine(BaseAgent):
    """
    L7 Meta Agent — Phase 29: Economic Efficiency, Survival Quality & Real Evolutionary Fitness.
    Runs every 10 minutes, analyzes all economic domains, and persists findings.
    """

    name = "EconomicEfficiencyEngine"
    agent_type = "economic_efficiency"
    layer = "L7"

    # ── Config ──────────────────────────────────────────────────────────────
    ANALYSIS_INTERVAL = 600          # Every 10 minutes
    FITNESS_WINDOWS_HOURS = [1, 6, 24]  # Rolling windows for 29B
    MIN_TRADES_FOR_ANALYSIS = 5      # Minimum trades to compute meaningful stats

    # Drawdown severity thresholds (29C)
    DD_WARNING = 0.05
    DD_MODERATE = 0.10
    DD_SEVERE = 0.15
    DD_CRITICAL = 0.20

    # Regime specialization thresholds (29D)
    REGIME_SPECIALIST_THRESHOLD = 0.30   # Sharpe delta required to be "specialist"
    CROSS_REGIME_SURVIVAL_MIN = 0.60     # Min survival rate across regimes

    # Mutation evolution thresholds (29E)
    MUTATION_COLLAPSE_THRESHOLD = 0.10   # Survival rate below this = collapsing
    DOMINANCE_THRESHOLD = 0.50           # Market share above this = dominant

    # Scout quality thresholds (29F)
    SCOUT_CONTRADICTION_PENALTY = 0.15   # Trust penalty per contradiction

    # Execution realism thresholds (29G)
    DEGRADATION_CRITICAL = 0.70          # Execution degradation above this = critical

    def __init__(self, redis_client, db_client):
        super().__init__(
            self.name, self.agent_type, self.layer, redis_client,
            advisory_only=True  # Never trades
        )
        self.db = db_client

        # In-memory caches for trend detection
        self._prev_trade_quality: dict = {}
        self._prev_capital_efficiency: dict = {}
        self._prev_survival_quality: dict = {}
        self._prev_scout_quality: dict = {}
        self._prev_mutation_fitness: dict = {}
        self._prev_regime_specialization: dict = {}
        self._prev_execution_realism: dict = {}

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════════

    async def run(self):
        logger.info(f"{self.name}: Phase 29 — Economic Efficiency Engine starting")
        while self.status == "running":
            try:
                await self._full_economic_analysis_cycle()
            except Exception as e:
                logger.error(f"{self.name}: Cycle error: {e}", exc_info=True)

            for _ in range(self.ANALYSIS_INTERVAL // 10):
                await asyncio.sleep(10)
                if self.status != "running":
                    return

    async def _full_economic_analysis_cycle(self):
        """Execute all 7 analysis domains and persist findings."""

        # ── 29A: Economic Efficiency Analyzer ───────────────────────────────
        trade_quality = await self._analyze_trade_quality()
        capital_efficiency = await self._analyze_capital_efficiency()
        survival_quality = await self._analyze_survival_quality()
        scout_quality = await self._analyze_scout_quality()

        # ── 29B: Long-Horizon Fitness Learning ─────────────────────────────
        fitness_windows = await self._compute_fitness_windows()
        await self._persist_fitness_windows(fitness_windows)

        # ── 29C: Capital Preservation Analysis ─────────────────────────────
        capital_preservation = await self._analyze_capital_preservation()

        # ── 29D: Regime Specialization Detection ───────────────────────────
        regime_specialization = await self._detect_regime_specialization()

        # ── 29E: Mutation Fitness Evolution ────────────────────────────────
        mutation_fitness = await self._analyze_mutation_fitness()

        # ── 29F: Scout Predictive Value Analysis ───────────────────────────
        scout_predictive = await self._analyze_scout_predictive_value()

        # ── 29G: Execution Realism Analysis ────────────────────────────────
        execution_realism = await self._analyze_execution_realism()

        # ── Persist composite report ───────────────────────────────────────
        composite = {
            "trade_quality": trade_quality,
            "capital_efficiency": capital_efficiency,
            "survival_quality": survival_quality,
            "scout_quality": scout_quality,
            "capital_preservation": capital_preservation,
            "regime_specialization": regime_specialization,
            "mutation_fitness": mutation_fitness,
            "scout_predictive_value": scout_predictive,
            "execution_realism": execution_realism,
        }
        await self._persist_composite_analysis(composite)

        # ── Detect trends / drift ─────────────────────────────────────────
        trends = self._detect_economic_trends(composite)
        if trends:
            logger.info(f"{self.name}: Economic trends detected: {json.dumps(trends, default=str)[:500]}")

        logger.info(
            f"{self.name}: Analysis complete — "
            f"trade_quality={trade_quality.get('expectancy', 0):.4f}, "
            f"capital_efficiency={capital_efficiency.get('return_per_drawdown', 0):.2f}, "
            f"survival_quality={survival_quality.get('avg_strategy_half_life_hours', 0):.1f}h, "
            f"mutation_dominance={mutation_fitness.get('dominant_family', 'none')}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 29A — TRADE QUALITY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_trade_quality(self) -> dict:
        """Analyze trade quality metrics: expectancy, win/loss asymmetry, slippage-adjusted edge.

        Uses paper_trades columns: time, side, quantity, price, fill_price, pnl.
        Computes pnl_pct from pnl / notional, spread_bps from fill vs price diff.
        """
        result = {
            "expectancy": 0.0,
            "win_loss_asymmetry": 0.0,
            "avg_holding_efficiency": 0.0,
            "slippage_adjusted_edge": 0.0,
            "risk_adjusted_return": 0.0,
            "trade_clustering": 0.0,
            "n_trades_analyzed": 0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Fetch recent paper trades — paper_trades has: time, strategy_id, symbol,
                # side, quantity, price, fill_price, status, pnl.  No pnl_pct, bars_held,
                # spread_bps, or direction columns — we compute them on the fly.
                r = await conn.execute(text("""
                    SELECT
                        COUNT(*)                                                          as n_trades,
                        COALESCE(AVG(pnl / NULLIF(quantity * price, 0)), 0)               as avg_return,
                        COALESCE(STDDEV(pnl / NULLIF(quantity * price, 0)), 0)            as return_std,
                        COALESCE(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END), 0)         as win_rate,
                        COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl / NULLIF(quantity * price, 0) ELSE 0 END), 0) as avg_win,
                        COALESCE(AVG(CASE WHEN pnl <= 0 THEN pnl / NULLIF(quantity * price, 0) ELSE 0 END), 0) as avg_loss,
                        COALESCE(AVG(ABS(COALESCE(fill_price, price) - price) / NULLIF(price, 0) * 10000), 0)  as avg_spread_bps
                    FROM paper_trades
                    WHERE time > NOW() - INTERVAL '24 hours'
                """))
                row = r.fetchone()
                if not row or (row[0] or 0) < self.MIN_TRADES_FOR_ANALYSIS:
                    return result

                n_trades = int(row[0] or 0)
                avg_return = float(row[1] or 0)
                return_std = float(row[2] or 0)
                win_rate = float(row[3] or 0)
                avg_win = float(row[4] or 0)
                avg_loss = abs(float(row[5] or 0))
                avg_spread = float(row[6] or 0)

                # Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
                expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

                # Win/Loss Asymmetry = Avg Win / Avg Loss (1.0 = symmetric)
                win_loss_asym = avg_win / max(0.0001, avg_loss)

                # Slippage-adjusted edge: expectancy - (spread/2)
                slippage_edge = expectancy - (avg_spread / 2 / 10000)

                # Risk-adjusted return: Sharpe-like (sqrt(96) for ~quarter-hour bars)
                risk_adj = avg_return / max(0.0001, return_std) * math.sqrt(96) if return_std > 0 else 0

                # Trade clustering: how clustered trades are (0 = uniform, 1 = highly clustered)
                trade_clustering = 0.0
                if n_trades > 1:
                    r2 = await conn.execute(text("""
                        SELECT COALESCE(STDDEV(trade_count), 0) / NULLIF(AVG(trade_count), 0) as clustering
                        FROM (
                            SELECT COUNT(*) as trade_count
                            FROM paper_trades
                            WHERE time > NOW() - INTERVAL '24 hours'
                            GROUP BY DATE_TRUNC('hour', time)
                        ) hourly
                    """))
                    cluster_row = r2.fetchone()
                    if cluster_row:
                        trade_clustering = min(1.0, float(cluster_row[0] or 0))

                result.update({
                    "expectancy": round(expectancy, 6),
                    "win_loss_asymmetry": round(win_loss_asym, 4),
                    "avg_holding_efficiency": round(avg_return / max(1, n_trades) * 100, 6),
                    "slippage_adjusted_edge": round(slippage_edge, 6),
                    "risk_adjusted_return": round(risk_adj, 4),
                    "trade_clustering": round(trade_clustering, 4),
                    "n_trades_analyzed": n_trades,
                })

        except Exception as e:
            logger.debug(f"{self.name}: Trade quality analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29A — CAPITAL EFFICIENCY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_capital_efficiency(self) -> dict:
        """Analyze capital efficiency: return per drawdown, return per exposure, velocity, stagnation."""
        result = {
            "return_per_unit_drawdown": 0.0,
            "return_per_unit_exposure": 0.0,
            "capital_velocity": 0.0,
            "capital_stagnation": 0.0,
            "leverage_efficiency": 1.0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Get portfolio P&L and exposure metrics
                r = await conn.execute(text("""
                    SELECT
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COALESCE(AVG(ABS(pnl)), 0) as avg_abs_pnl,
                        COALESCE(SUM(ABS(quantity * price)), 0) as total_exposure_dollar,
                        COUNT(*) as n_trades
                    FROM paper_trades
                    WHERE time > NOW() - INTERVAL '24 hours'
                """))
                row = r.fetchone()
                if not row or (row[3] or 0) < self.MIN_TRADES_FOR_ANALYSIS:
                    return result

                total_pnl = float(row[0] or 0)
                avg_abs_pnl = float(row[1] or 0)
                total_exposure = float(row[2] or 0)
                n_trades = int(row[3] or 0)

                # Get max drawdown
                r2 = await conn.execute(text("""
                    SELECT COALESCE(MAX(drawdown_pct), 0)
                    FROM capital_preservation_state
                    WHERE checked_at > NOW() - INTERVAL '24 hours'
                """))
                dd_row = r2.fetchone()
                max_drawdown = float(dd_row[0] or 0) + 0.0001

                # Get initial capital estimate
                r3 = await conn.execute(text("""
                    SELECT COALESCE(AVG(peak_value), 100000)
                    FROM capital_preservation_state
                    WHERE checked_at > NOW() - INTERVAL '24 hours'
                """))
                peak_row = r3.fetchone()
                peak_capital = float(peak_row[0] or 100000)

                # Return per unit drawdown
                ret_per_dd = total_pnl / max(1, peak_capital * max_drawdown)

                # Return per unit exposure
                ret_per_exp = total_pnl / max(1, total_exposure)

                # Capital velocity: how frequently capital is deployed
                velocity = n_trades / max(1, total_exposure / max(1, peak_capital)) if peak_capital > 0 else 0

                # Capital stagnation: periods with no trades as fraction of total time
                r4 = await conn.execute(text("""
                    SELECT
                        EXTRACT(EPOCH FROM NOW() - MIN(time)) / 3600 as total_hours,
                        COUNT(*) as n_hours_with_trades
                    FROM (
                        SELECT DISTINCT DATE_TRUNC('hour', time) as time
                        FROM paper_trades
                        WHERE time > NOW() - INTERVAL '24 hours'
                    ) hourly
                """))
                stag_row = r4.fetchone()
                stagnation = 0.0
                if stag_row and stag_row[0] and stag_row[0] > 0:
                    total_hours = float(stag_row[0] or 24)
                    active_hours = int(stag_row[1] or 0)
                    stagnation = 1.0 - (active_hours / max(1, total_hours))

                # Leverage efficiency
                leverage_eff = 1.0
                r5 = await conn.execute(text("""
                    SELECT COALESCE(AVG(leverage_cap_applied), 1.0)
                    FROM capital_allocation
                    WHERE computed_at > NOW() - INTERVAL '24 hours'
                """))
                lev_row = r5.fetchone()
                if lev_row:
                    leverage_eff = min(1.0, float(lev_row[0] or 1.0))

                result.update({
                    "return_per_unit_drawdown": round(ret_per_dd, 6),
                    "return_per_unit_exposure": round(ret_per_exp, 6),
                    "capital_velocity": round(velocity, 4),
                    "capital_stagnation": round(stagnation, 4),
                    "leverage_efficiency": round(leverage_eff, 4),
                })

        except Exception as e:
            logger.debug(f"{self.name}: Capital efficiency analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29A — SURVIVAL QUALITY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_survival_quality(self) -> dict:
        """Analyze survival quality: strategy half-life, mutation survival rate, regime persistence."""
        result = {
            "avg_strategy_half_life_hours": 0.0,
            "mutation_survival_rate": 0.0,
            "regime_persistence": 0.0,
            "drawdown_recovery_speed": 0.0,
            "portfolio_recovery_time_hours": 0.0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Strategy half-life: median age of strategies before retirement/death
                r = await conn.execute(text("""
                    SELECT
                        COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age_bars), 0) as median_age_bars,
                        COUNT(*) as n_strategies
                    FROM strategies
                    WHERE lifecycle_state IN ('retired', 'dead', 'monitor')
                      AND created_at > NOW() - INTERVAL '7 days'
                """))
                row = r.fetchone()
                if row and row[1] and int(row[1]) > 0:
                    median_age_bars = float(row[0] or 0)
                    half_life_hours = median_age_bars / 60  # Assuming 1m bars
                    result["avg_strategy_half_life_hours"] = round(half_life_hours, 2)

                # Mutation survival rate
                r2 = await conn.execute(text("""
                    SELECT COALESCE(AVG(survival_rate), 0)
                    FROM mutation_survival_log
                """))
                surv_row = r2.fetchone()
                if surv_row:
                    result["mutation_survival_rate"] = round(float(surv_row[0] or 0), 4)

                # Regime persistence: how consistently strategies survive across regimes
                r3 = await conn.execute(text("""
                    SELECT
                        COUNT(DISTINCT regime) as n_regimes,
                        COALESCE(AVG(regime_fitness_score), 0) as avg_regime_fitness
                    FROM regime_fitness_log
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """))
                reg_row = r3.fetchone()
                if reg_row:
                    n_regimes = int(reg_row[0] or 0)
                    avg_fitness = float(reg_row[1] or 0)
                    persistence = (n_regimes / max(1, 5)) * min(1.0, avg_fitness / 10)
                    result["regime_persistence"] = round(min(1.0, persistence), 4)

                # Drawdown recovery speed
                r4 = await conn.execute(text("""
                    WITH dd_events AS (
                        SELECT
                            checked_at,
                            drawdown_pct,
                            LAG(drawdown_pct) OVER (ORDER BY checked_at) as prev_dd,
                            EXTRACT(EPOCH FROM checked_at - LAG(checked_at) OVER (ORDER BY checked_at)) / 3600 as hours_since_prev
                        FROM capital_preservation_state
                        WHERE checked_at > NOW() - INTERVAL '7 days'
                    )
                    SELECT
                        COALESCE(AVG(
                            CASE WHEN drawdown_pct < 0.05 AND prev_dd >= 0.10
                            THEN hours_since_prev
                            ELSE NULL END
                        ), 0) as avg_recovery_hours
                    FROM dd_events
                """))
                rec_row = r4.fetchone()
                if rec_row:
                    recovery_hours = float(rec_row[0] or 0)
                    result["drawdown_recovery_speed"] = round(max(0, 1.0 - (recovery_hours / 168)), 4)  # Normalized to 1 week
                    if recovery_hours > 0:
                        result["portfolio_recovery_time_hours"] = round(recovery_hours, 2)

        except Exception as e:
            logger.debug(f"{self.name}: Survival quality analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29A — SCOUT QUALITY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_scout_quality(self) -> dict:
        """Analyze scout intelligence quality: predictive contribution, contradiction rate, SNR."""
        result = {
            "predictive_contribution": 0.0,
            "contradiction_rate": 0.0,
            "signal_to_noise_ratio": 0.0,
            "economic_attribution_quality": 0.0,
            "n_scouts_analyzed": 0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Predictive contribution: how often scout signals led to profitable outcomes
                r = await conn.execute(text("""
                    SELECT
                        COUNT(*) as n_attributions,
                        COALESCE(AVG(CASE WHEN survived_validation THEN 1 ELSE 0 END), 0) as survival_rate,
                        COALESCE(AVG(sharpe_contribution), 0) as avg_sharpe_contrib,
                        COALESCE(AVG(pnl_contribution), 0) as avg_pnl_contrib
                    FROM scout_economic_attribution
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """))
                row = r.fetchone()
                if row and row[0] and int(row[0]) > 0:
                    n_attr = int(row[0] or 0)
                    survival_rate = float(row[1] or 0)
                    avg_sharpe = float(row[2] or 0)
                    avg_pnl = float(row[3] or 0)
                    result["predictive_contribution"] = round(survival_rate, 4)
                    result["economic_attribution_quality"] = round(
                        (survival_rate * avg_sharpe + abs(avg_pnl) * 10) / 2, 4
                    )
                    result["n_scouts_analyzed"] = n_attr

                # Contradiction rate
                r2 = await conn.execute(text("""
                    SELECT COALESCE(AVG(recent_contradiction_rate), 0)
                    FROM source_performance_log
                """))
                contra_row = r2.fetchone()
                if contra_row:
                    result["contradiction_rate"] = round(float(contra_row[0] or 0), 4)

                # Signal-to-noise ratio: profitable signals vs total
                r3 = await conn.execute(text("""
                    SELECT
                        CASE WHEN SUM(n_profitable_signals + n_loss_signals) > 0
                        THEN SUM(n_profitable_signals)::numeric / NULLIF(SUM(n_profitable_signals + n_loss_signals), 0)
                        ELSE 0 END as snr
                    FROM source_performance_log
                """))
                snr_row = r3.fetchone()
                if snr_row:
                    snr = float(snr_row[0] or 0)
                    # Scale from [0,1] to meaningful SNR: 0.5 = random, 1.0 = perfect
                    result["signal_to_noise_ratio"] = round((snr - 0.5) * 2, 4)

        except Exception as e:
            logger.debug(f"{self.name}: Scout quality analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29B — LONG-HORIZON FITNESS LEARNING (rolling windows)
    # ══════════════════════════════════════════════════════════════════════════

    async def _compute_fitness_windows(self) -> dict:
        """Compute fitness metrics over multiple rolling windows: 1h, 6h, 24h."""
        windows = {}
        for hours in self.FITNESS_WINDOWS_HOURS:
            window_key = f"{hours}h"
            window_data = await self._compute_fitness_for_window(hours)
            windows[window_key] = window_data
        return windows

    async def _compute_fitness_for_window(self, hours: int) -> dict:
        """Compute fitness metrics for a given lookback window in hours."""
        data = {
            "n_strategies": 0,
            "avg_composite_fitness": 0.0,
            "avg_sharpe": 0.0,
            "avg_sortino": 0.0,
            "avg_calmar": 0.0,
            "avg_expectancy": 0.0,
            "median_composite_fitness": 0.0,
            "top_decile_fitness": 0.0,
            "bottom_decile_fitness": 0.0,
            "fitness_trend": 0.0,
            "mutation_survival_rate": 0.0,
            "scout_attribution_quality": 0.0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Aggregate backtest metrics
                r = await conn.execute(text(f"""
                    SELECT
                        COUNT(*) as n_strategies,
                        COALESCE(AVG(composite_fitness_score), 0) as avg_fitness,
                        COALESCE(AVG(COALESCE((results->>'sharpe')::numeric, 0)), 0) as avg_sharpe,
                        COALESCE(AVG(sortino_ratio), 0) as avg_sortino,
                        COALESCE(AVG(calmar_ratio), 0) as avg_calmar,
                        COALESCE(AVG(expectancy), 0) as avg_expectancy,
                        COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY composite_fitness_score), 0) as median_fit,
                        COALESCE(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY composite_fitness_score), 0) as top10_fit,
                        COALESCE(PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY composite_fitness_score), 0) as bot10_fit
                    FROM backtest_results
                    WHERE created_at > NOW() - INTERVAL '{hours} hours'
                """))
                row = r.fetchone()
                if row and row[0] and int(row[0]) > 0:
                    data.update({
                        "n_strategies": int(row[0]),
                        "avg_composite_fitness": round(float(row[1] or 0), 4),
                        "avg_sharpe": round(float(row[2] or 0), 4),
                        "avg_sortino": round(float(row[3] or 0), 4),
                        "avg_calmar": round(float(row[4] or 0), 4),
                        "avg_expectancy": round(float(row[5] or 0), 6),
                        "median_composite_fitness": round(float(row[6] or 0), 4),
                        "top_decile_fitness": round(float(row[7] or 0), 4),
                        "bottom_decile_fitness": round(float(row[8] or 0), 4),
                    })

                # Mutation survival rate for this window
                r2 = await conn.execute(text(f"""
                    SELECT COALESCE(AVG(survival_rate), 0)
                    FROM mutation_survival_log
                    WHERE updated_at > NOW() - INTERVAL '{hours} hours'
                """))
                surv_row = r2.fetchone()
                if surv_row:
                    data["mutation_survival_rate"] = round(float(surv_row[0] or 0), 4)

                # Scout attribution quality for this window
                r3 = await conn.execute(text(f"""
                    SELECT
                        COALESCE(AVG(CASE WHEN survived_validation THEN sharpe_contribution ELSE -sharpe_contribution END), 0)
                    FROM scout_economic_attribution
                    WHERE created_at > NOW() - INTERVAL '{hours} hours'
                """))
                attr_row = r3.fetchone()
                if attr_row:
                    data["scout_attribution_quality"] = round(float(attr_row[0] or 0), 4)

        except Exception as e:
            logger.debug(f"{self.name}: Fitness window {hours}h error: {e}")

        # Trend: compare to previous period if we have cached data
        prev_key = f"prev_{hours}h"
        if hasattr(self, prev_key):
            prev = getattr(self, prev_key, {})
            if prev.get("avg_composite_fitness", 0) > 0:
                current = data["avg_composite_fitness"]
                prev_val = prev["avg_composite_fitness"]
                data["fitness_trend"] = round((current - prev_val) / abs(prev_val + 0.0001), 4)

        # Cache for next cycle
        setattr(self, prev_key, data)
        return data

    async def _persist_fitness_windows(self, windows: dict) -> None:
        """Persist rolling fitness window data."""
        now = datetime.now(timezone.utc)
        for window_hours, data in windows.items():
            try:
                await self.db._execute_insert(
                    """
                    INSERT INTO economic_fitness_windows
                        (id, window_hours, computed_at, n_strategies, avg_composite_fitness,
                         avg_sharpe, avg_sortino, avg_calmar, avg_expectancy,
                         median_composite_fitness, top_decile_fitness, bottom_decile_fitness,
                         fitness_trend, mutation_survival_rate, scout_attribution_quality, metadata)
                    VALUES
                        (:id, :window_hours, :computed_at, :n_strategies, :avg_composite_fitness,
                         :avg_sharpe, :avg_sortino, :avg_calmar, :avg_expectancy,
                         :median_fitness, :top_fitness, :bottom_fitness,
                         :trend, :mutation_survival, :scout_attribution, :metadata)
                    """,
                    {
                        "id": self.select_trace_id(),
                        "window_hours": int(window_hours.replace("h", "")),
                        "computed_at": now,
                        "n_strategies": data["n_strategies"],
                        "avg_composite_fitness": data["avg_composite_fitness"],
                        "avg_sharpe": data["avg_sharpe"],
                        "avg_sortino": data["avg_sortino"],
                        "avg_calmar": data["avg_calmar"],
                        "avg_expectancy": data["avg_expectancy"],
                        "median_fitness": data["median_composite_fitness"],
                        "top_fitness": data["top_decile_fitness"],
                        "bottom_fitness": data["bottom_decile_fitness"],
                        "trend": data["fitness_trend"],
                        "mutation_survival": data["mutation_survival_rate"],
                        "scout_attribution": data["scout_attribution_quality"],
                        "metadata": safe_json_dumps({"agent": self.name}),
                    },
                )
            except Exception as e:
                logger.debug(f"{self.name}: Persist fitness window {window_hours} failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # 29C — CAPITAL PRESERVATION ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_capital_preservation(self) -> dict:
        """Analyze drawdown persistence, recovery behavior, cascading failure, concentration instability."""
        result = {
            "current_drawdown_pct": 0.0,
            "max_drawdown_24h": 0.0,
            "drawdown_persistence_hours": 0.0,
            "recovery_efficiency": 1.0,
            "cascading_failure_risk": 0.0,
            "concentration_instability": 0.0,
            "leverage_instability": 0.0,
            "portfolio_contagion_risk": 0.0,
            "action_taken": "none",
        }
        try:
            async with self.db.engine.connect() as conn:
                # Current drawdown state
                r = await conn.execute(text("""
                    SELECT drawdown_pct, action_taken
                    FROM capital_preservation_state
                    ORDER BY checked_at DESC LIMIT 1
                """))
                row = r.fetchone()
                if row:
                    result["current_drawdown_pct"] = round(float(row[0] or 0), 4)
                    result["action_taken"] = str(row[1] or "none")

                # Max drawdown in last 24h
                r2 = await conn.execute(text("""
                    SELECT COALESCE(MAX(drawdown_pct), 0)
                    FROM capital_preservation_state
                    WHERE checked_at > NOW() - INTERVAL '24 hours'
                """))
                dd_row = r2.fetchone()
                if dd_row:
                    result["max_drawdown_24h"] = round(float(dd_row[0] or 0), 4)

                # Drawdown persistence: how long drawdown has been sustained above warning level
                r3 = await conn.execute(text("""
                    WITH dd_periods AS (
                        SELECT
                            checked_at, drawdown_pct,
                            CASE WHEN drawdown_pct >= :dd_warn THEN 1 ELSE 0 END as in_dd
                        FROM capital_preservation_state
                        WHERE checked_at > NOW() - INTERVAL '7 days'
                        ORDER BY checked_at DESC
                    ),
                    dd_streaks AS (
                        SELECT checked_at, in_dd,
                               SUM(CASE WHEN in_dd = 0 THEN 1 ELSE 0 END) OVER (ORDER BY checked_at DESC ROWS UNBOUNDED PRECEDING) as streak_id
                        FROM dd_periods
                    )
                    SELECT COALESCE(EXTRACT(EPOCH FROM MAX(checked_at) - MIN(checked_at)) / 3600, 0) as persistence_hours
                    FROM dd_streaks
                    WHERE in_dd = 1
                    GROUP BY streak_id
                    ORDER BY persistence_hours DESC
                    LIMIT 1
                """), {"dd_warn": self.DD_WARNING})
                persist_row = r3.fetchone()
                if persist_row:
                    result["drawdown_persistence_hours"] = round(float(persist_row[0] or 0), 2)

                # Recovery efficiency: how quickly capital recovers after drawdown
                r4 = await conn.execute(text("""
                    SELECT
                        CASE
                            WHEN SUM(CASE WHEN drawdown_pct < 0.02 AND prev_dd > 0.08 THEN 1 ELSE 0 END) > 0
                            THEN AVG(CASE WHEN drawdown_pct < 0.02 AND prev_dd > 0.08 THEN recovery_hours ELSE NULL END)
                            ELSE 0
                        END as avg_recovery_hours
                    FROM (
                        SELECT
                            checked_at, drawdown_pct,
                            LAG(drawdown_pct) OVER (ORDER BY checked_at) as prev_dd,
                            EXTRACT(EPOCH FROM checked_at - LAG(checked_at) OVER (ORDER BY checked_at)) / 3600 as recovery_hours
                        FROM capital_preservation_state
                        WHERE checked_at > NOW() - INTERVAL '7 days'
                    ) sub
                """))
                rec_row = r4.fetchone()
                if rec_row and rec_row[0] and float(rec_row[0]) > 0:
                    avg_rec_hours = float(rec_row[0] or 0)
                    result["recovery_efficiency"] = round(max(0.0, 1.0 - (avg_rec_hours / 72)), 4)  # 72h = full failure

                # Cascading failure risk: correlation between strategy failures
                r5 = await conn.execute(text("""
                    WITH hourly_failures AS (
                        SELECT
                            DATE_TRUNC('hour', created_at) AS hour_bucket,
                            SUM(CASE WHEN lifecycle_state IN ('failed', 'dead') THEN 1 ELSE 0 END) AS failure_count
                        FROM strategies
                        WHERE created_at > NOW() - INTERVAL '7 days'
                        GROUP BY DATE_TRUNC('hour', created_at)
                    )
                    SELECT
                        CASE WHEN COUNT(*) > 1
                        THEN COALESCE(CORR(failure_count, prev_failure_count), 0)
                        ELSE 0 END AS cascade_corr
                    FROM (
                        SELECT
                            hour_bucket,
                            failure_count,
                            LAG(failure_count) OVER (ORDER BY hour_bucket) AS prev_failure_count
                        FROM hourly_failures
                    ) sub
                """))
                cascade_row = r5.fetchone()
                if cascade_row:
                    result["cascading_failure_risk"] = round(max(0.0, float(cascade_row[0] or 0)), 4)

                # Concentration instability
                r6 = await conn.execute(text("""
                    SELECT COALESCE(concentration_risk, 0)
                    FROM portfolio_intelligence
                    ORDER BY computed_at DESC LIMIT 1
                """))
                conc_row = r6.fetchone()
                if conc_row:
                    result["concentration_instability"] = round(float(conc_row[0] or 0), 4)

                # Portfolio contagion risk
                r7 = await conn.execute(text("""
                    SELECT COALESCE(contagion_exposure, 0)
                    FROM portfolio_evolution_log
                    ORDER BY created_at DESC LIMIT 1
                """))
                contagion_row = r7.fetchone()
                if contagion_row:
                    result["portfolio_contagion_risk"] = round(float(contagion_row[0] or 0), 4)

                # Leverage instability
                r8 = await conn.execute(text("""
                    SELECT COALESCE(STDDEV(leverage_cap_applied), 0)
                    FROM capital_allocation
                    WHERE computed_at > NOW() - INTERVAL '7 days'
                """))
                lev_row = r8.fetchone()
                if lev_row:
                    result["leverage_instability"] = round(min(1.0, float(lev_row[0] or 0)), 4)

        except Exception as e:
            logger.debug(f"{self.name}: Capital preservation analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29D — REGIME SPECIALIZATION DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    async def _detect_regime_specialization(self) -> dict:
        """Identify dominant regime specialists, fragile organisms, cross-regime survivors."""
        result = {
            "regime_specialists": {},
            "fragile_organisms": [],
            "cross_regime_survivors": 0,
            "volatility_sensitive": [],
            "liquidity_sensitive": [],
        }
        try:
            async with self.db.engine.connect() as conn:
                # Per-regime fitness analysis
                r = await conn.execute(text("""
                    SELECT
                        regime,
                        COUNT(*) as n_observations,
                        COALESCE(AVG(regime_fitness_score), 0) as avg_fitness,
                        COALESCE(AVG(sharpe), 0) as avg_sharpe,
                        COALESCE(AVG(sortino), 0) as avg_sortino,
                        COALESCE(AVG(win_rate), 0) as avg_win_rate,
                        COALESCE(AVG(max_drawdown), 0) as avg_drawdown,
                        COALESCE(SUM(total_trades), 0) as total_trades
                    FROM regime_fitness_log
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    GROUP BY regime
                    HAVING COUNT(*) >= 3
                    ORDER BY avg_fitness DESC
                """))

                regimes = {}
                for row in r.fetchall():
                    regime_name = str(row[0])
                    regimes[regime_name] = {
                        "n_observations": int(row[1]),
                        "avg_fitness": round(float(row[2] or 0), 4),
                        "avg_sharpe": round(float(row[3] or 0), 4),
                        "avg_sortino": round(float(row[4] or 0), 4),
                        "avg_win_rate": round(float(row[5] or 0), 4),
                        "avg_drawdown": round(float(row[6] or 0), 4),
                        "total_trades": int(row[7] or 0),
                    }

                result["regime_specialists"] = regimes

                # Identify fragile organisms: strategies that only survive in one regime
                r2 = await conn.execute(text("""
                    SELECT strategy_id, COUNT(DISTINCT regime) as n_regimes_survived
                    FROM regime_fitness_log
                    WHERE created_at > NOW() - INTERVAL '7 days'
                      AND regime_fitness_score > 0
                    GROUP BY strategy_id
                    HAVING COUNT(DISTINCT regime) = 1
                    ORDER BY COUNT(DISTINCT regime) ASC
                    LIMIT 20
                """))
                fragile = [str(r2[0]) for r2 in r2.fetchall()]
                result["fragile_organisms"] = fragile

                # Cross-regime survivors: strategies surviving in >= 3 regimes
                r3 = await conn.execute(text("""
                    SELECT COUNT(DISTINCT strategy_id)
                    FROM (
                        SELECT strategy_id, COUNT(DISTINCT regime) as n_regimes
                        FROM regime_fitness_log
                        WHERE created_at > NOW() - INTERVAL '7 days'
                          AND regime_fitness_score > 0
                        GROUP BY strategy_id
                        HAVING COUNT(DISTINCT regime) >= 3
                    ) multi_regime
                """))
                cross_row = r3.fetchone()
                if cross_row:
                    result["cross_regime_survivors"] = int(cross_row[0] or 0)

                # Volatility-sensitive strategies
                r4 = await conn.execute(text("""
                    SELECT DISTINCT strategy_id
                    FROM regime_fitness_log
                    WHERE regime ILIKE '%high_vol%' OR regime ILIKE '%panic%'
                      AND regime_fitness_score < 0
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 20
                """))
                vol_sensitive = [str(r4[0]) for r4 in r4.fetchall()]
                result["volatility_sensitive"] = vol_sensitive

                # Liquidity-sensitive strategies
                r5 = await conn.execute(text("""
                    SELECT DISTINCT strategy_id
                    FROM regime_fitness_log
                    WHERE (regime ILIKE '%low_liq%' OR regime ILIKE '%thin%')
                      AND regime_fitness_score < 0
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 20
                """))
                liq_sensitive = [str(r5[0]) for r5 in r5.fetchall()]
                result["liquidity_sensitive"] = liq_sensitive

        except Exception as e:
            logger.debug(f"{self.name}: Regime specialization detection error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29E — MUTATION FITNESS EVOLUTION
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_mutation_fitness(self) -> dict:
        """Track mutation family dominance, collapse rates, lineage survival."""
        result = {
            "mutation_families": {},
            "dominant_family": "none",
            "collapsing_families": [],
            "avg_lineage_survival": 0.0,
            "exploration_vs_exploitation": 0.5,
            "entropy_conditioned_success": {},
        }
        try:
            async with self.db.engine.connect() as conn:
                # Per-mutation-type survival analysis
                r = await conn.execute(text("""
                    SELECT
                        mutation_type,
                        SUM(total_applications) as total,
                        SUM(survival_count) as survived,
                        COALESCE(AVG(survival_rate), 0) as avg_survival_rate,
                        COALESCE(AVG(avg_fitness_contribution), 0) as avg_fitness_contribution,
                        CASE WHEN SUM(total_applications) > 0
                        THEN SUM(survival_count)::numeric / SUM(total_applications)
                        ELSE 0 END as weighted_survival
                    FROM mutation_survival_log
                    GROUP BY mutation_type
                    ORDER BY weighted_survival DESC
                """))

                families = {}
                total_apps = 0
                for row in r.fetchall():
                    mtype = str(row[0])
                    total = int(row[1] or 0)
                    survived = int(row[2] or 0)
                    surv_rate = float(row[3] or 0)
                    fitness_contrib = float(row[4] or 0)
                    weighted = float(row[5] or 0)
                    total_apps += total
                    families[mtype] = {
                        "total_applications": total,
                        "survived": survived,
                        "survival_rate": round(surv_rate, 4),
                        "avg_fitness_contribution": round(fitness_contrib, 4),
                        "weighted_survival": round(weighted, 4),
                        "market_share": 0.0,
                    }

                # Compute market share for each family
                if total_apps > 0:
                    for mtype in families:
                        families[mtype]["market_share"] = round(
                            families[mtype]["total_applications"] / total_apps, 4
                        )

                result["mutation_families"] = families

                # Dominant family: highest market share with survival rate above threshold
                dominant = "none"
                for mtype, data in sorted(
                    families.items(),
                    key=lambda x: x[1]["market_share"] * x[1]["survival_rate"],
                    reverse=True,
                ):
                    if data["market_share"] >= self.DOMINANCE_THRESHOLD:
                        dominant = mtype
                        break
                result["dominant_family"] = dominant

                # Collapsing families: high market share but low survival
                collapsing = []
                for mtype, data in families.items():
                    if data["survival_rate"] < self.MUTATION_COLLAPSE_THRESHOLD and data["total_applications"] > 5:
                        collapsing.append(mtype)
                result["collapsing_families"] = collapsing

                # Average lineage survival
                r2 = await conn.execute(text("""
                    SELECT COALESCE(AVG(survival_rate), 0)
                    FROM mutation_survival_log
                """))
                surv_row = r2.fetchone()
                if surv_row:
                    result["avg_lineage_survival"] = round(float(surv_row[0] or 0), 4)

                # Exploration vs exploitation: entropy of mutation distribution
                if families:
                    rates = [f["market_share"] for f in families.values() if f["market_share"] > 0]
                    if rates:
                        entropy = -sum(p * math.log2(p) for p in rates)
                        max_entropy = math.log2(len(rates))
                        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.5
                        result["exploration_vs_exploitation"] = round(normalized_entropy, 4)

                # Entropy-conditioned success: survival rate per mutation type by entropy regime
                # (proxy: survival rate already captures this)

        except Exception as e:
            logger.debug(f"{self.name}: Mutation fitness analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29F — SCOUT PREDICTIVE VALUE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_scout_predictive_value(self) -> dict:
        """Rank scouts by economic contribution. Measure predictive persistence, contradiction penalties."""
        result = {
            "scout_rankings": {},
            "top_scout": "none",
            "worst_scout": "none",
            "predictive_divergence": 0.0,
            "avg_contradiction_penalty": 0.0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Per-scout economic contribution
                r = await conn.execute(text("""
                    SELECT
                        source_scout,
                        COUNT(*) as n_attributions,
                        COALESCE(AVG(CASE WHEN survived_validation THEN 1 ELSE 0 END), 0) as survival_rate,
                        COALESCE(AVG(sharpe_contribution), 0) as avg_sharpe_contrib,
                        COALESCE(AVG(pnl_contribution), 0) as avg_pnl_contrib,
                        COALESCE(AVG(drawdown_contribution), 0) as avg_drawdown_contrib,
                        COALESCE(AVG(attribution_weight), 0) as avg_attribution_weight,
                        COALESCE(SUM(CASE WHEN survived_validation THEN 1 ELSE 0 END), 0) as n_survived
                    FROM scout_economic_attribution
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    GROUP BY source_scout
                    ORDER BY survival_rate DESC, avg_sharpe_contrib DESC
                """))

                rankings = {}
                for row in r.fetchall():
                    scout_name = str(row[0])
                    n_attr = int(row[1] or 0)
                    survival = float(row[2] or 0)
                    sharpe_contrib = float(row[3] or 0)
                    pnl_contrib = float(row[4] or 0)
                    dd_contrib = abs(float(row[5] or 0))
                    weight = float(row[6] or 0)
                    n_survived = int(row[7] or 0)

                    # Composite economic score
                    eco_score = (
                        survival * 0.3 +
                        max(-0.2, min(0.2, sharpe_contrib)) * 0.3 +
                        max(-0.2, min(0.2, pnl_contrib)) * 0.2 +
                        (1.0 - min(1.0, dd_contrib)) * 0.2
                    )

                    # Contradiction penalty
                    r2 = await conn.execute(text("""
                        SELECT COALESCE(AVG(recent_contradiction_rate), 0)
                        FROM source_performance_log
                        WHERE source = :scout
                    """), {"scout": scout_name})
                    contra_row = r2.fetchone()
                    contradiction_rate = float(contra_row[0] or 0) if contra_row else 0

                    penalty = contradiction_rate * self.SCOUT_CONTRADICTION_PENALTY
                    eco_score_penalized = eco_score * (1.0 - penalty)

                    rankings[scout_name] = {
                        "n_attributions": n_attr,
                        "survival_rate": round(survival, 4),
                        "avg_sharpe_contribution": round(sharpe_contrib, 4),
                        "avg_pnl_contribution": round(pnl_contrib, 6),
                        "avg_drawdown_contribution": round(dd_contrib, 4),
                        "avg_attribution_weight": round(weight, 4),
                        "n_survived": n_survived,
                        "contradiction_rate": round(contradiction_rate, 4),
                        "economic_score": round(eco_score, 4),
                        "economic_score_penalized": round(eco_score_penalized, 4),
                    }

                result["scout_rankings"] = rankings

                if rankings:
                    sorted_scouts = sorted(
                        rankings.items(),
                        key=lambda x: x[1]["economic_score_penalized"],
                        reverse=True,
                    )
                    result["top_scout"] = sorted_scouts[0][0] if sorted_scouts else "none"
                    result["worst_scout"] = sorted_scouts[-1][0] if len(sorted_scouts) > 1 else "none"

                    # Predictive divergence: std of economic scores
                    scores = [s["economic_score_penalized"] for s in rankings.values()]
                    if scores:
                        mean_score = sum(scores) / len(scores)
                        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
                        result["predictive_divergence"] = round(math.sqrt(variance), 4)

                    # Average contradiction penalty
                    contra_rates = [s["contradiction_rate"] for s in rankings.values()]
                    result["avg_contradiction_penalty"] = round(
                        sum(contra_rates) / len(contra_rates) * self.SCOUT_CONTRADICTION_PENALTY, 4
                    ) if contra_rates else 0.0

        except Exception as e:
            logger.debug(f"{self.name}: Scout predictive value analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 29G — EXECUTION REALISM ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_execution_realism(self) -> dict:
        """Analyze slippage realism, execution latency, fill quality, liquidity degradation."""
        result = {
            "avg_slippage_bps": 0.0,
            "avg_fill_probability": 1.0,
            "avg_latency_ms": 0.0,
            "execution_degradation": 0.0,
            "spread_sensitivity": 0.0,
            "liquidity_degradation_trend": 0.0,
            "simulated_vs_actual_slippage": 0.0,
        }
        try:
            async with self.db.engine.connect() as conn:
                # Latest execution realism simulation
                r = await conn.execute(text("""
                    SELECT
                        avg_expected_slippage_bps,
                        avg_fill_probability,
                        avg_simulated_latency_ms,
                        execution_degradation_score
                    FROM execution_realism
                    ORDER BY simulated_at DESC LIMIT 1
                """))
                row = r.fetchone()
                if row:
                    result["avg_slippage_bps"] = round(float(row[0] or 0), 4)
                    result["avg_fill_probability"] = round(float(row[1] or 0), 4)
                    result["avg_latency_ms"] = round(float(row[2] or 0), 2)
                    result["execution_degradation"] = round(float(row[3] or 0), 4)

                # Spread sensitivity: correlation between spread width and execution quality
                r2 = await conn.execute(text("""
                    SELECT
                        CASE WHEN COUNT(*) > 1
                        THEN COALESCE(CORR(avg_slippage_bps, fill_quality_score), 0)
                        ELSE 0 END as spread_sensitivity
                    FROM execution_intelligence
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                """))
                sens_row = r2.fetchone()
                if sens_row:
                    result["spread_sensitivity"] = round(abs(float(sens_row[0] or 0)), 4)

                # Liquidity degradation trend: is fill quality degrading over time?
                r3 = await conn.execute(text("""
                    SELECT
                        CASE WHEN COUNT(*) > 5
                        THEN COALESCE(CORR(
                            EXTRACT(EPOCH FROM simulated_at),
                            execution_degradation_score
                        ), 0)
                        ELSE 0 END as degradation_trend
                    FROM execution_realism
                    WHERE simulated_at > NOW() - INTERVAL '7 days'
                """))
                trend_row = r3.fetchone()
                if trend_row:
                    # Positive correlation = degrading over time
                    result["liquidity_degradation_trend"] = round(float(trend_row[0] or 0), 4)

                # Simulated vs actual slippage: compare execution_realism to actual execution_intelligence
                r4 = await conn.execute(text("""
                    SELECT
                        COALESCE(AVG(er.avg_expected_slippage_bps), 0) as sim_slippage,
                        COALESCE(AVG(ei.avg_slippage_bps), 0) as actual_slippage
                    FROM execution_realism er
                    CROSS JOIN LATERAL (
                        SELECT AVG(avg_slippage_bps) as avg_slippage_bps
                        FROM execution_intelligence
                        WHERE timestamp > NOW() - INTERVAL '1 hour'
                    ) ei
                    WHERE er.simulated_at > NOW() - INTERVAL '1 hour'
                """))
                slippage_row = r4.fetchone()
                if slippage_row:
                    sim_slip = float(slippage_row[0] or 0)
                    actual_slip = float(slippage_row[1] or 0)
                    if actual_slip > 0:
                        result["simulated_vs_actual_slippage"] = round(
                            (sim_slip - actual_slip) / actual_slip, 4
                        )

        except Exception as e:
            logger.debug(f"{self.name}: Execution realism analysis error: {e}")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # TREND DETECTION & PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_economic_trends(self, composite: dict) -> dict:
        """Compare current results to previous cycle and detect significant drift."""
        trends = {}

        # Compare trade quality
        tq = composite.get("trade_quality", {})
        prev_tq = self._prev_trade_quality
        if prev_tq and tq.get("expectancy", 0) != prev_tq.get("expectancy", 0):
            delta = tq.get("expectancy", 0) - prev_tq.get("expectancy", 0)
            if abs(delta) > 0.001:
                trends["expectancy_drift"] = round(delta, 6)
        self._prev_trade_quality = tq

        # Compare capital efficiency
        ce = composite.get("capital_efficiency", {})
        prev_ce = self._prev_capital_efficiency
        if prev_ce and ce.get("return_per_unit_drawdown", 0) != prev_ce.get("return_per_unit_drawdown", 0):
            delta = ce.get("return_per_unit_drawdown", 0) - prev_ce.get("return_per_unit_drawdown", 0)
            if abs(delta) > 0.001:
                trends["capital_efficiency_drift"] = round(delta, 6)
        self._prev_capital_efficiency = ce

        # Compare mutation fitness
        mf = composite.get("mutation_fitness", {})
        prev_mf = self._prev_mutation_fitness
        if prev_mf and mf.get("avg_lineage_survival", 0) != prev_mf.get("avg_lineage_survival", 0):
            delta = mf.get("avg_lineage_survival", 0) - prev_mf.get("avg_lineage_survival", 0)
            if abs(delta) > 0.01:
                trends["mutation_survival_drift"] = round(delta, 4)
        self._prev_mutation_fitness = mf

        return trends

    async def _persist_composite_analysis(self, composite: dict) -> None:
        """Persist the full composite economic analysis to the database."""
        now = datetime.now(timezone.utc)
        analysis_id = self.select_trace_id()

        try:
            # Extract key summary metrics for the composite row
            tq = composite.get("trade_quality", {})
            ce = composite.get("capital_efficiency", {})
            sq = composite.get("survival_quality", {})
            scq = composite.get("scout_quality", {})
            cp = composite.get("capital_preservation", {})
            rs = composite.get("regime_specialization", {})
            mf = composite.get("mutation_fitness", {})
            spv = composite.get("scout_predictive_value", {})
            er = composite.get("execution_realism", {})

            await self.db._execute_insert(
                """
                INSERT INTO economic_efficiency_analysis
                    (id, analyzed_at, expectancy, win_loss_asymmetry, slippage_adjusted_edge,
                     risk_adjusted_return, return_per_drawdown, capital_velocity,
                     strategy_half_life_hours, mutation_survival_rate, regime_persistence,
                     drawdown_persistence_hours, recovery_efficiency, cascading_failure_risk,
                     concentration_instability, portfolio_contagion_risk,
                     dominant_mutation_family, collapsing_families, exploration_ratio,
                     top_scout, worst_scout, predictive_divergence,
                     execution_degradation, spread_sensitivity, liquidity_degradation_trend,
                     composite_analysis, metadata)
                VALUES
                    (:id, :analyzed_at, :expectancy, :win_loss_asym, :slippage_edge,
                     :risk_adj_return, :return_per_dd, :capital_velocity,
                     :half_life_hours, :mutation_survival, :regime_persistence,
                     :dd_persistence_hours, :recovery_eff, :cascade_risk,
                     :concentration_instability, :contagion_risk,
                     :dominant_mutation, :collapsing, :exploration_ratio,
                     :top_scout, :worst_scout, :predictive_divergence,
                     :exec_degradation, :spread_sensitivity, :liq_degradation,
                     CAST(:composite AS jsonb), CAST(:metadata AS jsonb))
                """,
                {
                    "id": analysis_id,
                    "analyzed_at": now,
                    "expectancy": tq.get("expectancy", 0),
                    "win_loss_asym": tq.get("win_loss_asymmetry", 1.0),
                    "slippage_edge": tq.get("slippage_adjusted_edge", 0),
                    "risk_adj_return": tq.get("risk_adjusted_return", 0),
                    "return_per_dd": ce.get("return_per_unit_drawdown", 0),
                    "capital_velocity": ce.get("capital_velocity", 0),
                    "half_life_hours": sq.get("avg_strategy_half_life_hours", 0),
                    "mutation_survival": mf.get("avg_lineage_survival", 0),
                    "regime_persistence": sq.get("regime_persistence", 0),
                    "dd_persistence_hours": cp.get("drawdown_persistence_hours", 0),
                    "recovery_eff": cp.get("recovery_efficiency", 1.0),
                    "cascade_risk": cp.get("cascading_failure_risk", 0),
                    "concentration_instability": cp.get("concentration_instability", 0),
                    "contagion_risk": cp.get("portfolio_contagion_risk", 0),
                    "dominant_mutation": mf.get("dominant_family", "none"),
                    "collapsing": safe_json_dumps(mf.get("collapsing_families", [])),
                    "exploration_ratio": mf.get("exploration_vs_exploitation", 0.5),
                    "top_scout": spv.get("top_scout", "none"),
                    "worst_scout": spv.get("worst_scout", "none"),
                    "predictive_divergence": spv.get("predictive_divergence", 0),
                    "exec_degradation": er.get("execution_degradation", 0),
                    "spread_sensitivity": er.get("spread_sensitivity", 0),
                    "liq_degradation": er.get("liquidity_degradation_trend", 0),
                    "composite": safe_json_dumps(composite),
                    "metadata": safe_json_dumps({
                        "agent": self.name,
                        "n_domains_analyzed": 7,
                        "domains": [
                            "trade_quality", "capital_efficiency", "survival_quality",
                            "scout_quality", "capital_preservation", "regime_specialization",
                            "mutation_fitness", "scout_predictive_value", "execution_realism"
                        ],
                    }),
                },
            )
        except Exception as e:
            logger.debug(f"{self.name}: Persist composite analysis failed: {e}")

        # Also persist regime specialization details separately
        try:
            await self._persist_regime_specialization(rs, analysis_id, now)
        except Exception as e:
            logger.debug(f"{self.name}: Persist regime specialization failed: {e}")

        # Persist scout predictive rankings separately
        try:
            await self._persist_scout_rankings(spv, analysis_id, now)
        except Exception as e:
            logger.debug(f"{self.name}: Persist scout rankings failed: {e}")

    async def _persist_regime_specialization(self, rs: dict, analysis_id: str, now: datetime) -> None:
        """Persist regime specialization details."""
        analysis_namespace = uuid.uuid5(uuid.NAMESPACE_DNS, analysis_id)
        for regime, data in rs.get("regime_specialists", {}).items():
            await self.db._execute_insert(
                """
                INSERT INTO regime_specialization_log
                    (id, analysis_id, regime, n_observations, avg_fitness, avg_sharpe,
                     avg_sortino, avg_win_rate, avg_drawdown, total_trades, recorded_at)
                VALUES
                    (:id, :analysis_id, :regime, :n_obs, :avg_fitness, :avg_sharpe,
                     :avg_sortino, :avg_win_rate, :avg_drawdown, :total_trades, :recorded_at)
                """,
                {
                    "id": str(uuid.uuid5(analysis_namespace, f"regime:{regime}")),
                    "analysis_id": analysis_id,
                    "regime": regime,
                    "n_obs": data["n_observations"],
                    "avg_fitness": data["avg_fitness"],
                    "avg_sharpe": data["avg_sharpe"],
                    "avg_sortino": data["avg_sortino"],
                    "avg_win_rate": data["avg_win_rate"],
                    "avg_drawdown": data["avg_drawdown"],
                    "total_trades": data["total_trades"],
                    "recorded_at": now,
                },
            )

        # Persist fragile and cross-regime counts
        await self.db._execute_insert(
            """
            INSERT INTO regime_specialization_summary
                (id, analysis_id, computed_at, n_fragile_organisms, n_cross_regime_survivors,
                 n_volatility_sensitive, n_liquidity_sensitive, metadata)
            VALUES
                (:id, :analysis_id, :computed_at, :fragile, :cross_regime,
                 :vol_sensitive, :liq_sensitive, :metadata)
            """,
            {
                "id": str(uuid.uuid5(analysis_namespace, "regime_specialization_summary")),
                "analysis_id": analysis_id,
                "computed_at": now,
                "fragile": len(rs.get("fragile_organisms", [])),
                "cross_regime": rs.get("cross_regime_survivors", 0),
                "vol_sensitive": len(rs.get("volatility_sensitive", [])),
                "liq_sensitive": len(rs.get("liquidity_sensitive", [])),
                "metadata": safe_json_dumps({"agent": self.name}),
            },
        )

    async def _persist_scout_rankings(self, spv: dict, analysis_id: str, now: datetime) -> None:
        """Persist scout predictive value rankings."""
        analysis_namespace = uuid.uuid5(uuid.NAMESPACE_DNS, analysis_id)
        for scout_name, data in spv.get("scout_rankings", {}).items():
            await self.db._execute_insert(
                """
                INSERT INTO scout_predictive_value_log
                    (id, analysis_id, source_scout, computed_at, n_attributions,
                     survival_rate, avg_sharpe_contribution, avg_pnl_contribution,
                     avg_drawdown_contribution, contradiction_rate, economic_score,
                     economic_score_penalized, metadata)
                VALUES
                    (:id, :analysis_id, :source_scout, :computed_at, :n_attr,
                     :survival_rate, :sharpe_contrib, :pnl_contrib,
                     :dd_contrib, :contra_rate, :eco_score,
                     :eco_score_penalized, :metadata)
                """,
                {
                    "id": str(uuid.uuid5(analysis_namespace, f"scout:{scout_name}")),
                    "analysis_id": analysis_id,
                    "source_scout": scout_name,
                    "computed_at": now,
                    "n_attr": data["n_attributions"],
                    "survival_rate": data["survival_rate"],
                    "sharpe_contrib": data["avg_sharpe_contribution"],
                    "pnl_contrib": data["avg_pnl_contribution"],
                    "dd_contrib": data["avg_drawdown_contribution"],
                    "contra_rate": data["contradiction_rate"],
                    "eco_score": data["economic_score"],
                    "eco_score_penalized": data["economic_score_penalized"],
                    "metadata": safe_json_dumps({"agent": self.name}),
                },
            )
