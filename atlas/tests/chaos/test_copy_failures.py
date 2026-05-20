"""
test_copy_failures.py — Phase 21I

Chaos testing for copy trading resilience.
Tests:
- Replay integrity under copy drift
- Follower restart recovery
- Duplicate execution prevention
- Degraded-mode survivability
- Capital-aware scaling validation
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ================================================================
# TEST 1: Duplicate Execution Prevention (Idempotency)
# ================================================================

@pytest.mark.asyncio
async def test_duplicate_execution_prevention():
    """Ensure CopyTraderAgent prevents duplicate fills from the same leader order."""
    from atlas.agents.l5_execution.copy_trader import CopyTraderAgent

    redis_mock = AsyncMock()
    redis_mock.sismember.return_value = False
    
    db_mock = AsyncMock()
    # Mock successful insert followed by no rows affected for duplicate
    db_mock.engine.begin.return_value.__aenter__.return_value.execute.side_effect = [
        MagicMock(rowcount=1),  # First time inserts
        MagicMock(rowcount=0),  # Second time duplicate
    ]

    agent = CopyTraderAgent(redis_client=redis_mock, db_client=db_mock)
    agent.messaging = AsyncMock()

    msg = {
        "order_id": "leader_order_123",
        "account_ref": "leader_acc",
        "symbol": "BTCUSD",
        "side": "buy",
        "qty": 1.0,
        "price": 50000.0,
    }

    followers_map = {
        "leader_acc": [
            {"follower_id": "f1", "account_ref": "f1_acc", "allocation_ratio": 1.0}
        ]
    }

    # First handle
    await agent._handle_leader_fill(msg, followers_map)
    assert redis_mock.sadd.call_count == 1
    
    # Simulate duplicate message via pubsub
    redis_mock.sismember.return_value = True
    await agent._handle_leader_fill(msg, followers_map)
    
    # sadd should not be called again if sismember was True
    assert redis_mock.sadd.call_count == 1


# ================================================================
# TEST 2: Capital-Aware Scaling (Phase 21C)
# ================================================================

def test_capital_aware_allocation():
    """CopyCapitalAllocator must respect exposure caps and volatility."""
    from atlas.agents.l6_portfolio.copy_capital_allocator import (
        CopyCapitalAllocator, FollowerProfile
    )

    redis = MagicMock()
    db = MagicMock()
    allocator = CopyCapitalAllocator(redis, db)
    
    allocator._profiles_cache["f1"] = FollowerProfile(
        follower_id="f1",
        account_ref="f1_acc",
        total_capital=10000.0,
        max_single_position_pct=0.10, # Max $1000 per position
        target_volatility=0.15
    )

    # Leader takes a $5000 position
    decision = allocator.compute_allocation(
        follower_id="f1",
        symbol="BTCUSD",
        leader_qty=0.1,
        leader_price=50000.0, # Value = $5000
        leader_total_exposure=100000.0,
        current_follower_exposure=0.0,
        symbol_volatility=0.005 # Low volatility to avoid scaling down
    )

    # Without caps, proportional allocation is (10k / 100k) = 0.1
    # 0.1 * $5000 = $500 position.
    # $500 < $1000 cap, so scaling should be 0.1
    assert decision.scaling_factor == 0.1
    assert decision.allocated_qty == 0.01

    # Now leader takes a $100,000 position (all-in)
    decision2 = allocator.compute_allocation(
        follower_id="f1",
        symbol="ETHUSD",
        leader_qty=50.0,
        leader_price=2000.0, # Value = $100,000
        leader_total_exposure=100000.0,
        current_follower_exposure=0.0,
        symbol_volatility=0.02
    )
    
    # Proportional is 0.1, so follower value = $10,000.
    # But max_single_position_pct is 10% of $10,000 = $1,000.
    # So scaling must be heavily reduced.
    follower_value = decision2.allocated_qty * 2000.0
    assert follower_value <= 1000.0
    assert decision2.scaling_factor < 0.1


# ================================================================
# TEST 3: Degraded Mode Execution (Phase 21F)
# ================================================================

@pytest.mark.asyncio
async def test_degraded_mode_skips_execution():
    """Followers in frozen_follow mode must skip copy execution."""
    from atlas.agents.l5_execution.copy_trader import CopyTraderAgent

    redis_mock = AsyncMock()
    redis_mock.sismember.return_value = False
    
    # Simulate follower in frozen_follow mode
    async def mock_get(key):
        if "mode" in key:
            return b"frozen_follow"
        return None
    redis_mock.get = mock_get
    
    db_mock = AsyncMock()
    agent = CopyTraderAgent(redis_client=redis_mock, db_client=db_mock)
    agent.messaging = AsyncMock()

    msg = {
        "order_id": "leader_order_789",
        "account_ref": "leader_acc",
        "symbol": "BTCUSD",
        "qty": 1.0,
    }

    followers = {
        "leader_acc": [
            {"follower_id": "f2", "account_ref": "f2_acc", "allocation_ratio": 1.0}
        ]
    }

    await agent._handle_leader_fill(msg, followers)
    
    # Should not place order
    assert db_mock.engine.begin.call_count == 0


# ================================================================
# TEST 4: Copy Drift Severity Classification (Phase 21B)
# ================================================================

def test_drift_classification():
    """CopyDriftEngine must correctly classify severity."""
    from atlas.agents.l5_execution.copy_drift_engine import CopyDriftEngine

    assert CopyDriftEngine._classify_severity(0.01) == "synchronized"
    assert CopyDriftEngine._classify_severity(0.10) == "mild_drift"
    assert CopyDriftEngine._classify_severity(0.25) == "elevated_drift"
    assert CopyDriftEngine._classify_severity(1.5) == "critical_drift"


# ================================================================
# TEST 5: Portfolio Overlap Detection (Phase 21G)
# ================================================================

@pytest.mark.asyncio
async def test_overlap_engine_penalty():
    """CopyOverlapEngine must detect duplicated exposure across leaders."""
    from atlas.agents.l6_portfolio.copy_overlap_engine import CopyOverlapEngine

    redis = AsyncMock()
    db = AsyncMock()
    
    engine = CopyOverlapEngine(redis, db)
    
    async def mock_get_positions(lid):
        if lid == "leader_1":
            return {"BTCUSD": 5000.0, "ETHUSD": 2000.0}
        elif lid == "leader_2":
            return {"BTCUSD": 3000.0, "SOLUSD": 1000.0}
        return {}
    
    engine._get_leader_positions = mock_get_positions
    
    # Should detect BTCUSD overlap
    await engine._analyze_overlap("f1", ["leader_1", "leader_2"])
    
    # Verify penalty was set in Redis
    redis.set.assert_called()
    call_args = redis.set.call_args[0]
    assert "copy_overlap:f1:penalty" in call_args[0]
    # Penalty > 0 because of BTCUSD overlap
    assert float(call_args[1]) > 0.0


# ================================================================
# TEST 6: Position Reconciliation Deltas (Phase 21A)
# ================================================================

@pytest.mark.asyncio
async def test_reconciliation_deltas():
    """PositionReconciliationEngine must generate correct repair actions."""
    from atlas.agents.l5_execution.position_reconciliation_engine import PositionReconciliationEngine

    redis = AsyncMock()
    db = AsyncMock()
    
    engine = PositionReconciliationEngine(redis, db)
    
    async def mock_get_positions(aid, role):
        if role == "leader":
            return {
                "BTCUSD": {"qty": 1.0, "avg_entry": 50000, "exposure": 50000, "unrealized_pnl": 100, "realized_pnl": 0},
                "ETHUSD": {"qty": 10.0, "avg_entry": 2000, "exposure": 20000, "unrealized_pnl": 50, "realized_pnl": 0}
            }
        else:
            return {
                "BTCUSD": {"qty": 0.5, "avg_entry": 50000, "exposure": 25000, "unrealized_pnl": 50, "realized_pnl": 0}, # Delta = 0.5
                "SOLUSD": {"qty": 100.0, "avg_entry": 100, "exposure": 10000, "unrealized_pnl": 0, "realized_pnl": 0} # Orphan
            }
    
    engine._get_positions = mock_get_positions
    
    # We mock _persist_position_state to avoid DB inserts
    engine._persist_position_state = AsyncMock()
    
    await engine._reconcile_pair("l1", "f1")
    
    # DB execute_insert should be called for the recon report
    assert db._execute_insert.call_count == 1
    call_args = db._execute_insert.call_args[0]
    params = call_args[1]
    
    assert params["n_mismatches"] >= 3 # BTC delta, ETH missing, SOL orphan
    repair_actions = json.loads(params["repair_actions"])
    
    symbols = [r["symbol"] for r in repair_actions]
    assert "BTCUSD" in symbols
    assert "ETHUSD" in symbols
    assert "SOLUSD" in symbols


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
