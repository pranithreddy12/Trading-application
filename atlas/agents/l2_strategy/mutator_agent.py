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
"""

import asyncio
import json
import re
import math
from copy import deepcopy
from loguru import logger
from redis.asyncio import Redis
from anthropic import AsyncAnthropic

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient

# Allowed mutation classes — Claude must pick one
ALLOWED_MUTATION_TYPES = [
    "threshold_adjustment",
    "period_adjustment",
    "condition_removal",
    "condition_addition",
    "exit_refinement",
]

# Structural minimums — strategies below these are rejected
MIN_ENTRY_COUNT = 3
MIN_TRADES = 3

# Candidate pool Sharpe bands
REPAIR_SHARPE_MIN = 0.0  # failed_validation with entries, any sharpe
RESEARCH_SHARPE_MIN = 0.0
VALIDATED_B_SHARPE_MIN = 0.0

# Anti-clone: max cosine similarity to reject near-duplicates
MAX_SIMILARITY = 0.85


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
            new_conds = []
            for c in entry_conds if cond in entry_conds else exit_conds:
                new_conds.append(
                    re.sub(rf"rsi_14\s*{op}\s*{val}", f"rsi_14 {op} {adjusted}", c)
                )
            if cond in entry_conds:
                other_key = "exit_conditions"
                v3["entry_conditions"] = new_conds
                v3["exit_conditions"] = exit_conds
            else:
                v3["entry_conditions"] = entry_conds
                v3["exit_conditions"] = new_conds
            v3["_mutation_type"] = "rsi_threshold_shift"
            v3["_mutation_fields"] = ["rsi_14 threshold"]
            variants.append(v3)
            break

    return variants[:max_variants]


def _relax_threshold(cond: str, factor: float = 0.8) -> str:
    """Make an entry condition easier to satisfy (relax threshold)."""
    # Match patterns like "< 0.005", "> 2.5", "< -0.003"
    for pattern in [
        (r"(<)\s*(-?[\d.]+)", lambda m: f"< {float(m.group(2)) * factor:.4f}"),
        (
            r"(>)\s*(-?[\d.]+)",
            lambda m: (
                f"> {float(m.group(2)) * (1 / factor):.4f}"
                if float(m.group(2)) > 0
                else f"> {float(m.group(2)) * factor:.4f}"
            ),
        ),
    ]:
        match = re.search(pattern[0], cond)
        if match:
            return re.sub(pattern[0], pattern[1](match), cond)
    return cond


def _tighten_exit(cond: str, factor: float = 1.2) -> str:
    """Make an exit condition harder to trigger (tighten threshold)."""
    for pattern in [
        (r"(>)\s*(-?[\d.]+)", lambda m: f"> {float(m.group(2)) * factor:.4f}"),
        (r"(<)\s*(-?[\d.]+)", lambda m: f"< {float(m.group(2)) / factor:.4f}"),
    ]:
        match = re.search(pattern[0], cond)
        if match:
            return re.sub(pattern[0], pattern[1](match), cond)
    return cond


def _is_duplicate(
    spec: dict, existing_specs: list[dict], threshold: float = MAX_SIMILARITY
) -> bool:
    """Check if spec is too similar to existing ones."""
    for existing in existing_specs:
        sim = standardized_similarity(spec, existing)
        if sim < threshold:
            return True
    return False


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
            spec_to_save = {k: v for k, v in variant.items() if not k.startswith("_")}
            spec_to_save["name"] = f"{name}_mut_{mut_type}"

            # Anti-clone check
            if _is_duplicate(spec_to_save, existing_specs):
                logger.info(f"Skipping deterministic clone: {spec_to_save['name']}")
                continue

            child_id = await self.db_client.save_strategy(
                spec_to_save,
                status="pending_code",
                author_agent=f"{self.name}_deterministic",
            )
            mutated_ids.append((child_id, mut_type, mut_fields, spec_to_save))

        # --- Phase 2: Claude mutation (controlled) ---
        claude_spec = await self._claude_mutate(candidate, params)
        if claude_spec:
            claude_spec["name"] = f"{name}_mut_claude"

            # Anti-clone check
            if not _is_duplicate(
                claude_spec, existing_specs + [v[3] for v in mutated_ids]
            ):
                child_id = await self.db_client.save_strategy(
                    claude_spec,
                    status="pending_code",
                    author_agent=self.name,
                    prompt=self._build_claude_prompt(candidate),
                    raw_response=json.dumps(claude_spec),
                )
                mutated_ids.append(
                    (
                        child_id,
                        claude_spec.get("_mutation_type", "claude_refinement"),
                        claude_spec.get("_mutation_fields", ["unknown"]),
                        claude_spec,
                    )
                )

        # --- Record mutation lineage ---
        parent_metrics = {
            "sharpe": candidate.get("sharpe", candidate.get("holdout_sharpe", 0)),
            "entry_count": entry_c,
            "total_trades": trades,
        }
        for child_id, mut_type, mut_fields, _ in mutated_ids:
            await self.db_client.save_mutation_record(
                parent_id=strategy_id,
                child_id=child_id,
                mutation_type=mut_type,
                changed_fields=mut_fields,
                parent_metrics=parent_metrics,
                child_metrics={"sharpe": 0, "entry_count": 0, "total_trades": 0},
            )

        # Publish signals for new strategies
        messaging = MessagingClient(self._redis)
        for child_id, _, _, _ in mutated_ids:
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
        """Build the Claude prompt with failure memory."""
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
        drawdown = candidate.get("max_drawdown", 0)

        return f"""Strategy: {name}
Current Sharpe: {sharpe:.2f}
Entry signals: {entry_c}
Total trades: {trades}
Max Drawdown: {drawdown:.1f}%

DIAGNOSTIC: {diagnostic}

Current Spec:
{json.dumps(params, indent=2)}

Mutate conservatively. Output valid JSON with: strategy_name, hypothesis, entry_conditions, exit_conditions, stop_loss, take_profit, position_sizing, timeframe, asset_class, tags, mutation_type, changed_fields, changes"""

    async def _get_recent_mutants(self, limit: int = 50) -> list[dict]:
        """Get recently-created strategies for anti-clone comparison."""
        async with self.db_client.engine.connect() as conn:
            from sqlalchemy import text

            result = await conn.execute(
                text("""
                    SELECT normalized_strategy FROM strategies
                    WHERE author_agent LIKE '%Mutator%' OR author_agent LIKE '%mutator%'
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
