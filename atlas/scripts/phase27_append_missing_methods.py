"""
Phase 27: Append missing Phase 26 + Phase 27 methods to the restored timescale_client.py.
These methods were lost during the file truncation incident.
"""
import ast

FILE = "data/storage/timescale_client.py"

# ── Phase 26: Scout Coupling Telemetry Methods ────────────────────────

PHASE26_METHODS = r"""
    # ================================================================
    # PHASE 26 — SCOUT COUPLING TELEMETRY METHODS
    # ================================================================

    async def log_scout_influence(
        self,
        source_scout: str,
        target_agent: str,
        influence_type: str,
        influence_metric: str,
        delta: float = 0.0,
        before_value: float | None = None,
        after_value: float | None = None,
        confidence: float = 0.0,
        regime_context: str = "",
        entropy_context: float = 0.0,
        metadata: dict | None = None,
    ) -> None:
        """Persist a scout-to-agent influence event to scout_influence_log.
        
        Called by IdeatorAgentV2 and MutationPolicyEngine to record every time
        scout intelligence materially changes agent behavior.
        """
        import json as _json
        await self._execute_insert(
            """
            INSERT INTO scout_influence_log
                (id, source_scout, target_agent, influence_type, influence_metric,
                 before_value, after_value, delta, confidence,
                 regime_context, entropy_context, metadata, created_at)
            VALUES
                (gen_random_uuid(), :source, :target, :itype, :metric,
                 :before, :after, :delta, :conf,
                 :regime, :entropy, CAST(:meta AS jsonb), NOW())
            """,
            {
                "source": source_scout,
                "target": target_agent,
                "itype": influence_type,
                "metric": influence_metric,
                "before": before_value,
                "after": after_value,
                "delta": round(float(delta), 6),
                "conf": round(float(confidence), 4),
                "regime": regime_context or "",
                "entropy": round(float(entropy_context), 4),
                "meta": _json.dumps(metadata or {}),
            },
        )

    async def log_economic_attribution(
        self,
        source_scout: str,
        influence_type: str,
        target_agent: str,
        strategy_id: str | None = None,
        strategy_name: str = "",
        sharpe_contribution: float = 0.0,
        drawdown_contribution: float = 0.0,
        pnl_contribution: float = 0.0,
        win_rate_contribution: float = 0.0,
        attribution_weight: float = 0.0,
        survived_validation: bool = False,
        regime_at_time: str = "",
        entropy_at_time: float = 0.0,
        before_value: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Persist a scout economic attribution record to scout_economic_attribution.
        
        Called after validation/execution outcomes are known to trace causal chain:
        scout -> ideator -> mutation -> validation -> execution -> pnl
        """
        import json as _json
        import uuid as _uuid
        trace_id = _uuid.uuid4().hex[:16]
        await self._execute_insert(
            """
            INSERT INTO scout_economic_attribution
                (trace_id, source_scout, influence_type, target_agent,
                 strategy_id, strategy_name, sharpe_contribution,
                 drawdown_contribution, pnl_contribution, win_rate_contribution,
                 attribution_weight, survived_validation,
                 regime_at_time, entropy_at_time, metadata, created_at)
            VALUES
                (:trace_id, :source, :itype, :target,
                 :strat_id, :strat_name, :sharpe,
                 :drawdown, :pnl, :win_rate,
                 :weight, :survived,
                 :regime, :entropy, CAST(:meta AS jsonb), NOW())
            """,
            {
                "trace_id": trace_id,
                "source": source_scout,
                "itype": influence_type,
                "target": target_agent,
                "strat_id": strategy_id or "",
                "strat_name": strategy_name or "",
                "sharpe": round(float(sharpe_contribution), 6),
                "drawdown": round(float(drawdown_contribution), 6),
                "pnl": round(float(pnl_contribution), 6),
                "win_rate": round(float(win_rate_contribution), 6),
                "weight": round(float(attribution_weight), 6),
                "survived": bool(survived_validation),
                "regime": regime_at_time or "",
                "entropy": round(float(entropy_at_time), 4),
                "meta": _json.dumps(metadata or {"before_value": before_value}),
            },
        )

    async def get_scout_influence_summary(self, hours: int = 24) -> list[dict]:
        """Fetch recent scout influence events for the mutation policy engine."""
        async with self.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT source_scout, target_agent, influence_type,
                       influence_metric, delta, regime_context,
                       entropy_context, created_at
                FROM scout_influence_log
                WHERE created_at > NOW() - INTERVAL :hours_str
                ORDER BY created_at DESC
                LIMIT 200
            """), {"hours_str": f"{hours} hours"})
            return [
                {
                    "source_scout": row[0],
                    "target_agent": row[1],
                    "influence_type": row[2],
                    "influence_metric": row[3],
                    "delta": float(row[4]) if row[4] is not None else 0.0,
                    "regime_context": row[5] or "",
                    "entropy_context": float(row[6]) if row[6] is not None else 0.0,
                    "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                }
                for row in r.fetchall()
            ]

    async def get_economic_attribution_summary(self, hours: int = 24) -> list[dict]:
        """Fetch recent economic attribution records for trust evolution."""
        async with self.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT source_scout, COUNT(*) as n_strategies,
                       AVG(sharpe_contribution) as avg_sharpe,
                       AVG(pnl_contribution) as avg_pnl,
                       SUM(CASE WHEN survived_validation THEN 1 ELSE 0 END) as n_survived,
                       AVG(attribution_weight) as avg_weight
                FROM scout_economic_attribution
                WHERE created_at > NOW() - INTERVAL :hours_str
                GROUP BY source_scout
                ORDER BY avg_sharpe DESC
            """), {"hours_str": f"{hours} hours"})
            return [
                {
                    "source_scout": row[0],
                    "n_strategies": int(row[1]),
                    "avg_sharpe_contribution": float(row[2] or 0),
                    "avg_pnl_contribution": float(row[3] or 0),
                    "n_survived_validation": int(row[4] or 0),
                    "avg_attribution_weight": float(row[5] or 0),
                }
                for row in r.fetchall()
            ]
"""

# ── Phase 27E: Evolutionary Garbage Collection ────────────────────────

PHASE27_GC = r"""
    async def evolutionary_garbage_collection(self, dry_run: bool = True) -> dict:
        """Phase 27E: Clean up stale evolutionary artifacts.
        
        Marks and/or removes:
        - code_failed strategies older than 24 hours
        - permanently_failed strategies older than 7 days
        - invalidated strategies older than 3 days
        - obsolete strategies older than 14 days
        
        Preserves audit trail and event lineage.
        If dry_run=True, only counts rows that WOULD be affected.
        """
        from loguru import logger
        results = {"dry_run": dry_run}
        try:
            async with self.engine.begin() as conn:
                # ── Count phase ──
                queries = [
                    ("code_failed_obsoleted", "SELECT COUNT(*) FROM strategies WHERE status = 'code_failed' AND created_at < NOW() - INTERVAL '24 hours'"),
                    ("perm_failed_obsoleted", "SELECT COUNT(*) FROM strategies WHERE status = 'permanently_failed' AND created_at < NOW() - INTERVAL '7 days'"),
                    ("invalidated_obsoleted", "SELECT COUNT(*) FROM strategies WHERE status = 'invalidated' AND created_at < NOW() - INTERVAL '3 days'"),
                    ("obsolete_deleted", "SELECT COUNT(*) FROM strategies WHERE status = 'obsolete' AND created_at < NOW() - INTERVAL '14 days'"),
                    ("orphan_mutations_deleted", "SELECT COUNT(*) FROM mutation_record WHERE child_id NOT IN (SELECT id::text FROM strategies) AND created_at < NOW() - INTERVAL '7 days'"),
                ]
                for key, sql in queries:
                    r = await conn.execute(text(sql))
                    results[key] = r.fetchone()[0]

                if dry_run:
                    logger.info(
                        "evolutionary_gc (dry_run): code_failed->obsolete=%s, "
                        "perm_failed->obsolete=%s, invalidated->obsolete=%s, "
                        "obsolete_deleted=%s, orphan_mutations=%s",
                        results.get("code_failed_obsoleted", 0),
                        results.get("perm_failed_obsoleted", 0),
                        results.get("invalidated_obsoleted", 0),
                        results.get("obsolete_deleted", 0),
                        results.get("orphan_mutations_deleted", 0),
                    )
                    return results

                # ── Execution phase ──
                updates = [
                    ("code_failed_obsoleted", "UPDATE strategies SET status = 'obsolete', compiled_code = NULL WHERE status = 'code_failed' AND created_at < NOW() - INTERVAL '24 hours'"),
                    ("perm_failed_obsoleted", "UPDATE strategies SET status = 'obsolete' WHERE status = 'permanently_failed' AND created_at < NOW() - INTERVAL '7 days'"),
                    ("invalidated_obsoleted", "UPDATE strategies SET status = 'obsolete' WHERE status = 'invalidated' AND created_at < NOW() - INTERVAL '3 days'"),
                    ("obsolete_deleted", "DELETE FROM strategies WHERE status = 'obsolete' AND created_at < NOW() - INTERVAL '14 days'"),
                    ("orphan_mutations_deleted", "DELETE FROM mutation_record WHERE child_id NOT IN (SELECT id::text FROM strategies) AND created_at < NOW() - INTERVAL '7 days'"),
                ]
                for key, sql in updates:
                    r = await conn.execute(text(sql))
                    results[key] = r.rowcount

                logger.info(
                    "evolutionary_gc: code_failed->obsolete=%s, "
                    "perm_failed->obsolete=%s, invalidated->obsolete=%s, "
                    "obsolete_deleted=%s, orphan_mutations=%s",
                    results.get("code_failed_obsoleted", 0),
                    results.get("perm_failed_obsoleted", 0),
                    results.get("invalidated_obsoleted", 0),
                    results.get("obsolete_deleted", 0),
                    results.get("orphan_mutations_deleted", 0),
                )
        except Exception as e:
            logger.error(f"evolutionary_gc: Error: {e}")
            results["error"] = str(e)
        return results
"""


# ── Append all missing methods ────────────────────────────────────────

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Check what's already present
present = set()
for name in [
    "log_scout_influence", "log_economic_attribution",
    "get_scout_influence_summary", "get_economic_attribution_summary",
    "evolutionary_garbage_collection",
]:
    if f"async def {name}" in content:
        present.add(name)
        print(f"  {name}: already present ✅")
    else:
        print(f"  {name}: MISSING — will append")

# Build the appendix
appendix = "\n\n"  # Just in case file doesn't end with newline

if "log_scout_influence" not in present:
    appendix += PHASE26_METHODS
    print("  → Appending Phase 26 methods")

if "evolutionary_garbage_collection" not in present:
    appendix += PHASE27_GC
    print("  → Appending Phase 27 GC method")

if appendix.strip():
    content = content.rstrip("\n") + appendix + "\n"
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n✅ Appended {len(appendix)} chars to {FILE}")
else:
    print("\n✅ All methods already present — no changes needed")

# Verify syntax
try:
    ast.parse(content)
    print("✅ Syntax OK")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
