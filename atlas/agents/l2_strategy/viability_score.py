"""
Expected Viability Score — pre-save mutation quality scoring.

Scores a mutation spec before saving based on:
  - Structural realism (entry/exit balance, condition count)
  - Entry likelihood (predicted signal frequency)
  - Complexity penalty (overfitting risk)
  - Novelty vs parent (Jaccard distance)
  - Parent weakness match (does the mutation address the parent's known failure?)

Score range: 0.0 (inviable) to 1.0 (highly promising).
"""

from __future__ import annotations

from typing import Optional

from atlas.agents.l2_strategy.condition_parser import spec_condition_stats


def compute_viability_score(
    child_spec: dict,
    parent_params: Optional[dict] = None,
    parent_failure: Optional[dict] = None,
) -> float:
    """
    Compute expected viability score [0.0, 1.0] for a mutation before saving.

    Factors:
      1. Structural soundness (0.0-0.25) — entry count, exit presence, total balance
      2. Complexity discipline (0.0-0.20) — not overfit, not trivial
      3. Novelty vs parent   (0.0-0.20) — feature diversity gain
      4. Parent weakness match (0.0-0.20) — addresses known failure mode
      5. Entry likelihood     (0.0-0.15) — predicted signal availability

    Returns score 0.0-1.0.
    """
    scores = {}
    child_stats = spec_condition_stats(child_spec)
    parent_stats = spec_condition_stats(parent_params or {})

    # 1. Structural soundness (0.0-0.25)
    scores["structural"] = _score_structural(child_stats)

    # 2. Complexity discipline (0.0-0.20)
    scores["complexity"] = _score_complexity(child_stats)

    # 3. Novelty vs parent (0.0-0.20)
    scores["novelty"] = _score_novelty(child_stats, parent_stats)

    # 4. Parent weakness match (0.0-0.20)
    scores["weakness_match"] = _score_weakness_match(
        child_spec, parent_params, parent_failure
    )

    # 5. Entry likelihood (0.0-0.15)
    scores["entry_likelihood"] = _score_entry_likelihood(child_stats, parent_stats)

    total = sum(scores.values())
    return round(min(total, 1.0), 4)


def _score_structural(stats: dict) -> float:
    """Score structural soundness: entry/exit balance, condition count."""
    entry = stats.get("entry_count", 0)
    exit_ = stats.get("exit_count", 0)
    total = stats.get("total_conditions", 0)

    if entry == 0:
        return 0.0
    if total > 6:
        return 0.05
    if total >= 2 and exit_ >= 1:
        return 0.25
    if total >= 2:
        return 0.20
    return 0.10


def _score_complexity(stats: dict) -> float:
    """Score complexity discipline: penalty for too many features or sparse conditions."""
    features = stats.get("feature_diversity", 0)
    total = stats.get("total_conditions", 0)

    if features >= 4:
        return 0.05
    if features >= 2 and total <= 4:
        return 0.20
    if total == 0:
        return 0.0
    return 0.15


def _score_novelty(child_stats: dict, parent_stats: dict) -> float:
    """Score novelty: new features added vs parent."""
    if not parent_stats.get("features_used"):
        return 0.20
    child_features = set(child_stats.get("features_used", []))
    parent_features = set(parent_stats.get("features_used", []))
    if not child_features:
        return 0.0
    if child_features == parent_features:
        return 0.05
    new_features = child_features - parent_features
    ratio = len(new_features) / len(child_features) if child_features else 0
    return min(0.20, ratio * 0.30)


def _score_weakness_match(
    child_spec: dict,
    parent_params: Optional[dict],
    parent_failure: Optional[dict],
) -> float:
    """Score whether the mutation addresses the parent's known failure mode."""
    if not parent_failure:
        return 0.10
    child_entry = child_spec.get("entry_conditions", [])
    parent_entry = parent_params.get("entry_conditions", []) if parent_params else []
    entry_c = parent_failure.get("entry_count", 0)
    sharpe = parent_failure.get("sharpe", 0)

    score = 0.05
    if entry_c is not None and entry_c < 5 and len(child_entry) <= len(parent_entry):
        score += 0.10
    if entry_c is not None and entry_c < 5 and child_entry != parent_entry:
        score += 0.05
    if sharpe is not None and sharpe < 0:
        score += 0.05
    return min(score, 0.20)


def _score_entry_likelihood(child_stats: dict, parent_stats: dict) -> float:
    """Score entry likelihood based on condition structure changes."""
    child_entry = child_stats.get("entry_count", 0)
    parent_entry = parent_stats.get("entry_count", 0)

    if child_entry == 0:
        return 0.0
    if child_entry >= 3:
        return 0.05
    if child_entry < parent_entry:
        return 0.05
    if child_entry == parent_entry:
        return 0.08
    return 0.15


def classify_viability(score: float) -> str:
    """Classify a viability score into a human-readable band."""
    if score >= 0.80:
        return "highly_promising"
    if score >= 0.60:
        return "promising"
    if score >= 0.40:
        return "neutral"
    if score >= 0.20:
        return "risky"
    return "inviable"
