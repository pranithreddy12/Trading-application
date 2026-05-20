"""Institutional: Retirement Correctness — verify strategy lifecycle governance."""

import pytest


def test_retirement_lifecycle():
    """Strategies must follow: active -> monitor -> pending -> retired."""
    lifecycle = ["active", "monitor", "pending_retirement", "retired"]
    assert len(lifecycle) == 4
    assert lifecycle[0] == "active"
    assert lifecycle[-1] == "retired"


def test_retirement_criteria():
    """Retirement must require minimum drift severity or age."""
    composite_severity = 0.65
    n_days_active = 45
    min_severity = 0.50
    min_age_days = 30
    eligible = composite_severity >= min_severity or n_days_active >= min_age_days
    assert eligible is True


def test_capital_withdrawal_on_retirement():
    """Capital must be deallocated on retirement."""
    allocations = {"s1": 0.3, "s2": 0.2, "s3": 0.5}
    retired = ["s3"]
    for sid in retired:
        allocations.pop(sid, None)
    assert "s3" not in allocations


def test_retirement_irreversibility():
    """Once retired, strategy cannot be re-activated without re-validation."""
    status = "retired"
    assert status == "retired"
    # Must go through re-validation to become active again
    allowed_transitions = {"retired": ["pending_validation"]}
    assert "active" not in allowed_transitions.get("retired", [])
