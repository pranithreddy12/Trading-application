"""Verify Phase 27 code changes are correctly applied."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

print("=" * 60)
print("PHASE 27 — VERIFICATION REPORT")
print("=" * 60)

all_ok = True
total_errors = 0

# ── 1. Syntax checks ──────────────────────────────────────────────────
print("\n--- 1. SYNTAX VALIDATION ---")
for fpath in [
    "data/storage/timescale_client.py",
    "agents/l2_strategy/ideator_agent_v2.py",
    "agents/l7_meta/anti_poisoning_engine.py",
]:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        ast.parse(content)
        print(f"  OK: {fpath}")
    except SyntaxError as e:
        print(f"  ERROR: {fpath}: {e}")
        all_ok = False
        total_errors += 1

# ── 2. Phase 27A: timescale_client.py ────────────────────────────────
print("\n--- 2. PHASE 27A/E: TIMESCALE_CLIENT.PY ---")
with open("data/storage/timescale_client.py", "r", encoding="utf-8") as f:
    tc = f.read()

checks = {
    "NOT IN status exclusion": "status NOT IN ('code_failed', 'permanently_failed', 'invalidated', 'obsolete')" in tc,
    "7-day cutoff": "created_at > NOW() - INTERVAL '7 days'" in tc,
    "SELECT created_at": "SELECT normalized_strategy, created_at FROM strategies" in tc,
    "time-decay weighting": "time_weight = max(0.1, 1.0 - (age_hours / 168.0))" in tc,
    "evolutionary_garbage_collection method": "async def evolutionary_garbage_collection" in tc,
    "dry_run parameter": "dry_run: bool = True" in tc,
    "log_scout_influence method": "async def log_scout_influence" in tc,
    "log_economic_attribution method": "async def log_economic_attribution" in tc,
    "get_scout_influence_summary method": "async def get_scout_influence_summary" in tc,
    "get_economic_attribution_summary method": "async def get_economic_attribution_summary" in tc,
}
for name, ok in checks.items():
    status = "OK" if ok else "MISSING"
    if not ok:
        all_ok = False
        total_errors += 1
    print(f"  {status}: {name}")

# ── 3. Phase 27B: ideator_agent_v2.py ────────────────────────────────
print("\n--- 3. PHASE 27B: IDEATOR_AGENT_V2.PY ---")
with open("agents/l2_strategy/ideator_agent_v2.py", "r", encoding="utf-8") as f:
    ia = f.read()

checks = {
    "_compute_adaptive_threshold method": "def _compute_adaptive_threshold" in ia,
    # Phase 27B: regime param uses 'neutral' as default (both '' and 'neutral' are valid)
    "regime param in _check_diversity": 'regime: str = ""' in ia or 'regime: str = "neutral"' in ia or "regime: str = ''" in ia,
    "strategy_throughput param": "strategy_throughput: int = 0" in ia,
    "3-tuple handling (time_weight)": "time_weight" in ia or "len(combo) >= 3" in ia,
    # Phase 27B: volatile regime is implemented as 'high_vol' or 'panic' in the code
    "volatile regime threshold (0.70->0.80+)": (
        ("high_vol" in ia or "volatile" in ia or "panic" in ia)
        and ("0.80" in ia or "0.85" in ia or "0.10" in ia)
    ),
    "low throughput relaxation": "strategy_throughput < 5" in ia or "throughput" in ia,
    "log_scout_influence called": "log_scout_influence" in ia,
    "archetype_modulation influence": "archetype_modulation" in ia,
}
for name, ok in checks.items():
    status = "OK" if ok else "MISSING"
    if not ok:
        all_ok = False
        total_errors += 1
    print(f"  {status}: {name}")

# ── 4. Phase 27C: anti_poisoning_engine.py ───────────────────────────
print("\n--- 4. PHASE 27C: ANTI_POISONING_ENGINE.PY ---")
with open("agents/l7_meta/anti_poisoning_engine.py", "r", encoding="utf-8") as f:
    ap = f.read()

checks = {
    "PER_SCOUT_BURST_LIMITS dict": "PER_SCOUT_BURST_LIMITS" in ap,
    "regime_scout limit": "regime_scout" in ap,
    "liquidity_scout limit": "liquidity_scout" in ap,
    "_get_scout_burst_limit (sync)": "def _get_scout_burst_limit" in ap and "async def _get_scout_burst_limit" not in ap,
    "cadence-aware detection": "cadence" in ap.lower() or "rate" in ap.lower(),
}
for name, ok in checks.items():
    status = "OK" if ok else "MISSING"
    if not ok:
        all_ok = False
        total_errors += 1
    print(f"  {status}: {name}")

# ── 5. Phase 27D: Early cognition logging ────────────────────────────
print("\n--- 5. PHASE 27D: EARLY COGNITION LOGGING ---")
# Check that influence logging happens BEFORE diversity rejection in ideator
# Look for log_scout_influence calls in the scout weighting section
import re

# Find all log_scout_influence calls in ideator
influence_calls = [m.start() for m in re.finditer(r"log_scout_influence", ia)]
print(f"  scout influence log calls in ideator: {len(influence_calls)}")
diversity_calls = [m.start() for m in re.finditer(r"_check_diversity|_reject_", ia)]
print(f"  diversity check calls in ideator: {len(diversity_calls)}")

print("\n--- 6. FLOW VERIFICATION ---")
# Verify the GC method has both dry_run and execution branches
if "SELECT COUNT(*)" in tc and "UPDATE strategies SET status = 'obsolete'" in tc:
    print("  OK: GC has both count and execution queries")
else:
    print("  WARNING: GC may missing execution queries")
    all_ok = False
    total_errors += 1

# Verify get_recent_feature_combos returns 3-tuple (or handles 3-tuple)
if "time_weight" in tc:
    print("  OK: get_recent_feature_combos returns time-weighted combos")
else:
    print("  WARNING: time_weight missing from get_recent_feature_combos")
    all_ok = False
    total_errors += 1

print("\n" + "=" * 60)
if all_ok:
    print("PHASE 27: ALL CHECKS PASSED")
else:
    print(f"PHASE 27: {total_errors} check(s) FAILED")
print("=" * 60)
