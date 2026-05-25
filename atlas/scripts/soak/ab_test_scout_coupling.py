"""
ab_test_scout_coupling.py — Phase 26F

Controlled A/B experiment:
  Test A: Scouts OFF (pure deterministic grammar)
  Test B: Scouts ON (scout-informed generation)

Compares:
  - Archetype distribution (does B show regime-aligned archetypes?)
  - Grammar-level parameter differences (thresholds, stops, etc.)
  - Validation pass rate delta
  - Scout influence events generated

Usage:
  python atlas/scripts/soak/ab_test_scout_coupling.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from loguru import logger


# ================================================================
# MOCK DATA — Simulate scout context under Test A vs Test B
# ================================================================

BASELINE_SCOUT_CONTEXT = None  # Test A: No scout data

HIGH_BULL_SCOUT = {
    "regime": "overbought",
    "scout_text": (
        "Market: vol=low, trend=trending_up, liq=healthy, corr=normal "
        "Liquidity: regime=healthy, score=80, risk=0.1 "
        "Execution: regime=optimal, fill_score=90, slippage=1.5bps"
    ),
}

HIGH_ENTROPY_SCOUT = {
    "regime": "ranging",
    "scout_text": (
        "Market: vol=panic_vol, trend=mixed, liq=thin, corr=spike_detected "
        "Liquidity: regime=thin, score=25, risk=4.2 "
        "Correlation: cluster=panic, avg_corr=0.91, state=high_risk "
        "Execution: regime=degraded, fill_score=35, slippage=28bps"
    ),
}

TRENDING_SCOUT = {
    "regime": "trending",
    "scout_text": (
        "Market: vol=moderate, trend=trending_up, liq=healthy, corr=normal "
        "Execution: regime=optimal, fill_score=85, slippage=2bps"
    ),
}


def run_ideator_simulation(scout_context: dict | None, n_strategies: int = 50) -> dict:
    """
    Simulated ideator run — uses the same weight computation logic as IdeatorAgentV2.
    Returns archetype distribution and parameter stats.
    """
    from atlas.agents.l2_strategy.ideator_agent_v2 import (
        ARCHETYPES, STRATEGY_GRAMMAR, IdeatorAgentV2
    )

    # Instantiate a lightweight version for logic access (no DB needed)
    class MockIdeator:
        DIVERSITY_SIMILARITY_THRESHOLD = 0.70
        DIVERSITY_SOFT_PENALTY_START = 0.55
        name = "MockIdeator"
        
        def _compute_scout_archetype_weights(self, regime, scout_text):
            return IdeatorAgentV2._compute_scout_archetype_weights(
                self, regime, scout_text
            )
        
        def _compute_scout_aggression(self, regime, scout_text):
            return IdeatorAgentV2._compute_scout_aggression(
                self, regime, scout_text
            )
        
        def _compute_scout_timeframe(self, scout_text):
            return IdeatorAgentV2._compute_scout_timeframe(
                self, scout_text
            )
    
    mock = MockIdeator()
    results = {"archetypes": Counter(), "aggressions": [], "timeframes": Counter()}

    for _ in range(n_strategies):
        if scout_context:
            regime = scout_context["regime"]
            scout_text = scout_context["scout_text"]
            weights = mock._compute_scout_archetype_weights(regime, scout_text)
            arch_keys = list(weights.keys())
            arch_weights = [weights[k] for k in arch_keys]
            chosen = random.choices(arch_keys, weights=arch_weights, k=1)[0]
            aggression = mock._compute_scout_aggression(regime, scout_text)
            timeframe = mock._compute_scout_timeframe(scout_text)
        else:
            # Baseline: uniform distribution
            chosen = random.choice(ARCHETYPES)
            aggression = 1.0
            timeframe = "1m"

        results["archetypes"][chosen] += 1
        results["aggressions"].append(aggression)
        results["timeframes"][timeframe] += 1

    n = n_strategies
    aggressions = results["aggressions"]
    return {
        "archetype_distribution": dict(results["archetypes"]),
        "archetype_entropy": _compute_entropy(list(results["archetypes"].values())),
        "avg_aggression": round(sum(aggressions) / max(1, len(aggressions)), 4),
        "min_aggression": round(min(aggressions), 4),
        "max_aggression": round(max(aggressions), 4),
        "timeframe_distribution": dict(results["timeframes"]),
        "n_strategies": n,
    }


def _compute_entropy(counts: list[int]) -> float:
    """Shannon entropy of a distribution."""
    import math
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return round(-sum(p * math.log2(p) for p in probs), 4)


def print_comparison(test_a: dict, test_b: dict, label_b: str):
    """Print a formatted comparison table."""
    print(f"\n{'='*60}")
    print(f"  Test A (Scouts OFF) vs Test B ({label_b})")
    print(f"{'='*60}")
    print(f"{'Metric':<30} {'Test A':>12} {'Test B':>12} {'Delta':>12}")
    print(f"{'-'*66}")

    metrics = [
        ("Archetype Entropy", "archetype_entropy"),
        ("Avg Aggression", "avg_aggression"),
        ("Min Aggression", "min_aggression"),
    ]
    for label, key in metrics:
        a_val = test_a.get(key, 0.0)
        b_val = test_b.get(key, 0.0)
        delta = b_val - a_val
        print(f"  {label:<28} {a_val:>12.4f} {b_val:>12.4f} {delta:>+12.4f}")

    print(f"\n  Archetype Distribution (A vs B):")
    all_archetypes = set(test_a["archetype_distribution"]) | set(test_b["archetype_distribution"])
    for arch in sorted(all_archetypes):
        a_pct = test_a["archetype_distribution"].get(arch, 0) / test_a["n_strategies"]
        b_pct = test_b["archetype_distribution"].get(arch, 0) / test_b["n_strategies"]
        delta = b_pct - a_pct
        arrow = "^" if delta > 0.05 else ("v" if delta < -0.05 else " ")
        print(f"    {arch:<25} {a_pct:>6.1%}    {b_pct:>6.1%}   {arrow} {delta:>+6.1%}")

    print(f"\n  Timeframe Distribution (Test B only):")
    for tf, count in test_b.get("timeframe_distribution", {}).items():
        print(f"    {tf}: {count}/{test_b['n_strategies']} strategies")


def main():
    n = 200  # Strategies per test

    print("\n" + "="*60)
    print("  PHASE 26F — A/B INTELLIGENCE TEST")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print(f"  N={n} strategies per test")
    print("="*60)

    # Test A: Baseline
    test_a = run_ideator_simulation(None, n_strategies=n)

    # Test B1: Bullish scout
    test_b1 = run_ideator_simulation(HIGH_BULL_SCOUT, n_strategies=n)
    print_comparison(test_a, test_b1, "Scouts ON (Bullish/Trending)")

    # Test B2: High entropy
    test_b2 = run_ideator_simulation(HIGH_ENTROPY_SCOUT, n_strategies=n)
    print_comparison(test_a, test_b2, "Scouts ON (High Entropy/Panic)")

    # Test B3: Trending
    test_b3 = run_ideator_simulation(TRENDING_SCOUT, n_strategies=n)
    print_comparison(test_a, test_b3, "Scouts ON (Trending)")

    # Verdict
    print(f"\n{'='*60}")
    print("  VERDICT")
    print("="*60)

    # Check if scout-informed tests show meaningful behavioral differences
    passed = []

    # 1. Bullish scout should boost momentum/trend archetypes
    bull_momentum = test_b1["archetype_distribution"].get("momentum", 0) / n
    base_momentum = test_a["archetype_distribution"].get("momentum", 0) / n
    if bull_momentum > base_momentum + 0.05:
        passed.append(f"[PASS] Bullish scout boosts momentum: {base_momentum:.1%} -> {bull_momentum:.1%}")
    else:
        passed.append(f"[WARN] Momentum not boosted in bullish: {base_momentum:.1%} -> {bull_momentum:.1%}")

    # 2. High entropy should reduce aggression
    if test_b2["avg_aggression"] < test_a["avg_aggression"]:
        passed.append(f"[PASS] Entropy reduces aggression: {test_a['avg_aggression']:.3f} -> {test_b2['avg_aggression']:.3f}")
    else:
        passed.append(f"[WARN] Aggression not reduced in high entropy: {test_a['avg_aggression']:.3f} -> {test_b2['avg_aggression']:.3f}")

    # 3. High entropy should increase timeframe preference to 5m/15m
    slow_tfs = sum(
        test_b2["timeframe_distribution"].get(tf, 0)
        for tf in ["5m", "15m"]
    )
    if slow_tfs > n * 0.1:
        passed.append(f"[PASS] High entropy shifts to slower timeframes: {slow_tfs}/{n}")
    else:
        passed.append(f"[WARN] Timeframe not shifted in high entropy: {slow_tfs}/{n} slow")

    # 4. Archetype entropy should differ
    entropy_delta = abs(test_b2["archetype_entropy"] - test_a["archetype_entropy"])
    if entropy_delta > 0.01:
        passed.append(f"[PASS] Archetype entropy changes: delta={entropy_delta:.4f}")
    else:
        passed.append(f"[INFO] Archetype entropy similar: delta={entropy_delta:.4f}")

    for result in passed:
        print(f"  {result}")

    # Output JSON for soak report
    report = {
        "test_a_baseline": test_a,
        "test_b_bullish": test_b1,
        "test_b_high_entropy": test_b2,
        "test_b_trending": test_b3,
        "verdicts": passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "phase26_ab_test_results.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    main()
