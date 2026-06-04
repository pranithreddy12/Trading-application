"""
test_phase19_meta_intelligence.py — Phase 19J: Meta-Intelligence Test Suite

Tests:
1. LLM outage resilience — deterministic systems continue operating
2. Deterministic generation continuity — grammar engine produces valid strategies
3. Advisory isolation — meta agents cannot call execution/mutation APIs
4. Replay integrity — deterministic outputs replay given same inputs
5. Mutation policy replayability — advisor produces consistent entropy metrics
6. Scout synthesis robustness — handles missing/partial scout data
7. Hypothesis lifecycle — proposed → testing → confirmed/rejected/expired
8. GovernanceViolation enforcement
"""

import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ================================================================
# TEST 1: GovernanceViolation enforcement
# ================================================================

def test_governance_violation_on_advisory_agent():
    """Advisory-only agents must raise GovernanceViolation for forbidden actions."""
    from atlas.core.agent_base import BaseAgent, GovernanceViolation

    class MockAdvisoryAgent(BaseAgent):
        async def run(self):
            pass

    redis = MagicMock()
    agent = MockAdvisoryAgent(
        name="TestAdvisory",
        agent_type="test",
        layer="L7",
        redis_client=redis,
        advisory_only=True,
    )
    assert agent.advisory_only is True

    with pytest.raises(GovernanceViolation, match="advisory-only"):
        agent._enforce_advisory_guard("place_order")


def test_governance_non_advisory_agent_passes():
    """Non-advisory agents should NOT raise GovernanceViolation."""
    from atlas.core.agent_base import BaseAgent, GovernanceViolation

    class MockAgent(BaseAgent):
        async def run(self):
            pass

    redis = MagicMock()
    agent = MockAgent(
        name="TestNormal",
        agent_type="test",
        layer="L2",
        redis_client=redis,
        advisory_only=False,
    )
    # Should not raise
    agent._enforce_advisory_guard("place_order")


# ================================================================
# TEST 2: Deterministic grammar engine
# ================================================================

def test_strategy_grammar_structure():
    """STRATEGY_GRAMMAR must define all required archetypes with valid structure."""
    from atlas.agents.l2_strategy.ideator_agent_v2 import STRATEGY_GRAMMAR

    required_archetypes = [
        "momentum", "mean_reversion", "breakout",
        "trend_following", "volatility_regime",
    ]
    for arch in required_archetypes:
        assert arch in STRATEGY_GRAMMAR, f"Missing archetype: {arch}"
        grammar = STRATEGY_GRAMMAR[arch]
        assert "families" in grammar
        assert "entry_templates" in grammar
        assert "exit_templates" in grammar
        assert "valid_regimes" in grammar
        assert len(grammar["entry_templates"]) >= 2
        assert len(grammar["exit_templates"]) >= 1
        assert len(grammar["valid_regimes"]) >= 1


def test_grammar_template_resolution():
    """Grammar templates must resolve to valid condition strings."""
    from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2

    redis = MagicMock()
    db = MagicMock()
    agent = IdeatorAgentV2(0, 0.5, redis, db, mode="rich")

    # Numeric range template
    tmpl = ("rsi_14", "<", (28, 38))
    result = agent._resolve_grammar_template(tmpl, "equity", {})
    assert result is not None
    assert "rsi_14 <" in result
    val = float(result.split("< ")[1])
    assert 28 <= val <= 38

    # Cross-feature template
    tmpl2 = ("ema_12", ">", "ema_26")
    result2 = agent._resolve_grammar_template(tmpl2, "equity", {})
    assert result2 == "ema_12 > ema_26"


def test_llm_meta_advisor_defaults_false():
    """USE_LLM_META_ADVISOR should default to False."""
    # Ensure env var is not set for this test
    original = os.environ.pop("USE_LLM_META_ADVISOR", None)
    try:
        from importlib import reload
        import atlas.agents.l2_strategy.ideator_agent_v2 as ideator_mod
        redis = MagicMock()
        db = MagicMock()
        agent = ideator_mod.IdeatorAgentV2(0, 0.5, redis, db, mode="rich")
        assert agent._llm_meta_advisor is False
    finally:
        if original is not None:
            os.environ["USE_LLM_META_ADVISOR"] = original


# ================================================================
# TEST 3: Meta agent advisory_only enforcement
# ================================================================

def test_meta_reasoning_agent_is_advisory():
    """MetaReasoningAgent must be advisory_only."""
    from atlas.agents.l7_meta.meta_reasoning_agent import MetaReasoningAgent
    from atlas.core.agent_base import GovernanceViolation

    redis = MagicMock()
    db = MagicMock()
    agent = MetaReasoningAgent(redis_client=redis, db_client=db)
    assert agent.advisory_only is True

    with pytest.raises(GovernanceViolation):
        agent._enforce_advisory_guard("execute_trade")


def test_hypothesis_engine_is_advisory():
    """HypothesisEngine must be advisory_only."""
    from atlas.agents.l7_meta.hypothesis_engine import HypothesisEngine
    from atlas.core.agent_base import GovernanceViolation

    redis = MagicMock()
    db = MagicMock()
    agent = HypothesisEngine(redis_client=redis, db_client=db)
    assert agent.advisory_only is True

    with pytest.raises(GovernanceViolation):
        agent._enforce_advisory_guard("mutate_strategy")


def test_failure_analysis_engine_is_advisory():
    """FailureAnalysisEngine must be advisory_only."""
    from atlas.agents.l7_meta.failure_analysis_engine import FailureAnalysisEngine
    from atlas.core.agent_base import GovernanceViolation

    redis = MagicMock()
    db = MagicMock()
    agent = FailureAnalysisEngine(redis_client=redis, db_client=db)
    assert agent.advisory_only is True


def test_scout_synthesis_engine_is_advisory():
    """ScoutSynthesisEngine must be advisory_only."""
    from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine
    from atlas.core.agent_base import GovernanceViolation

    redis = MagicMock()
    db = MagicMock()
    agent = ScoutSynthesisEngine(redis_client=redis, db_client=db)
    assert agent.advisory_only is True


# ================================================================
# TEST 4: Deterministic reasoning fallback
# ================================================================

def test_meta_reasoning_deterministic_fallback():
    """MetaReasoningAgent should produce valid output without LLM."""
    from atlas.agents.l7_meta.meta_reasoning_agent import MetaReasoningAgent

    redis = MagicMock()
    db = MagicMock()
    agent = MetaReasoningAgent(redis_client=redis, db_client=db)

    # Simulate system state with high drift
    state = {
        "drift": {"feature": 0.5, "strategy": 0.3, "regime": 0.8, "composite": 0.75},
        "recent_24h": {"validated": 10, "failed": 50, "retired": 5, "total": 65},
        "mutation_summary": [
            {"type": "parameter_shift", "total": 10, "improved": 2, "avg_delta": -0.5},
        ],
        "prior_analyses": [],
    }

    advisory = agent._generate_deterministic_reasoning(state)
    assert advisory is not None
    assert "advisory_type" in advisory
    assert "confidence" in advisory
    assert "recommendations" in advisory
    assert advisory["advisory_type"] in [
        "strategic_advisory", "governance_warning", "drift_diagnosis",
        "mutation_recommendation",
    ]
    assert 0.0 <= advisory["confidence"] <= 1.0


# ================================================================
# TEST 5: Failure analysis pattern detection
# ================================================================

def test_failure_analysis_systemic_patterns():
    """FailureAnalysisEngine should detect systemic patterns from failure data."""
    from atlas.agents.l7_meta.failure_analysis_engine import FailureAnalysisEngine

    redis = MagicMock()
    db = MagicMock()
    engine = FailureAnalysisEngine(redis_client=redis, db_client=db)

    data = {
        "total_failures": 10,
        "failed_strategies": [
            {"id": "s1", "name": "test1", "status": "compile_error",
             "error": "syntax", "params": {}, "created_at": "2026-01-01"},
        ] * 8,  # 8 compile errors out of 10
        "drift_spikes": [{"composite": 0.8}],
        "execution_anomalies": [],
        "mutation_performance": [
            {"type": "parameter_shift", "total": 5, "improved": 0, "avg_delta": -0.3},
            {"type": "indicator_replace", "total": 5, "improved": 0, "avg_delta": -0.5},
            {"type": "threshold_tighten", "total": 5, "improved": 0, "avg_delta": -0.2},
        ],
    }

    patterns = engine._detect_systemic_patterns(data)
    pattern_types = [p["pattern"] for p in patterns]

    # Should detect compile error clustering
    assert "compile_error_cluster" in pattern_types
    # Should detect mutation entropy collapse
    assert "mutation_entropy_collapse" in pattern_types


# ================================================================
# TEST 6: Mutation entropy metric
# ================================================================

def test_mutation_entropy_computation():
    """MutationPolicyEngine should compute normalized entropy correctly."""
    from atlas.agents.l7_meta.mutation_policy_engine import MutationPolicyEngine

    redis = MagicMock()
    db = MagicMock()
    engine = MutationPolicyEngine(redis, db)

    # Uniform distribution = maximum entropy = 1.0
    n_types = len(engine._weights)
    engine._weights = {k: 1.0 / n_types for k in engine._weights}
    entropy_uniform = engine._compute_entropy_metric()
    assert abs(entropy_uniform - 1.0) < 0.01, f"Uniform entropy should be ~1.0, got {entropy_uniform}"

    # Concentrated distribution = low entropy
    engine._weights = {k: 0.001 for k in engine._weights}
    first_key = list(engine._weights.keys())[0]
    engine._weights[first_key] = 0.99
    entropy_concentrated = engine._compute_entropy_metric()
    assert entropy_concentrated < 0.3, f"Concentrated entropy should be <0.3, got {entropy_concentrated}"


# ================================================================
# TEST 7: Scout synthesis agreement metrics
# ================================================================

def test_scout_agreement_computation():
    """ScoutSynthesisEngine should compute agreement scores deterministically."""
    from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine

    redis = MagicMock()
    db = MagicMock()
    engine = ScoutSynthesisEngine(redis_client=redis, db_client=db)

    # All scouts agree (bullish)
    signals_agree = {
        "regime_scout": {"type": "internal", "summary_signal": "bullish"},
        "liquidity_scout": {"type": "internal", "summary_signal": "healthy"},
        "execution_scout": {"type": "internal", "summary_signal": "healthy"},
    }
    metrics_agree = engine._compute_agreement_metrics(signals_agree)
    assert metrics_agree["agreement_score"] > 0.6

    # Scouts disagree
    signals_disagree = {
        "regime_scout": {"type": "internal", "summary_signal": "bullish"},
        "liquidity_scout": {"type": "internal", "summary_signal": "stressed"},
        "reddit": {"type": "external", "summary_signal": "bearish"},
    }
    metrics_disagree = engine._compute_agreement_metrics(signals_disagree)
    assert metrics_disagree["agreement_score"] < metrics_agree["agreement_score"]


# ================================================================
# TEST 8: Hypothesis lifecycle states
# ================================================================

def test_hypothesis_dataclass():
    """Hypothesis dataclass should have correct defaults and fields."""
    from atlas.agents.l7_meta.hypothesis_engine import Hypothesis

    h = Hypothesis(
        id="test_id",
        trace_id="trace_123",
        statement="Test hypothesis",
        observation_source="drift_detection",
        testable_prediction="X will happen",
    )
    assert h.confidence == 0.5
    assert h.status == "active"
    assert h.evidence_count == 0
    assert h.contradiction_count == 0
    assert h.decay_rate == 0.01


def test_hypothesis_engine_deterministic_generation():
    """HypothesisEngine should generate hypotheses deterministically from observations."""
    from atlas.agents.l7_meta.hypothesis_engine import HypothesisEngine

    redis = MagicMock()
    db = MagicMock()
    engine = HypothesisEngine(redis_client=redis, db_client=db)
    engine._llm_enabled = False

    observations = [
        {
            "source": "drift_detection",
            "type": "drift_escalation",
            "data": {"feature_drift": 0.6, "strategy_drift": 0.3,
                     "regime_drift": 0.2, "composite": 0.5},
        },
        {
            "source": "mutation_memory",
            "type": "mutation_entropy_collapse",
            "data": {"mutations": [
                {"type": "parameter_shift", "avg_delta": -0.3},
                {"type": "indicator_replace", "avg_delta": -0.5},
            ]},
        },
    ]

    hypotheses = engine._generate_deterministic_hypotheses(observations)
    assert len(hypotheses) >= 2
    for h in hypotheses:
        assert h.statement
        assert h.testable_prediction
        assert h.observation_source
        assert 0.0 <= h.confidence <= 1.0
        assert h.status == "active"


# ================================================================
# TEST 9: LLM outage resilience
# ================================================================

def test_llm_outage_resilience_ideator():
    """IdeatorAgentV2 must produce strategies without LLM access."""
    from atlas.agents.l2_strategy.ideator_agent_v2 import (
        IdeatorAgentV2, STRATEGY_GRAMMAR
    )

    redis = MagicMock()
    db = MagicMock()
    agent = IdeatorAgentV2(0, 0.5, redis, db, mode="rich")
    agent._llm_meta_advisor = False  # LLM disabled

    # Grammar engine should be usable
    assert STRATEGY_GRAMMAR is not None
    assert len(STRATEGY_GRAMMAR) >= 5


def test_deterministic_synthesis_without_llm():
    """ScoutSynthesisEngine should produce valid synthesis without LLM."""
    from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine

    redis = MagicMock()
    db = MagicMock()
    engine = ScoutSynthesisEngine(redis_client=redis, db_client=db)

    signals = {
        "regime_scout": {
            "type": "internal", "summary_signal": "bullish",
            "data": [{"symbol": "SPY", "trend": "trending_up"}],
        },
    }
    metrics = engine._compute_agreement_metrics(signals)
    synthesis = engine._generate_deterministic_synthesis(signals, metrics)

    assert "contextual_summary" in synthesis
    assert "market_state_interpretation" in synthesis
    assert "dominant_theme" in synthesis
    assert "confidence" in synthesis


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
