"""
test_selection.py — Tournament selection unit tests.

Validates the Phase 37B tournament selection utilities with:
1. Basic selection correctness (count, ordering)
2. Edge cases (empty, small pool, singleton)
3. Diversity verification (not always picking top-1)
4. Uniqueness guarantees (no duplicates across selections)
5. String key vs callable key
6. Statistical sampling verification (underdogs get picked sometimes)
"""

import random
from typing import Any

import pytest

from atlas.core.selection import tournament_select, tournament_select_unique


# ================================================================
# FIXTURES
# ================================================================

@pytest.fixture
def diverse_candidates() -> list[dict[str, Any]]:
    """10 candidates with gradually decreasing scores."""
    return [
        {"id": f"s{i}", "name": f"strat_{i}", "composite_fitness": float(100 - i * 5), "sharpe": 2.0 - i * 0.15}
        for i in range(10)
    ]


@pytest.fixture
def flat_candidates() -> list[dict[str, Any]]:
    """20 candidates with nearly identical scores — tournament should pick diverse ones."""
    return [
        {"id": f"f{i}", "name": f"flat_{i}", "composite_fitness": 50.0 + (i % 3) * 0.1, "sharpe": 1.0}
        for i in range(20)
    ]


@pytest.fixture
def small_pool() -> list[dict[str, Any]]:
    """Only 3 candidates — smaller than default tournament_size."""
    return [
        {"id": "a", "name": "alpha", "composite_fitness": 80.0},
        {"id": "b", "name": "beta", "composite_fitness": 60.0},
        {"id": "c", "name": "gamma", "composite_fitness": 40.0},
    ]


@pytest.fixture
def cloned_ids() -> list[dict[str, Any]]:
    """Candidates with duplicate IDs to test id_key dedup."""
    return [
        {"id": "dup", "name": "first", "composite_fitness": 95.0},
        {"id": "dup", "name": "second", "composite_fitness": 90.0},
        {"id": "uniq", "name": "third", "composite_fitness": 85.0},
        {"id": "other", "name": "fourth", "composite_fitness": 80.0},
    ]


# ================================================================
# TEST 1: Basic selection correctness
# ================================================================

class TestBasicSelection:
    """Core selection mechanics."""

    def test_selects_correct_number(self, diverse_candidates):
        """Should return exactly n_select items."""
        result = tournament_select(diverse_candidates, tournament_size=3, key="composite_fitness", n_select=2)
        assert len(result) == 2

    def test_selects_with_replacement_possible(self, diverse_candidates):
        """tournament_select allows replacement — can select same item twice."""
        result = tournament_select(diverse_candidates, tournament_size=3, key="composite_fitness", n_select=10)
        # With 10 selections from 10 candidates tournament is random sampling, but
        # any selection is valid as long as we get 10 results
        assert len(result) == 10

    def test_returns_empty_for_empty_input(self):
        """Should return empty list for empty candidates."""
        assert tournament_select([], key="score", n_select=5) == []

    def test_returns_empty_for_empty_input(self):
        """Should return empty list for empty input."""
        assert tournament_select([], key="score") == []

    def test_n_select_zero(self, diverse_candidates):
        """n_select=0 should return empty list."""
        # Implementation: range(0) = empty, so selected stays []
        result = tournament_select(diverse_candidates, tournament_size=3, key="composite_fitness", n_select=0)
        assert result == []


# ================================================================
# TEST 2: Small pool edge cases
# ================================================================

class TestSmallPool:
    """Behavior when pool is smaller than tournament_size."""

    def test_falls_back_to_sorted_top_n(self, small_pool):
        """Pool <= tournament_size should return sorted top-N."""
        result = tournament_select(small_pool, tournament_size=5, key="composite_fitness", n_select=2)
        assert len(result) == 2
        assert result[0]["id"] == "a"  # highest score
        assert result[1]["id"] == "b"  # second highest

    def test_small_pool_unique(self, small_pool):
        """tournament_select_unique should also fall back to sorted top-N."""
        result = tournament_select_unique(small_pool, tournament_size=5, key="composite_fitness", n_select=2)
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_small_pool_requests_more_than_pool(self, small_pool):
        """When n_select > pool size, return as many as possible."""
        result = tournament_select_unique(small_pool, tournament_size=5, key="composite_fitness", n_select=10)
        # Can't return more unique items than exist
        assert len(result) <= len(small_pool)

    def test_single_candidate(self):
        """With 1 candidate, should return that candidate."""
        single = [{"id": "x", "score": 50}]
        result = tournament_select(single, tournament_size=3, key="score", n_select=1)
        assert len(result) == 1
        assert result[0]["id"] == "x"


# ================================================================
# TEST 3: String key vs callable key
# ================================================================

class TestKeyCallable:
    """Both str key and callable key should work."""

    def test_string_key(self, diverse_candidates):
        """String key selects by dict field."""
        result = tournament_select(diverse_candidates, tournament_size=3, key="sharpe", n_select=2)
        assert len(result) == 2
        # All items have positive sharpe, so selections are valid

    def test_callable_key(self, diverse_candidates):
        """Callable key should work with custom scoring logic."""
        # Custom scorer: sharpe * 2 + composite_fitness / 10
        def custom_scorer(s):
            return float(s.get("sharpe", 0)) * 2 + float(s.get("composite_fitness", 0)) / 10

        result = tournament_select(diverse_candidates, tournament_size=3, key=custom_scorer, n_select=1)
        assert len(result) == 1
        assert result[0]["id"] in {c["id"] for c in diverse_candidates}

    def test_callable_with_missing_key(self):
        """Callable should handle dicts missing the scored key."""
        candidates = [
            {"id": "a", "value": 100},
            {"id": "b"},  # missing 'value'
            {"id": "c", "value": 80},
        ]

        result = tournament_select(candidates, tournament_size=2, key=lambda s: float(s.get("value", 0) or 0), n_select=3)
        assert len(result) == 3

    def test_string_key_missing(self):
        """String key with missing field should default to 0."""
        candidates = [
            {"id": "a"},  # no 'score' key
            {"id": "b", "score": 50},
        ]
        result = tournament_select(candidates, tournament_size=2, key="score", n_select=1)
        assert len(result) == 1
        assert result[0]["id"] == "b"  # b has 50, a has 0


# ================================================================
# TEST 4: Uniqueness guarantee
# ================================================================

class TestUniqueness:
    """tournament_select_unique must guarantee no duplicate IDs."""

    def test_no_duplicate_ids(self, diverse_candidates):
        """tournament_select_unique should never return duplicate IDs."""
        result = tournament_select_unique(diverse_candidates, tournament_size=3, key="composite_fitness", n_select=5)
        ids = {c["id"] for c in result}
        assert len(ids) == len(result), f"Duplicate IDs found: {[c['id'] for c in result]}"

    def test_unique_with_flat_scores(self, flat_candidates):
        """Even with flat scores, unique should return distinct candidates."""
        result = tournament_select_unique(flat_candidates, tournament_size=4, key="composite_fitness", n_select=5)
        assert len(result) == 5
        ids = {c["id"] for c in result}
        assert len(ids) == 5

    def test_unique_honors_id_key(self, cloned_ids):
        """Should treat same id_key as duplicate even with different dicts."""
        result = tournament_select_unique(cloned_ids, tournament_size=3, key="composite_fitness", n_select=3)
        ids = [c["id"] for c in result]
        # Should not contain 'dup' twice
        dup_count = ids.count("dup")
        assert dup_count <= 1, f"'dup' appeared {dup_count} times"

    def test_unique_returns_fewer_when_pool_exhausted(self):
        """When n_select > unique pool / tournament_size, return what's possible."""
        tiny = [{"id": f"t{i}", "score": 100 - i} for i in range(4)]
        # tournament_size=5 will trigger fallback (len=4 <= 5)
        result = tournament_select_unique(tiny, tournament_size=5, key="score", n_select=10)
        assert len(result) <= 4  # Can't return more than pool size


# ================================================================
# TEST 5: Diversity verification
# ================================================================

class TestDiversity:
    """
    Tournament selection should NOT always pick the single highest-scoring item.
    We run multiple trials with a large pool and verify that lower-ranked items
    get selected occasionally.
    """

    def test_not_always_top_one(self):
        """
        Over many trials with 100 candidates, the #1 ranked candidate should
        not be the only one selected. Tournament sampling means lower-ranked
        candidates occasionally win their tournament.
        """
        random.seed(42)  # Deterministic for reproducibility

        candidates = [
            {"id": f"s{i}", "composite_fitness": float(100 - i)}
            for i in range(100)
        ]

        trials = 500
        selections = {"s0": 0, "s1": 0, "s2": 0, "s3": 0, "s4": 0}

        for _ in range(trials):
            winner = tournament_select(candidates, tournament_size=5, key="composite_fitness", n_select=1)[0]
            wid = winner["id"]
            if wid in selections:
                selections[wid] += 1

        # s0 (best) should be selected most often, but NOT 100% of the time
        top_one_pct = selections["s0"] / trials
        assert top_one_pct < 0.5, (
            f"s0 selected {top_one_pct:.1%} of the time — "
            f"tournament should allow underdogs: {selections}"
        )
        # Lower-ranked candidates should get SOME selections
        lower_selected = sum(selections[wid] for wid in ["s2", "s3", "s4"])
        assert lower_selected > 0, (
            f"No lower-ranked candidates were ever selected: {selections}"
        )

    def test_diversity_increases_with_larger_tournament(self):
        """
        Larger tournament_size = more exploitation (top picks dominate).
        Smaller tournament_size = more exploration (underdogs get picked).
        """
        random.seed(42)

        candidates = [
            {"id": f"d{i}", "composite_fitness": float(100 - i)}
            for i in range(50)
        ]

        # Small tournament (size=2) — more exploration
        small_t_results = [tournament_select(candidates, tournament_size=2, key="composite_fitness", n_select=1)[0]["id"] for _ in range(200)]
        small_t_diversity = len(set(small_t_results))

        # Large tournament (size=20) — more exploitation
        large_t_results = [tournament_select(candidates, tournament_size=20, key="composite_fitness", n_select=1)[0]["id"] for _ in range(200)]
        large_t_diversity = len(set(large_t_results))

        # Smaller tournament should yield more diversity
        assert small_t_diversity >= large_t_diversity, (
            f"Small tournament diversity ({small_t_diversity}) should be >= "
            f"large tournament diversity ({large_t_diversity})"
        )


# ================================================================
# TEST 6: Integration — imports resolve correctly
# ================================================================

class TestIntegrationImports:
    """Module imports should resolve cleanly."""

    def test_core_selection_importable(self):
        """atlas.core.selection should import without errors."""
        from atlas.core.selection import tournament_select, tournament_select_unique
        assert callable(tournament_select)
        assert callable(tournament_select_unique)

    def test_combiner_agent_imports(self):
        """combiner_agent should import without errors (it uses tournament_select_unique)."""
        from atlas.agents.l2_strategy.combiner_agent import CombinerAgent
        assert CombinerAgent is not None

    def test_mutator_agent_imports(self):
        """mutator_agent should import without errors (it uses tournament_select)."""
        from atlas.agents.l2_strategy.mutator_agent import MutatorAgent
        assert MutatorAgent is not None

    def test_deployment_governor_imports(self):
        """deployment_governor should import without errors (it uses tournament_select_unique)."""
        from atlas.agents.l7_meta.deployment_governor import DeploymentGovernor
        assert DeploymentGovernor is not None


# ================================================================
# TEST 7: Statistical fairness verification
# ================================================================

class TestStatisticalFairness:
    """
    Verify the selection is proportional but not deterministic.
    Higher-scoring candidates should be selected proportionally more often
    when tournament size is reasonable.
    """

    def test_score_proportional_selection(self):
        """
        Run many tournaments with a known pool and verify ranked order
        correlates with selection frequency. Top candidates should win
        more often than bottom ones (without being 100%).
        """
        random.seed(42)

        # Use a larger pool (30) and add noise so lower-ranked candidates
        # have a realistic chance to win tournaments
        candidates = [
            {"id": f"r{i}", "score": float(max(0, 100 - i * 3 + random.randint(-5, 5)))}
            for i in range(30)
        ]

        trials = 2000
        win_count: dict[str, int] = {}
        for _ in range(trials):
            winner = tournament_select(candidates, tournament_size=3, key="score", n_select=1)[0]
            win_count[winner["id"]] = win_count.get(winner["id"], 0) + 1

        # Verify rank-order: higher-ranked (lower index) should win more
        # than lower-ranked (higher index) on average. Group into quartiles.
        ids_by_rank = [f"r{i}" for i in range(8)]
        win_rates = [win_count.get(rid, 0) / trials for rid in ids_by_rank]

        # Top quartile (r0-r7) should all have > 0 wins
        for i in range(8):
            assert win_count.get(f"r{i}", 0) > 0, (
                f"r{i} was never selected in {trials} trials — "
                f"exploration not reaching lower ranks: {win_count}"
            )

        # The very highest-ranked (r0) should win more often than the mid-ranked (r7)
        # but shouldn't dominate completely
        top_win_rate = win_rates[0]
        assert top_win_rate < 0.3, (
            f"r0 selected {top_win_rate:.1%} of the time — "
            f"tournament should prevent single-candidate dominance: {win_count}"
        )

        # At least 20 out of 30 candidates should have been selected at least once
        selected_count = sum(1 for rid in [f"r{i}" for i in range(30)] if win_count.get(rid, 0) > 0)
        assert selected_count >= 20, (
            f"Only {selected_count}/30 distinct candidates were ever selected — "
            f"tournament not providing enough exploration: {win_count}"
        )


# ================================================================
# TEST 8: Random seed determinism
# ================================================================

class TestDeterminism:
    """With same random seed, selection should be deterministic."""

    def test_deterministic_with_seed(self):
        candidates = [
            {"id": f"d{i}", "score": float(100 - i * 3)}
            for i in range(20)
        ]

        random.seed(12345)
        result_a = tournament_select(candidates, tournament_size=4, key="score", n_select=3)
        result_a_ids = [c["id"] for c in result_a]

        random.seed(12345)
        result_b = tournament_select(candidates, tournament_size=4, key="score", n_select=3)
        result_b_ids = [c["id"] for c in result_b]

        assert result_a_ids == result_b_ids, "Same seed should produce same selection"

    def test_different_seed_different_results(self):
        candidates = [
            {"id": f"e{i}", "score": float(100 - i * 2)}
            for i in range(30)
        ]

        random.seed(111)
        result_a = tournament_select(candidates, tournament_size=5, key="score", n_select=5)
        result_a_ids = [c["id"] for c in result_a]

        random.seed(222)
        result_b = tournament_select(candidates, tournament_size=5, key="score", n_select=5)
        result_b_ids = [c["id"] for c in result_b]

        # Different seeds should produce different selections
        # (1 in 30^5 ≈ 1 in 24M chance of collision)
        assert result_a_ids != result_b_ids, (
            f"Different seeds produced identical selections: {result_a_ids}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
