"""
MutationPatternAgent — L7 Contextual Meta-Learner.

Instead of:  "threshold_adjustment works" (context-free)
Learns:      "threshold_adjustment works in: crypto, 1m, momentum regime"

Pipeline:
  1. Fetch mutation_memory joined with strategies context (asset_class, timeframe, archetype)
  2. Group outcomes by context dimensions: mutation_type × asset_class, mutation_type × timeframe
  3. Compute win rates, avg score deltas, confidence per context
  4. Persist to pattern_memory (pattern_type='mutation_context')
  5. Publish contextual intelligence for mutator + ideator consumption
"""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent
from atlas.core.event_lineage import EventLineageClient


CONTEXT_DIMENSIONS = ["asset_class", "timeframe", "archetype"]


class ContextualMutationProfile(dict):
    """A dict subclass representing a contextual mutation intelligence record."""

    def __init__(
        self,
        mutation_type: str,
        dimension: str,
        dimension_value: str,
        total: int,
        improved: int,
        avg_score_delta: float,
        avg_sharpe_delta: float,
    ):
        super().__init__()
        self["mutation_type"] = mutation_type
        self["dimension"] = dimension
        self["dimension_value"] = dimension_value
        self["total"] = total
        self["improved"] = improved
        self["avg_score_delta"] = round(avg_score_delta, 4)
        self["avg_sharpe_delta"] = round(avg_sharpe_delta, 4)
        self["win_rate"] = round(improved / total, 4) if total > 0 else 0.0
        self["confidence"] = round(min(1.0, total / 10), 2)


class MutationPatternAgent(BaseAgent):
    """
    L7 Contextual Mutation Meta-Learner.

    Discovers which mutation types work best under which market conditions,
    transforming context-free mutation tracking into conditional evolutionary intelligence.
    """

    name = "MutationPatternAgent"
    agent_type = "mutation_pattern"
    layer = "L7"
    RUN_INTERVAL = 3600  # every hour
    MIN_SAMPLE_SIZE = 3  # minimum mutations to form a contextual pattern

    def __init__(self, redis_client, db_client=None):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db_client = db_client

    # =========================================================
    # MAIN LOOP
    # =========================================================
    async def run(self):
        logger.info("MutationPatternAgent started (contextual meta-learner)")
        while self.status == "running":
            try:
                await self._analyze_context()
            except Exception as e:
                logger.error(f"MutationPatternAgent cycle failed: {e}", exc_info=True)
            await asyncio.sleep(self.RUN_INTERVAL)

    # =========================================================
    # MASTER PIPELINE
    # =========================================================
    async def _analyze_context(self):
        """Full pipeline: fetch → group → compute → persist → signal."""
        if not self.db_client:
            logger.warning("MutationPatternAgent skipped — no db_client")
            return

        records = await self._fetch_mutation_context()
        if not records:
            logger.info("No mutation records found for contextual analysis")
            return

        grouped = self._group_by_context(records)
        profiles = self._compute_contextual_profiles(grouped)

        if profiles:
            await self._save_contexts(profiles)
            await self._publish_intelligence(profiles)
            await self._log_lifecycle(profiles)

            # Log summary
            total_contexts = len(profiles)
            high_conf = sum(1 for p in profiles if p["confidence"] >= 0.7)
            logger.info(
                f"MutationPatternAgent: {total_contexts} contextual patterns "
                f"({high_conf} high-confidence) from {len(records)} mutation records"
            )

    # =========================================================
    # FETCH: mutation_memory + strategies context
    # =========================================================
    async def _fetch_mutation_context(self) -> list[dict]:
        """
        Join mutation_memory with strategies to extract context dimensions:
        asset_class, timeframe, archetype from normalized_strategy/parameters JSONB.
        """
        query = """
            SELECT
                m.mutation_type,
                m.score_delta,
                m.sharpe_delta,
                m.improved,
                COALESCE(s.normalized_strategy, s.parameters) AS context_json
            FROM mutation_memory m
            JOIN strategies s ON m.parent_strategy_id = s.id
            WHERE m.created_at >= NOW() - INTERVAL '30 days'
              AND m.score_delta IS NOT NULL
        """
        try:
            async with self.db_client.engine.connect() as conn:
                result = await conn.execute(text(query))
                rows = result.fetchall()

            records = []
            for r in rows:
                mut_type = r[0] or "unknown"
                score_delta = float(r[1]) if r[1] is not None else 0.0
                sharpe_delta = float(r[2]) if r[2] is not None else 0.0
                improved = r[3]  # bool or None
                ctx_raw = r[4]

                # Extract context from JSONB
                ctx = {}
                if isinstance(ctx_raw, str):
                    try:
                        ctx = json.loads(ctx_raw)
                    except (json.JSONDecodeError, TypeError):
                        ctx = {}
                elif isinstance(ctx_raw, dict):
                    ctx = ctx_raw

                # Parse tags/archetype
                tags = ctx.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                archetype = tags[0] if tags else "unknown"

                # Parse context fields from parameters JSONB
                # (normalized_strategy may have asset_class, timeframe at root or nested)
                asset_class = ctx.get("asset_class", "unknown")
                timeframe = ctx.get("timeframe", "unknown")

                # Fallback: try extracting from parameters sub-field
                if asset_class == "unknown" and "parameters" in ctx:
                    params = ctx["parameters"]
                    if isinstance(params, dict):
                        asset_class = params.get("asset_class", "unknown")
                        timeframe = params.get("timeframe", "unknown")

                records.append({
                    "mutation_type": mut_type,
                    "score_delta": score_delta,
                    "sharpe_delta": sharpe_delta,
                    "improved": improved,
                    "asset_class": asset_class,
                    "timeframe": timeframe,
                    "archetype": archetype,
                })

            return records

        except Exception as e:
            logger.error(f"Mutation context fetch failed: {e}")
            return []

    # =========================================================
    # GROUP: by mutation_type × each context dimension
    # =========================================================
    def _group_by_context(self, records: list[dict]) -> dict[str, dict]:
        """
        Group records by (mutation_type, dimension, dimension_value) tuples.
        Returns: { (mut_type, dim, val): [records] }
        """
        buckets: dict[str, dict] = defaultdict(list)

        for rec in records:
            mut_type = rec["mutation_type"]

            for dim in CONTEXT_DIMENSIONS:
                dim_val = rec.get(dim, "unknown")
                key = f"{mut_type}||{dim}||{dim_val}"
                buckets[key].append(rec)

        return dict(buckets)

    # =========================================================
    # COMPUTE: contextual win rates and deltas
    # =========================================================
    def _compute_contextual_profiles(
        self, buckets: dict[str, dict]
    ) -> list[ContextualMutationProfile]:
        """Compute win_rate, avg_score_delta, avg_sharpe_delta per context bucket."""
        profiles = []

        for key, recs in buckets.items():
            if len(recs) < self.MIN_SAMPLE_SIZE:
                continue

            parts = key.split("||")
            mut_type = parts[0]
            dimension = parts[1]
            dimension_value = parts[2]

            total = len(recs)
            improved = sum(1 for r in recs if r["improved"] is True)
            avg_score_delta = sum(r["score_delta"] for r in recs) / total
            avg_sharpe_delta = sum(r["sharpe_delta"] for r in recs) / total

            profile = ContextualMutationProfile(
                mutation_type=mut_type,
                dimension=dimension,
                dimension_value=dimension_value,
                total=total,
                improved=improved,
                avg_score_delta=avg_score_delta,
                avg_sharpe_delta=avg_sharpe_delta,
            )
            profiles.append(profile)

        # Sort by confidence descending, then win_rate descending
        profiles.sort(key=lambda p: (p["confidence"], p["win_rate"]), reverse=True)
        return profiles

    # =========================================================
    # PERSIST: to pattern_memory
    # =========================================================
    async def _save_contexts(self, profiles: list[ContextualMutationProfile]):
        """Save contextual mutation profiles to pattern_memory."""
        query = """
            INSERT INTO pattern_memory
                (id, pattern_type, archetype, feature_family, asset_class,
                 timeframe, composite_score_avg, short_window_score_avg,
                 sharpe_avg, win_rate_avg, total_trades_avg, cost_burden_avg,
                 sample_size, confidence_score, recommendation, motif_details,
                 detected_at, updated_at)
            VALUES
                (:id, :pattern_type, :archetype, :feature_family, :asset_class,
                 :timeframe, :composite_score_avg, :short_window_score_avg,
                 :sharpe_avg, :win_rate_avg, :total_trades_avg, :cost_burden_avg,
                 :sample_size, :confidence_score, :recommendation, :motif_details,
                 NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                updated_at = NOW(),
                composite_score_avg = EXCLUDED.composite_score_avg,
                sharpe_avg = EXCLUDED.sharpe_avg,
                win_rate_avg = EXCLUDED.win_rate_avg,
                sample_size = EXCLUDED.sample_size,
                confidence_score = EXCLUDED.confidence_score,
                recommendation = EXCLUDED.recommendation,
                motif_details = EXCLUDED.motif_details
        """
        try:
            async with self.db_client.engine.begin() as conn:
                for p in profiles:
                    mut_type = p["mutation_type"]
                    dim = p["dimension"]
                    dim_val = p["dimension_value"]
                    win_rate = p["win_rate"]
                    confidence = p["confidence"]

                    # Build recommendation
                    if win_rate >= 0.6 and confidence >= 0.5:
                        rec = (f"PRIORITIZE {mut_type} in {dim}={dim_val} "
                               f"(win_rate={win_rate:.0%}, n={p['total']})")
                    elif win_rate <= 0.3 and confidence >= 0.5:
                        rec = (f"AVOID {mut_type} in {dim}={dim_val} "
                               f"(win_rate={win_rate:.0%}, n={p['total']})")
                    else:
                        rec = f"MONITOR {mut_type} in {dim}={dim_val} (n={p['total']})"

                    # Store context breakdown in motif_details
                    details = {
                        "mutation_type": mut_type,
                        "dimension": dim,
                        "dimension_value": dim_val,
                        "avg_sharpe_delta": p["avg_sharpe_delta"],
                        "improved_count": p["improved"],
                    }

                    # Use composite_score_avg for score_delta, sharpe_avg for sharpe_delta
                    await conn.execute(
                        text(query),
                        {
                            "id": str(uuid.uuid4()),
                            "pattern_type": "mutation_context",
                            "archetype": mut_type,
                            "feature_family": [dim],
                            "asset_class": dim_val if dim == "asset_class" else "all",
                            "timeframe": dim_val if dim == "timeframe" else "all",
                            "composite_score_avg": p["avg_score_delta"],
                            "short_window_score_avg": 0.0,
                            "sharpe_avg": p["avg_sharpe_delta"],
                            "win_rate_avg": win_rate,
                            "total_trades_avg": float(p["total"]),
                            "cost_burden_avg": 0.0,
                            "sample_size": p["total"],
                            "confidence_score": confidence,
                            "recommendation": rec,
                            "motif_details": json.dumps(details),
                        },
                    )

        except Exception as e:
            logger.error(f"Failed to save mutation contexts: {e}")

    # =========================================================
    # SIGNAL: publish contextual intelligence to Redis
    # =========================================================
    async def _publish_intelligence(self, profiles: list[ContextualMutationProfile]):
        """Publish contextual mutation intelligence for ideator + mutator."""
        # Build per-mutation-type aggregated context map
        by_type: dict[str, list[dict]] = defaultdict(list)
        for p in profiles:
            by_type[p["mutation_type"]].append(p)

        # Format as dict: { mutation_type: { context: win_rate, ... } }
        context_map = {}
        for mut_type, ctx_profiles in by_type.items():
            entries = []
            for cp in ctx_profiles:
                dim = cp["dimension"]
                dim_val = cp["dimension_value"]
                entries.append({
                    "context": f"{dim}={dim_val}",
                    "win_rate": cp["win_rate"],
                    "confidence": cp["confidence"],
                    "n": cp["total"],
                })
            # Sort by confidence desc
            entries.sort(key=lambda e: e["confidence"], reverse=True)
            context_map[mut_type] = entries

        signal = {
            "type": "mutation_context_intelligence",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_contexts": len(profiles),
            "context_map": context_map,
            "top_recommendations": [
                p.get("recommendation", "")
                for p in profiles[:5]
                if p["confidence"] >= 0.5
            ],
        }

        try:
            await self._redis.publish(
                "mutation_intelligence",
                json.dumps(signal),
            )
            logger.debug(
                f"Published mutation context intelligence: "
                f"{len(context_map)} types, {len(profiles)} contexts"
            )
        except Exception as e:
            logger.warning(f"Failed to publish mutation intelligence: {e}")

        # Also persist to pattern_memory as an ecosystem summary
        await self._save_ecosystem_summary(profiles, context_map)

    async def _save_ecosystem_summary(
        self,
        profiles: list[ContextualMutationProfile],
        context_map: dict,
    ):
        """Save an ecosystem-level summary to pattern_memory."""
        high_conf = [p for p in profiles if p["confidence"] >= 0.5]
        summary_query = """
            INSERT INTO pattern_memory
                (id, pattern_type, archetype, feature_family, asset_class,
                 timeframe, composite_score_avg, short_window_score_avg,
                 sharpe_avg, win_rate_avg, total_trades_avg, cost_burden_avg,
                 sample_size, confidence_score, recommendation, motif_details,
                 detected_at, updated_at)
            VALUES
                (:id, :pattern_type, :archetype, :feature_family, :asset_class,
                 :timeframe, :composite_score_avg, :short_window_score_avg,
                 :sharpe_avg, :win_rate_avg, :total_trades_avg, :cost_burden_avg,
                 :sample_size, :confidence_score, :recommendation, :motif_details,
                 NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                updated_at = NOW(),
                motif_details = EXCLUDED.motif_details
        """
        try:
            async with self.db_client.engine.begin() as conn:
                await conn.execute(
                    text(summary_query),
                    {
                        "id": str(uuid.uuid4()),
                        "pattern_type": "mutation_context_summary",
                        "archetype": "all",
                        "feature_family": [],
                        "asset_class": "all",
                        "timeframe": "all",
                        "composite_score_avg": 0.0,
                        "short_window_score_avg": 0.0,
                        "sharpe_avg": 0.0,
                        "win_rate_avg": 0.0,
                        "total_trades_avg": float(len(profiles)),
                        "cost_burden_avg": 0.0,
                        "sample_size": sum(p["total"] for p in profiles),
                        "confidence_score": min(1.0, len(high_conf) / 5),
                        "recommendation": (
                            f"Contextual mutation intelligence: {len(profiles)} profiles "
                            f"({len(high_conf)} high-confidence) across "
                            f"{len(context_map)} mutation types"
                        ),
                        "motif_details": json.dumps({
                            "total_profiles": len(profiles),
                            "high_confidence_profiles": len(high_conf),
                            "mutation_types_tracked": list(context_map.keys()),
                            "best_contexts": [
                                {
                                    "mutation_type": p["mutation_type"],
                                    "context": f"{p['dimension']}={p['dimension_value']}",
                                    "win_rate": p["win_rate"],
                                    "n": p["total"],
                                }
                                for p in high_conf[:10]
                                if p["win_rate"] >= 0.6
                            ],
                            "worst_contexts": [
                                {
                                    "mutation_type": p["mutation_type"],
                                    "context": f"{p['dimension']}={p['dimension_value']}",
                                    "win_rate": p["win_rate"],
                                    "n": p["total"],
                                }
                                for p in high_conf[:10]
                                if p["win_rate"] <= 0.3
                            ],
                        }),
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to save ecosystem summary: {e}")

    # =========================================================
    # LIFECYCLE
    # =========================================================
    async def _log_lifecycle(self, profiles: list[ContextualMutationProfile]):
        try:
            lineage = EventLineageClient(self.db_client)
            await lineage.create_event(
                trace_id=f"mutation_context_{datetime.utcnow().strftime('%Y%m%d_%H%M')}",
                stage="mutation_context",
                status="completed",
                actor=self.name,
                metadata={
                    "total_profiles": len(profiles),
                    "mutation_types": list(set(p["mutation_type"] for p in profiles)),
                    "high_confidence": sum(1 for p in profiles if p["confidence"] >= 0.7),
                },
            )
        except Exception as exc:
            logger.warning(f"MutationPattern lifecycle log failed: {exc}")


async def main():
    """Standalone entrypoint."""
    from redis.asyncio import Redis
    from atlas.config.settings import settings
    from atlas.data.storage.timescale_client import TimescaleClient

    redis_client = Redis.from_url(settings.redis_url)
    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()

    agent = MutationPatternAgent(redis_client, db_client)
    await agent.start()

    try:
        while agent.status == "running":
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()
    finally:
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
