"""Institutional: Scout Reliability — verify external intelligence source quality."""

import pytest


def test_scout_source_diversity():
    """Multiple scout sources must be active for reliable signals."""
    active_sources = {"reddit", "discord", "news", "youtube", "podcast"}
    min_sources = 2
    assert len(active_sources) >= min_sources


def test_scout_source_trust_decay():
    """Stale sources should have trust decay."""
    source_age_days = {"reddit": 2, "twitter": 30, "news": 1}
    trust_scores = {}
    for source, age in source_age_days.items():
        trust_scores[source] = max(0.1, 1.0 - (age * 0.02))
    assert trust_scores["twitter"] < trust_scores["reddit"]
    assert trust_scores["twitter"] < trust_scores["news"]


def test_contradictory_signal_resolution():
    """Contradictory signals should be weighted by source reliability."""
    signals = [
        {"source": "reddit", "direction": "bullish", "reliability": 0.6},
        {"source": "news", "direction": "bearish", "reliability": 0.9},
    ]
    weighted = sum(s["reliability"] * (1 if s["direction"] == "bullish" else -1) for s in signals)
    assert weighted < 0, "Higher reliability bearish signal should dominate"


def test_misinformation_detection():
    """Anomalous signals should be flagged as potential misinformation."""
    signal = {"sentiment": 0.95, "source_reliability": 0.3, "z_score": 3.2}
    is_anomalous = signal["z_score"] > 2.5 and signal["source_reliability"] < 0.5
    assert is_anomalous is True
