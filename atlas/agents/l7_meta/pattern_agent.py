import asyncio
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional
from loguru import logger

from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent
from atlas.core.event_lineage import EventLineageClient


FEATURE_FAMILIES = {
    "rsi": {"rsi_14", "rsi"},
    "bollinger": {"bollinger_lower", "bollinger_upper", "bollinger_band_position"},
    "vwap": {"vwap", "price_vs_vwap_pct"},
    "ema": {"ema_5", "ema_12", "ema_26", "ema_spread_pct"},
    "sma": {"sma_5", "sma_20"},
    "macd": {"macd", "macd_signal"},
    "volume": {"relative_volume", "volume"},
    "volatility": {"rolling_volatility", "volatility_regime"},
    "trend": {"trend_strength"},
    "returns": {"returns", "log_returns"},
}


def _resolve_feature_families(conditions: list[str]) -> list[str]:
    families = set()
    for cond in conditions:
        for feat in re.findall(r"\b[a-z_][a-z_0-9]+\b", cond):
            for family, members in FEATURE_FAMILIES.items():
                if feat in members:
                    families.add(family)
    return sorted(families)


def _parse_asset_class(tags: list[str], params: dict) -> str:
    if tags:
        for t in tags:
            if t in ("crypto", "equity"):
                return t
    return params.get("asset_class", "unknown")


def _parse_timeframe(params: dict) -> str:
    return params.get("timeframe", "unknown")


class PatternAgent(BaseAgent):
    name = "PatternAgent"
    agent_type = "pattern_analyst"
    layer = "L7"
    RUN_INTERVAL = 21600

    def __init__(self, redis_client, db_client=None):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db_client = db_client

    async def run(self):
        while self.status == "running":
            await self._analyze_patterns()
            await asyncio.sleep(self.RUN_INTERVAL)

    async def _analyze_patterns(self):
        if not self.db_client:
            return

        patterns = await self._extract_patterns()

        if patterns:
            await self._save_patterns(patterns)
            await self._publish_signals(patterns)
            await self._log_lifecycle(patterns)
            await self.db_client.log(
                agent_id=self.agent_id,
                level="INFO",
                message="pattern_analysis complete",
                metadata={
                    "type": "pattern_analysis",
                    "motif_count": len(patterns),
                    "pattern_types": list(set(p["pattern_type"] for p in patterns)),
                },
            )

        return patterns

    async def _extract_patterns(self) -> list[dict]:
        rows = await self._fetch_backtested_strategies()
        if not rows:
            return []

        clusters = self._cluster_strategies(rows)
        motifs = self._compute_motifs(clusters)
        scorecards = self._build_scorecards(motifs, len(rows))

        return motifs + scorecards

    async def _fetch_backtested_strategies(self) -> list[dict]:
        query = """
            SELECT
                s.id, s.name, s.status, s.normalized_strategy,
                s.parameters, s.created_at,
                b.sharpe, b.short_window_score, b.win_rate,
                b.total_trades, b.entry_count, b.max_drawdown,
                b.results, b.passed_validation
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
        """
        async with self.db_client.engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()

        parsed = []
        for r in rows:
            ns = r[3]
            if isinstance(ns, str):
                try:
                    ns = json.loads(ns)
                except Exception:
                    ns = {}
            params_raw = r[4]
            if isinstance(params_raw, str):
                try:
                    params_raw = json.loads(params_raw)
                except Exception:
                    params_raw = {}
            params = params_raw if isinstance(params_raw, dict) else {}

            tags = ns.get("tags") if isinstance(ns, dict) else params.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            entry_cond = (
                ns.get("entry_conditions", [])
                if isinstance(ns, dict)
                else params.get("entry_conditions", [])
            )
            exit_cond = (
                ns.get("exit_conditions", [])
                if isinstance(ns, dict)
                else params.get("exit_conditions", [])
            )

            results_raw = r[12]
            if isinstance(results_raw, str):
                try:
                    results_raw = json.loads(results_raw)
                except Exception:
                    results_raw = {}
            results = results_raw if isinstance(results_raw, dict) else {}

            feature_families = _resolve_feature_families(entry_cond + exit_cond)
            asset_class = _parse_asset_class(tags, params)
            timeframe = _parse_timeframe(params)
            archetype = tags[0] if tags else "unknown"

            for v in (r[7],):
                pass

            parsed.append(
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "status": r[2],
                    "archetype": archetype,
                    "asset_class": asset_class,
                    "timeframe": timeframe,
                    "feature_families": feature_families,
                    "sharpe": float(r[6]) if r[6] is not None else None,
                    "short_window_score": (float(r[7]) if r[7] is not None else None),
                    "win_rate": float(r[8]) if r[8] is not None else None,
                    "total_trades": int(r[9]) if r[9] is not None else 0,
                    "entry_count": int(r[10]) if r[10] is not None else 0,
                    "max_drawdown": float(r[11]) if r[11] is not None else None,
                    "gross_edge": float(results.get("gross_edge", 0)),
                    "cost_burden": float(results.get("cost_burden", 0)),
                    "composite_score": float(results.get("composite_score", 0)),
                    "tags": tags,
                }
            )

        return parsed

    def _cluster_strategies(self, strategies: list[dict]) -> dict[tuple, list[dict]]:
        clusters = defaultdict(list)
        for s in strategies:
            key = (
                s["archetype"],
                s["asset_class"],
                tuple(sorted(s["feature_families"])),
            )
            clusters[key].append(s)
        return dict(clusters)

    def _compute_motifs(self, clusters: dict[tuple, list[dict]]) -> list[dict]:
        motifs = []

        for key, members in clusters.items():
            archetype, asset_class, feature_family = key
            n = len(members)

            scores = [
                m["short_window_score"]
                for m in members
                if m["short_window_score"] is not None
            ]
            composites = [
                m["composite_score"]
                for m in members
                if m["composite_score"] is not None
            ]
            sharpes = [m["sharpe"] for m in members if m["sharpe"] is not None]
            win_rates = [m["win_rate"] for m in members if m["win_rate"] is not None]
            trades = [m["total_trades"] for m in members]
            costs = [m["cost_burden"] for m in members]
            edges = [m["gross_edge"] for m in members]

            avg_score = sum(scores) / len(scores) if scores else 0
            avg_composite = sum(composites) / len(composites) if composites else 0
            avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0
            avg_win = sum(win_rates) / len(win_rates) if win_rates else 0
            avg_trades = sum(trades) / len(trades) if trades else 0
            avg_cost = sum(costs) / len(costs) if costs else 0
            avg_edge = sum(edges) / len(edges) if edges else 0

            cost_trap = avg_cost > 0 and avg_edge > 0 and (avg_cost / avg_edge) > 0.5

            if avg_composite >= 40:
                ptype = "winning_motif"
                rec = "Prioritize this archetype for ideation focus"
            elif avg_composite >= 30:
                ptype = "neutral_motif"
                rec = "Monitor; consider parameter tuning before scaling"
            else:
                ptype = "losing_motif"
                rec = "Deprioritize; avoid similar feature combinations"

            if cost_trap:
                ptype = "cost_trap"
                rec = "Review position sizing; costs consume >50% of edge"

            confidence = min(1.0, n / 10)

            motifs.append(
                {
                    "pattern_type": ptype,
                    "archetype": archetype,
                    "feature_family": list(feature_family),
                    "asset_class": asset_class,
                    "timeframe": "mixed",
                    "regime": None,
                    "composite_score_avg": round(avg_composite, 2),
                    "short_window_score_avg": round(avg_score, 2),
                    "sharpe_avg": round(avg_sharpe, 2),
                    "win_rate_avg": round(avg_win, 4),
                    "total_trades_avg": round(avg_trades, 1),
                    "cost_burden_avg": round(avg_cost, 4),
                    "sample_size": n,
                    "confidence_score": round(confidence, 2),
                    "recommendation": rec,
                    "motif_details": {
                        "members": [m["name"] for m in members[:5]],
                        "total_members": n,
                        "avg_gross_edge": round(avg_edge, 4),
                        "is_cost_trap": cost_trap,
                    },
                }
            )

        return motifs

    def _build_scorecards(
        self, motifs: list[dict], total_backtested: int
    ) -> list[dict]:
        scorecards = []

        if total_backtested == 0:
            return scorecards

        winning = [m for m in motifs if m["pattern_type"] == "winning_motif"]
        losing = [m for m in motifs if m["pattern_type"] == "losing_motif"]
        cost_traps = [m for m in motifs if m["pattern_type"] == "cost_trap"]

        scorecards.append(
            {
                "pattern_type": "ecosystem_summary",
                "archetype": "all",
                "feature_family": [],
                "asset_class": "all",
                "timeframe": "all",
                "regime": None,
                "composite_score_avg": round(
                    sum(m["composite_score_avg"] for m in motifs) / len(motifs)
                    if motifs
                    else 0,
                    2,
                ),
                "short_window_score_avg": 0,
                "sharpe_avg": 0,
                "win_rate_avg": 0,
                "total_trades_avg": 0,
                "cost_burden_avg": 0,
                "sample_size": total_backtested,
                "confidence_score": 1.0,
                "recommendation": "Pattern analysis summary",
                "motif_details": {
                    "total_backtested": total_backtested,
                    "winning_motifs": len(winning),
                    "losing_motifs": len(losing),
                    "cost_traps": len(cost_traps),
                    "winning_archetypes": [m["archetype"] for m in winning],
                    "losing_archetypes": [m["archetype"] for m in losing],
                },
            }
        )

        return scorecards

    async def _save_patterns(self, patterns: list[dict]):
        query = """
            INSERT INTO pattern_memory
                (id, pattern_type, archetype, feature_family, asset_class,
                 timeframe, regime, composite_score_avg, short_window_score_avg,
                 sharpe_avg, win_rate_avg, total_trades_avg, cost_burden_avg,
                 sample_size, confidence_score, recommendation, motif_details,
                 detected_at, updated_at)
            VALUES
                (:id, :pattern_type, :archetype, :feature_family, :asset_class,
                 :timeframe, :regime, :composite_score_avg, :short_window_score_avg,
                 :sharpe_avg, :win_rate_avg, :total_trades_avg, :cost_burden_avg,
                 :sample_size, :confidence_score, :recommendation, :motif_details,
                 NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                updated_at = NOW(),
                composite_score_avg = EXCLUDED.composite_score_avg,
                short_window_score_avg = EXCLUDED.short_window_score_avg,
                sharpe_avg = EXCLUDED.sharpe_avg,
                win_rate_avg = EXCLUDED.win_rate_avg,
                sample_size = EXCLUDED.sample_size,
                confidence_score = EXCLUDED.confidence_score,
                recommendation = EXCLUDED.recommendation,
                motif_details = EXCLUDED.motif_details
        """
        async with self.db_client.engine.begin() as conn:
            for p in patterns:
                await conn.execute(
                    text(query),
                    {
                        "id": str(uuid.uuid4()),
                        "pattern_type": p["pattern_type"],
                        "archetype": p["archetype"],
                        "feature_family": p["feature_family"],
                        "asset_class": p["asset_class"],
                        "timeframe": p.get("timeframe", "unknown"),
                        "regime": p.get("regime"),
                        "composite_score_avg": p["composite_score_avg"],
                        "short_window_score_avg": p.get("short_window_score_avg", 0),
                        "sharpe_avg": p.get("sharpe_avg", 0),
                        "win_rate_avg": p.get("win_rate_avg", 0),
                        "total_trades_avg": p.get("total_trades_avg", 0),
                        "cost_burden_avg": p.get("cost_burden_avg", 0),
                        "sample_size": p["sample_size"],
                        "confidence_score": p["confidence_score"],
                        "recommendation": p.get("recommendation", ""),
                        "motif_details": json.dumps(p.get("motif_details", {})),
                    },
                )

    async def _publish_signals(self, patterns: list[dict]):
        winning = [p for p in patterns if p["pattern_type"] == "winning_motif"]
        losing = [p for p in patterns if p["pattern_type"] == "losing_motif"]
        cost_traps = [p for p in patterns if p["pattern_type"] == "cost_trap"]

    async def _log_lifecycle(self, patterns: list[dict]):
        if not patterns:
            return
        try:
            lineage = EventLineageClient(self.db_client)
            winning = [p for p in patterns if p["pattern_type"] == "winning_motif"]
            losing = [p for p in patterns if p["pattern_type"] == "losing_motif"]
            await lineage.create_event(
                trace_id=f"pattern_{datetime.utcnow().strftime('%Y%m%d_%H%M')}",
                stage="pattern",
                status="completed",
                actor=self.name,
                metadata={
                    "total_motifs": len(patterns),
                    "winning": len(winning),
                    "losing": len(losing),
                    "archetypes": list(set(p["archetype"] for p in patterns)),
                },
            )
        except Exception as exc:
            logger.warning(f"Pattern lifecycle log failed: {exc}")

        signal = {
            "type": "pattern_signals",
            "detected_at": datetime.utcnow().isoformat(),
            "winning_archetypes": [
                {"archetype": p["archetype"], "score": p["composite_score_avg"]}
                for p in winning
            ],
            "losing_archetypes": [
                {"archetype": p["archetype"], "score": p["composite_score_avg"]}
                for p in losing
            ],
            "cost_trap_archetypes": [
                {"archetype": p["archetype"], "cost_ratio": p["cost_burden_avg"]}
                for p in cost_traps
            ],
            "top_recommendations": [p["recommendation"] for p in patterns[:3]],
            "total_motifs": len(patterns),
        }
        await self._redis.publish("pattern_signals", json.dumps(signal))
