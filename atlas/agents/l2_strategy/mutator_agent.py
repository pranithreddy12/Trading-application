"""
MutatorAgent v2 — Controlled Evolutionary Optimizer.

Transforms from "LLM rewrites strategy" to "controlled evolutionary optimizer":
  1. Hard-constrained mutation types (threshold, period, condition, exit)
  2. Expanded candidate pool: failed_validation (with entries) + research_candidate + validated_B
  3. Structural filter: reject dead strategies (entry_count=0, trades<3)
  4. JSON extraction hardening (strip fences, extract block)
  5. Failure memory passed to prompt (entry_count, trades, validator notes)
  6. Anti-clone: normalized_strategy similarity check before save
  7. Mutation memory: parent-child tracking with delta scoring
  8. Deterministic micro-mutations before Claude (threshold tweaks, condition removal)
  9. Mutation family taxonomy: repair, refinement, exploration, aggression, simplification
 10. Mutation telemetry: per-family win rates, entry/trade deltas, complexity delta
"""

import asyncio
import json
import re
from copy import deepcopy
from enum import Enum
from loguru import logger
from redis.asyncio import Redis
from anthropic import AsyncAnthropic

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.viability_score import (
    compute_viability_score,
    classify_viability,
)


# Mutation family taxonomy — governs how we classify and learn from mutations
class MutationFamily(str, Enum):
    REPAIR = "repair"  # Fix broken conditions (relax thresholds, widen triggers)
    REFINEMENT = "refinement"  # Tweak working strategies (small threshold shifts)
    EXPLORATION = "exploration"  # Add new conditions or indicators
    AGGRESSION = "aggression"  # Tighten exits, reduce risk tolerance
    SIMPLIFICATION = "simplification"  # Remove unnecessary conditions


# Allowed mutation classes — Claude must pick one
ALLOWED_MUTATION_TYPES = [
    "threshold_adjustment",
    "period_adjustment",
    "condition_removal",
    "condition_addition",
    "exit_refinement",
]

# Allowed mutation types -> family mapping
MUTATION_TYPE_FAMILY = {
    "threshold_adjustment": MutationFamily.REPAIR,
    "rsi_threshold_shift": MutationFamily.REPAIR,
    "condition_removal": MutationFamily.SIMPLIFICATION,
    "condition_addition": MutationFamily.EXPLORATION,
    "exit_refinement": MutationFamily.AGGRESSION,
    "claude_refinement": MutationFamily.REFINEMENT,
}

# Structural minimums — strategies below these are rejected
MIN_ENTRY_COUNT = 3
MIN_TRADES = 3

# Candidate pool Sharpe bands
REPAIR_SHARPE_MIN = 0.0  # failed_validation with entries, any sharpe
RESEARCH_SHARPE_MIN = 0.0
VALIDATED_B_SHARPE_MIN = 0.0

# Anti-clone: max Jaccard distance to reject near-duplicates
# standardized_similarity returns 0.0=identical, 1.0=different
MAX_DUPLICATE_DISTANCE = 0.15


def extract_json_block(text: str) -> str:
    """Extract JSON from Claude response, stripping markdown fences and commentary."""
    # Strip ```json ... ``` fences
    text = text.strip()
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()
    else:
        # Try finding first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return text.strip()


def standardized_similarity(a: dict, b: dict) -> float:
    """
    Compute dissimilarity between two strategy specs.
    Uses feature/indicator overlap (Jaccard distance).
    Returns 0.0 (identical) to 1.0 (completely different).
    """

    def _extract_features(spec: dict) -> set:
        features = set()
        for key in ("entry_conditions", "exit_conditions"):
            for cond in spec.get(key) or []:
                for feat in re.findall(r"\b[a-z_0-9]+\b", str(cond)):
                    features.add(feat)
        return features

    a_feats = _extract_features(a)
    b_feats = _extract_features(b)

    if not a_feats or not b_feats:
        return 1.0

    intersection = a_feats & b_feats
    union = a_feats | b_feats
    jaccard_distance = 1.0 - (len(intersection) / len(union)) if union else 1.0
    return jaccard_distance


def deterministic_micro_mutations(spec: dict, max_variants: int = 3) -> list[dict]:
    """
    Generate rule-based micro-mutations from a strategy spec.
    Cheaper + more reliable than Claude for simple threshold adjustments.
    """
    variants = []
    params = spec.get("parameters", spec)
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}

    entry_conds = params.get("entry_conditions", []) or []
    exit_conds = params.get("exit_conditions", []) or []

    # --- Mutation 1: Relax the most restrictive threshold ---
    # Find numeric thresholds and loosen them by 20%
    new_entry = []
    for cond in entry_conds:
        new_cond = _relax_threshold(cond, factor=0.8)
        new_entry.append(new_cond)
    new_exit = []
    for cond in exit_conds:
        new_cond = _tighten_exit(cond, factor=1.2)
        new_exit.append(new_cond)
    if new_entry != entry_conds or new_exit != exit_conds:
        v1 = deepcopy(spec)
        v1["entry_conditions"] = new_entry
        v1["exit_conditions"] = new_exit
        v1["_mutation_type"] = "threshold_adjustment"
        v1["_mutation_fields"] = ["entry_conditions", "exit_conditions"]
        variants.append(v1)

    # --- Mutation 2: Remove the most restrictive condition ---
    if len(entry_conds) >= 2:
        # Find the condition that references the most restrictive-feeling feature
        restrictive_keywords = [
            "relative_volume",
            "volatility_regime",
            "trend_strength",
        ]
        removable = -1
        for i, cond in enumerate(entry_conds):
            if any(kw in cond.lower() for kw in restrictive_keywords):
                removable = i
                break
        if removable == -1:
            removable = len(entry_conds) - 1  # remove last condition

        v2 = deepcopy(spec)
        v2["entry_conditions"] = [
            c for j, c in enumerate(entry_conds) if j != removable
        ]
        v2["_mutation_type"] = "condition_removal"
        v2["_mutation_fields"] = [f"entry_conditions[{removable}]"]
        variants.append(v2)

    # --- Mutation 3: Adjust RSI threshold ---
    for cond in entry_conds + exit_conds:
        rsi_match = re.search(r"rsi_14\s*([<>=]+)\s*(\d+)", cond)
        if rsi_match:
            op, val = rsi_match.group(1), int(rsi_match.group(2))
            adjusted = val + 5  # shift RSI threshold by 5
            v3 = deepcopy(spec)
            if cond in entry_conds:
                target_conds = entry_conds
                other_conds = exit_conds
            else:
                target_conds = exit_conds
                other_conds = entry_conds
            new_conds = [
                re.sub(
                    rf"rsi_14\s*{re.escape(op)}\s*{val}",
                    f"rsi_14 {op} {adjusted}",
                    c,
                )
                for c in target_conds
            ]
            if cond in entry_conds:
                v3["entry_conditions"] = new_conds
                v3["exit_conditions"] = other_conds
            else:
                v3["exit_conditions"] = new_conds
                v3["entry_conditions"] = other_conds
            v3["_mutation_type"] = "rsi_threshold_shift"
            v3["_mutation_fields"] = ["rsi_14 threshold"]
            variants.append(v3)
            break

    return variants[:max_variants]


def _relax_threshold(cond: str, factor: float = 0.8) -> str:
    """Make an entry condition easier to satisfy (relax threshold).
    For >: lower the threshold (multiply). For <: raise the threshold (divide).
    """
    for op_pattern in [
        (r"(>)\s*(-?[\d.]+)", lambda m: f"> {float(m.group(2)) * factor:.4f}"),
        (r"(<)\s*(-?[\d.]+)", lambda m: f"< {float(m.group(2)) / factor:.4f}"),
    ]:
        match = re.search(op_pattern[0], cond)
        if match:
            return re.sub(op_pattern[0], op_pattern[1](match), cond)
    return cond


def _tighten_exit(cond: str, factor: float = 1.2) -> str:
    """Make an exit condition harder to trigger (tighten threshold).
    For >: raise the threshold. For <: lower the threshold.
    Uses absolute movement for negative thresholds (further from zero = tighter).
    """

    def _tighten(op: str, val: float) -> str:
        if op == ">":
            new_val = val * factor if val >= 0 else val / factor
        else:
            new_val = val / factor if val >= 0 else val * factor
        return f"{op} {new_val:.4f}"

    for op_pattern in [
        (r"(>)\s*(-?[\d.]+)", lambda m: _tighten(">", float(m.group(2)))),
        (r"(<)\s*(-?[\d.]+)", lambda m: _tighten("<", float(m.group(2)))),
    ]:
        match = re.search(op_pattern[0], cond)
        if match:
            return re.sub(op_pattern[0], op_pattern[1](match), cond)
    return cond


def _is_duplicate(
    spec: dict, existing_specs: list[dict], max_distance: float = MAX_DUPLICATE_DISTANCE
) -> bool:
    """Check if spec is too similar to existing ones (distance <= threshold = duplicate)."""
    for existing in existing_specs:
        distance = standardized_similarity(spec, existing)
        if distance <= max_distance:
            return True
    return False


def _classify_mutation_family(mutation_type: str) -> str:
    """Map a mutation type to its family taxonomy."""
    base_type = (
        mutation_type.split("::")[-1] if "::" in mutation_type else mutation_type
    )
    family = MUTATION_TYPE_FAMILY.get(base_type, MutationFamily.REFINEMENT)
    return family.value


def _family_qualified_type(mutation_type: str, family: str | None = None) -> str:
    """Encode mutation type with its family for storage: 'family::type'."""
    if family is None:
        family = _classify_mutation_family(mutation_type)
    return f"{family}::{mutation_type}"


def _compute_complexity(spec: dict) -> int:
    """Compute structural complexity score for a mutation spec."""
    entry = spec.get("entry_conditions", [])
    exit_ = spec.get("exit_conditions", [])
    score = len(entry) + len(exit_)
    for cond in entry + exit_:
        for feat in re.findall(r"\b[a-z_0-9]+\b", str(cond)):
            score += 1
    return score


def _predicted_entry_delta(parent_params: dict, child_spec: dict) -> int:
    """Estimate how entry frequency will change based on condition changes."""
    parent_entry = (
        parent_params.get("entry_conditions", [])
        if isinstance(parent_params, dict)
        else []
    )
    child_entry = child_spec.get("entry_conditions", [])
    parent_gt_count = sum(
        1 for c in parent_entry if re.search(r">\s*\d+\.?\d*", str(c))
    )
    child_gt_count = sum(1 for c in child_entry if re.search(r">\s*\d+\.?\d*", str(c)))
    parent_lt_count = sum(
        1 for c in parent_entry if re.search(r"<\s*\d+\.?\d*", str(c))
    )
    child_lt_count = sum(1 for c in child_entry if re.search(r"<\s*\d+\.?\d*", str(c)))
    delta = (child_gt_count - parent_gt_count) + (parent_lt_count - child_lt_count)
    return delta


def _normalize_mutation_spec(spec: dict, parent_name: str, source: str) -> dict:
    """Normalize a mutation spec to consistent root-level schema (name not strategy_name)."""
    out = {k: v for k, v in spec.items() if not k.startswith("_")}
    if "name" not in out and "strategy_name" in out:
        out["name"] = out.pop("strategy_name")
    if "name" not in out:
        out["name"] = f"{parent_name}_mut_{source}"
    return out


def _validate_mutation(spec: dict, parent_params: dict) -> str | None:
    """Hard structural validation before saving a mutation. Returns error string or None."""
    entry = spec.get("entry_conditions", [])
    exit_ = spec.get("exit_conditions", [])
    parent_entry = (
        parent_params.get("entry_conditions", [])
        if isinstance(parent_params, dict)
        else []
    )

    if not entry and not exit_:
        return "No entry or exit conditions"
    if len(entry) == 0:
        return "Zero entry conditions — mutation invalid"
    if len(entry) > 3:
        return f"Too many entry conditions ({len(entry)} > 3)"
    if entry == parent_entry:
        return "Entry conditions unchanged from parent"
    return None


def _build_diagnostic(result: dict) -> str:
    """Build a human-readable diagnostic from backtest results."""
    parts = []
    entry_c = result.get("entry_count", 0)
    trades = result.get("total_trades", 0)
    sharpe = result.get("sharpe", result.get("holdout_sharpe", 0))
    drawdown = result.get("max_drawdown", 0)
    notes = result.get("notes", "")

    if entry_c == 0:
        parts.append("Zero entry signals - conditions never triggered")
    elif entry_c < 10:
        parts.append(f"Low entry frequency ({entry_c} signals)")
    else:
        parts.append(f"Reasonable entry frequency ({entry_c} signals)")

    if trades < 5:
        parts.append(f"Too few holdout trades ({trades})")
    else:
        parts.append(f"{trades} holdout trades")

    if sharpe is not None and sharpe < 0:
        parts.append(f"Negative Sharpe ({sharpe:.2f})")
    elif sharpe and sharpe > 0:
        parts.append(f"Positive Sharpe ({sharpe:.2f})")

    if drawdown and drawdown < -30:
        parts.append(f"Excessive drawdown ({drawdown:.1f}%)")

    if notes:
        parts.append(f"Validator: {notes[:200]}")

    return "; ".join(parts)


class MutatorAgent(BaseAgent):
    """
    Controlled evolutionary strategy optimizer.
    Mutates weak-but-viable strategies through targeted perturbations,
    not full rewrites.
    """

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name="MutatorAgent",
            agent_type="mutator",
            layer="L2",
            redis_client=redis_client,
        )
        self.RUN_INTERVAL_SECONDS = 900  # 15 minutes in demo mode
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.db_client = db_client

    async def run(self):
        logger.info("MutatorAgent v2 started (controlled evolutionary optimizer)")
        while self.status == "running":
            await self._mutation_cycle()
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _mutation_cycle(self):
        """Full mutation pipeline: fetch candidates -> filter -> mutate -> save."""
        logger.info("Starting mutation cycle...")
        try:
            candidates = await self.db_client.get_repair_candidates(limit=10)
            if not candidates:
                logger.info("No repair candidates found. Skipping cycle.")
                return

            logger.info(f"Found {len(candidates)} repair candidates")

            # Fetch existing mutant specs for anti-clone check
            # (get recently-created mutated strategies)
            existing_mutants = await self._get_recent_mutants(limit=50)

            for candidate in candidates:
                try:
                    await self._process_candidate(candidate, existing_mutants)
                except Exception as e:
                    logger.error(
                        f"Error processing candidate {candidate.get('name', '?')}: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Mutation cycle error: {e}", exc_info=True)

    async def _process_candidate(self, candidate: dict, existing_specs: list[dict]):
        """Process a single candidate through deterministic + Claude mutation."""
        strategy_id = candidate["id"]
        name = candidate.get("name", "unknown")
        params = candidate.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}

        # --- Structural filter ---
        entry_c = candidate.get("entry_count", 0)
        trades = candidate.get("total_trades", 0)
        if entry_c is None or entry_c < MIN_ENTRY_COUNT:
            logger.info(f"Skipping {name}: entry_count={entry_c} < {MIN_ENTRY_COUNT}")
            return
        if trades is None or trades < MIN_TRADES:
            logger.info(f"Skipping {name}: total_trades={trades} < {MIN_TRADES}")
            return

        logger.info(
            f"Processing candidate: {name} (entries={entry_c}, trades={trades})"
        )

        # --- Phase 1: Deterministic micro-mutations ---
        deterministic_variants = deterministic_micro_mutations(params)
        mutated_ids = []

        for variant in deterministic_variants:
            mut_type = variant.pop("_mutation_type", "deterministic")
            mut_fields = variant.pop("_mutation_fields", [])
            spec_to_save = _normalize_mutation_spec(variant, name, mut_type)

            # Structural validation
            validation_error = _validate_mutation(spec_to_save, params)
            if validation_error:
                logger.info(f"Skipping deterministic {mut_type}: {validation_error}")
                continue

            # Viability score — pre-save quality gate
            viability = compute_viability_score(
                spec_to_save,
                parent_params=params,
                parent_failure={
                    "entry_count": entry_c,
                    "sharpe": candidate.get("sharpe", 0),
                },
            )
            score_label = classify_viability(viability)
            if viability < 0.30:
                logger.info(
                    f"Skipping deterministic {mut_type}: viability={viability:.3f} ({score_label})"
                )
                continue

            # Anti-clone check
            if _is_duplicate(spec_to_save, existing_specs):
                logger.info(f"Skipping deterministic clone: {spec_to_save['name']}")
                continue

            # Classify mutation family and compute scorecard
            mut_family = _classify_mutation_family(mut_type)
            qualified_type = _family_qualified_type(mut_type, mut_family)
            parent_complexity = _compute_complexity(params)
            child_complexity = _compute_complexity(spec_to_save)
            predicted_delta = _predicted_entry_delta(params, spec_to_save)

            child_id = await self.db_client.save_strategy(
                spec_to_save,
                status="pending_code",
                author_agent=f"{self.name}_deterministic",
            )
            mutated_ids.append(
                (
                    child_id,
                    qualified_type,
                    mut_fields,
                    spec_to_save,
                    mut_family,
                    parent_complexity,
                    child_complexity,
                    predicted_delta,
                )
            )

        # --- Phase 2: Claude mutation (controlled) ---
        claude_raw = await self._claude_mutate(candidate, params)
        if claude_raw:
            claude_mut_type = claude_raw.get("_mutation_type", "claude_refinement")
            claude_mut_fields = claude_raw.get("_mutation_fields", ["unknown"])
            claude_spec = _normalize_mutation_spec(claude_raw, name, "claude")

            claude_validation_error = _validate_mutation(claude_spec, params)
            claude_viability = compute_viability_score(
                claude_spec,
                parent_params=params,
                parent_failure={
                    "entry_count": entry_c,
                    "sharpe": candidate.get("sharpe", 0),
                },
            )
            claude_is_duplicate = _is_duplicate(
                claude_spec, existing_specs + [v[3] for v in mutated_ids]
            )

            if claude_validation_error:
                logger.info(f"Skipping Claude mutation: {claude_validation_error}")
            elif claude_viability < 0.30:
                logger.info(
                    f"Skipping Claude mutation: viability={claude_viability:.3f} ({classify_viability(claude_viability)})"
                )
            elif claude_is_duplicate:
                logger.info(f"Skipping Claude clone: {claude_spec.get('name', '?')}")
            else:
                mut_family = _classify_mutation_family(claude_mut_type)
                qualified_type = _family_qualified_type(claude_mut_type, mut_family)
                parent_complexity = _compute_complexity(params)
                child_complexity = _compute_complexity(claude_spec)
                predicted_delta = _predicted_entry_delta(params, claude_spec)

                child_id = await self.db_client.save_strategy(
                    claude_spec,
                    status="pending_code",
                    author_agent=self.name,
                    prompt=self._build_claude_prompt(candidate),
                    raw_response=json.dumps(claude_raw),
                )
                mutated_ids.append(
                    (
                        child_id,
                        qualified_type,
                        claude_mut_fields,
                        claude_spec,
                        mut_family,
                        parent_complexity,
                        child_complexity,
                        predicted_delta,
                    )
                )

        # --- Record mutation lineage with telemetry ---
        parent_metrics = {
            "sharpe": candidate.get("sharpe", candidate.get("holdout_sharpe", 0)),
            "entry_count": entry_c,
            "total_trades": trades,
        }
        for (
            child_id,
            qualified_type,
            mut_fields,
            child_spec,
            mut_family,
            parent_complexity,
            child_complexity,
            predicted_delta,
        ) in mutated_ids:
            await self.db_client.save_mutation_record(
                parent_id=strategy_id,
                child_id=child_id,
                mutation_type=qualified_type,
                changed_fields=mut_fields,
                parent_metrics=parent_metrics,
                child_metrics={"sharpe": 0, "entry_count": 0, "total_trades": 0},
            )
            logger.info(
                f"  Mutant [{mut_family}] {qualified_type}: "
                f"complexity {parent_complexity}->{child_complexity}, "
                f"predicted_entry_delta {predicted_delta:+d}"
            )

        # Publish signals for new strategies
        messaging = MessagingClient(self._redis)
        for child_id, *_ in mutated_ids:
            await messaging.publish(
                Channel.STRATEGY_SIGNALS,
                {
                    "type": "new_spec",
                    "strategy_id": child_id,
                    "source": "mutator",
                },
            )

        logger.info(f"Generated {len(mutated_ids)} mutants from {name}")

    async def _claude_mutate(self, candidate: dict, params: dict) -> dict | None:
        """Use Claude for controlled mutation with hard constraints."""
        diagnostic = _build_diagnostic(candidate)
        sharpe = candidate.get("sharpe", candidate.get("holdout_sharpe", 0))

        system_prompt = f"""You are a conservative strategy optimizer for a quant fund.

CRITICAL RULES — VIOLATION WILL INVALIDATE YOUR OUTPUT:

1. PRESERVE the parent strategy's core hypothesis and structure.
2. Change ONLY 1-3 parameters, thresholds, or conditions.
3. Do NOT rewrite from scratch. Do NOT introduce a new philosophy.
4. Do NOT exceed 3 entry conditions.
5. Prioritize increasing trigger realism — if conditions never triggered, relax thresholds.
6. If the parent has zero entries, a zero-entry mutation is INVALID.
7. Respond ONLY with a valid JSON object. No markdown, no commentary.
8. Allowed mutation types (pick ONE): {", ".join(ALLOWED_MUTATION_TYPES)}"""

        user_prompt = self._build_claude_prompt(candidate, diagnostic)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1200,
                temperature=0.5,  # Lower temperature for more conservative mutations
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text

            # JSON extraction hardening
            cleaned = extract_json_block(content)
            try:
                spec = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Claude JSON parse failed for {candidate.get('name')}: {e}"
                )
                logger.debug(f"Raw content: {content[:500]}")
                return None

            # Validate required fields
            if not spec.get("entry_conditions") and not spec.get("exit_conditions"):
                logger.error(f"Claude returned spec with no conditions: {spec}")
                return None

            # Validate mutation type is allowed
            mut_type = spec.get("mutation_type", "unknown")
            if mut_type not in ALLOWED_MUTATION_TYPES:
                logger.warning(
                    f"Claude used disallowed mutation type '{mut_type}', marking as claude_refinement"
                )
                spec["_mutation_type"] = "claude_refinement"
            else:
                spec["_mutation_type"] = mut_type

            spec["_mutation_fields"] = spec.get(
                "changed_fields", spec.get("changes", "unknown")
            )
            # Clean up Claude artifacts
            spec.pop("changes", None)
            spec.pop("mutation_type", None)
            spec.pop("explanation", None)
            spec.pop("expected_sharpe", None)
            spec.pop("expected_win_rate", None)

            return spec

        except Exception as e:
            logger.error(f"Claude API error for {candidate.get('name')}: {e}")
            return None

    def _build_claude_prompt(self, candidate: dict, diagnostic: str = "") -> str:
        """Build the Claude prompt with failure memory (minimized token payload)."""
        name = candidate.get("name", "unknown")
        params = candidate.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        sharpe = candidate.get("sharpe", candidate.get("holdout_sharpe", 0))
        entry_c = candidate.get("entry_count", 0)
        trades = candidate.get("total_trades", 0)

        # Send only essential fields, not the full nested spec
        minimal_spec = json.dumps(
            {
                "entry_conditions": params.get("entry_conditions", []),
                "exit_conditions": params.get("exit_conditions", []),
                "sharpe": sharpe,
                "entry_count": entry_c,
            },
            indent=2,
        )

        return f"""Strategy: {name}
Sharpe: {sharpe:.2f} | Entries: {entry_c} | Trades: {trades}
DIAGNOSTIC: {diagnostic[:200] if diagnostic else "None"}

Current Spec:
{minimal_spec}

Mutate conservatively. Output valid JSON: strategy_name, entry_conditions, exit_conditions, mutation_type, changed_fields"""

    async def _get_recent_mutants(self, limit: int = 50) -> list[dict]:
        """Get recently-created strategies for anti-clone comparison."""
        async with self.db_client.engine.connect() as conn:
            from sqlalchemy import text

            result = await conn.execute(
                text("""
                    SELECT normalized_strategy FROM strategies
                    WHERE LOWER(author_agent) LIKE '%mutator%'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            specs = []
            for row in result.fetchall():
                val = row[0]
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except Exception:
                        continue
                if isinstance(val, dict):
                    specs.append(val)
            return specs


async def main():
    """Entrypoint: initialize Redis + DB, create agent, start mutation loop."""
    logger.info("Starting MutatorAgent v2...")

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    db_client = TimescaleClient(db_url=settings.database_url)
    await db_client.connect()

    agent = MutatorAgent(redis_client=redis_client, db_client=db_client)
    agent.status = "running"
    logger.info(f"MutatorAgent status: {agent.status}")

    try:
        await agent.run()
    finally:
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
