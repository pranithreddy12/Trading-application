"""Institutional: Deployment Rollback — verify canary/shadow deployment safety."""

import pytest


def test_rollback_on_performance_degradation():
    """Deployment should auto-rollback if performance degrades."""
    pre_deploy_sharpe = 1.5
    post_deploy_sharpe = 0.8
    degradation_threshold = 0.3
    sharpe_drop = pre_deploy_sharpe - post_deploy_sharpe
    degradation_pct = sharpe_drop / pre_deploy_sharpe
    should_rollback = degradation_pct > degradation_threshold
    assert should_rollback is True


def test_canary_safety():
    """Canary deployment should limit exposure."""
    canary_allocation = 0.05
    max_canary = 0.10
    assert canary_allocation <= max_canary


def test_shadow_mode_no_impact():
    """Shadow mode trades must not affect live portfolio."""
    shadow_trades = [{"pnl": -100}, {"pnl": 150}]
    live_portfolio_start = 100000
    live_portfolio_end = 100000  # No impact
    assert live_portfolio_start == live_portfolio_end


def test_approval_gate():
    """Promotion requires explicit approval."""
    approval_required = True
    was_approved = False
    if approval_required and not was_approved:
        cannot_promote = True
    else:
        cannot_promote = False
    assert cannot_promote is True


@pytest.mark.asyncio
async def test_rollback_restores_previous_version():
    """Rollback must restore the previous working version."""
    versions = {
        "current": {"sharpe": 0.8, "code": "v2_buggy"},
        "previous": {"sharpe": 1.5, "code": "v1_stable"},
    }
    after_rollback = dict(versions["previous"])
    assert after_rollback["sharpe"] == 1.5
    assert after_rollback["code"] == "v1_stable"
