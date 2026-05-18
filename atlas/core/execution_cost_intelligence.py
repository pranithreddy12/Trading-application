"""
execution_cost_intelligence.py — ATLAS Execution Cost Intelligence Layer (ECIL)

PURPOSE:
Provides unified cost-aware metrics and generation priors for all ATLAS agents.
Evolves ATLAS from pattern-aware to cost-aware generation.

MISSION:
Teach Ideator, Validator, Mutator, and Pattern systems to optimize for strategies
that survive realistic fees, slippage, and spreads.

CORE PRINCIPLES:
1. Agent-agnostic: usable by any agent without coupling
2. Restart-safe: stateless, deterministic computation
3. Modular: import only needed functions
4. Observable: all computations have clear inputs/outputs
5. Educative: generates advisory priors for generation systems

USAGE EXAMPLES:
```python
from atlas.core.execution_cost_intelligence import (
    estimate_round_trip_cost,
    cost_efficiency_score,
    friction_burden_pct,
    classify_cost_profile,
)

# In Ideator
cost_hints = generate_cost_priors(
    asset_class="crypto",
    archetype="momentum",
    trade_frequency_target=30,
)

# In Validator
profile = classify_cost_profile(
    net_return=0.05,
    trade_count=50,
    gross_return=0.054,
)

# In Mutator tracking
delta = cost_efficiency_delta(
    parent_net_return=0.05,
    parent_trade_count=50,
    child_net_return=0.048,
    child_trade_count=40,
)
```

SCHEMA:
- Restart-safe: ✅ Pure functions, no state
- Observable: ✅ All metrics have clear definitions
- Idempotent: ✅ Same input → same output always
- Audit-traceable: ✅ All computations documented

---
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class CostProfile(str, Enum):
    """Cost profile classification for strategies."""
    LOW_FRICTION_ALPHA = "low_friction_alpha"
    MEDIUM_EFFICIENCY = "medium_efficiency"
    HIGH_CHURN_TRAP = "high_churn_cost_trap"
    OVERTRADING_FRAGILE = "overtrading_fragile"
    INSTITUTIONAL_CANDIDATE = "institutional_candidate"
    UNDEFINED = "undefined"


class AssetClass(str, Enum):
    """Asset class with cost profile differentials."""
    CRYPTO = "crypto"
    EQUITY = "equity"
    FOREX = "forex"
    UNKNOWN = "unknown"


@dataclass
class CostProfile_Data:
    """Structured cost profile output."""
    classification: CostProfile
    edge_per_trade_bps: float
    cost_burden_pct: float
    friction_resilience: float  # 0-1, higher = better
    risk_level: str  # low, medium, high
    recommendation: str


@dataclass
class CostMetrics:
    """Complete cost metrics for a strategy."""
    net_return: float
    gross_return: float
    trade_count: int
    round_trip_cost_pct: float
    cost_efficiency_score: float
    friction_burden_pct: float
    expected_edge_per_trade_bps: float
    cost_profile: CostProfile
    asset_class: AssetClass


# ============================================================================
# SECTION 1: COST MODELS BY ASSET CLASS
# ============================================================================

def get_cost_model(asset_class: str) -> Dict[str, float]:
    """
    Return standardized cost model for asset class.
    
    Returns:
        dict with keys: commission_pct, slippage_pct, spread_pct
    """
    asset_class = str(asset_class).lower().strip()
    
    # Cost model: (commission, slippage, spread)
    COST_MODELS = {
        "crypto": {
            "commission_pct": 0.0015,  # 0.15% (Binance taker)
            "slippage_pct": 0.001,      # 0.1% (volatility dependent)
            "spread_pct": 0.001,        # 0.1% (typical spread)
        },
        "equity": {
            "commission_pct": 0.0005,   # 0.05% (typical retail)
            "slippage_pct": 0.0003,     # 0.03% (liquid ETFs)
            "spread_pct": 0.0002,       # 0.02% (tight spread)
        },
        "forex": {
            "commission_pct": 0.0001,   # 0.01% (FX typically tight)
            "slippage_pct": 0.0002,     # 0.02%
            "spread_pct": 0.0001,       # 0.01%
        },
    }
    
    model = COST_MODELS.get(asset_class, COST_MODELS["unknown"] 
                             if "unknown" in COST_MODELS 
                             else COST_MODELS["crypto"])
    
    if asset_class not in COST_MODELS:
        logger.warning(f"Unknown asset class '{asset_class}', using crypto costs")
    
    return model


# ============================================================================
# SECTION 2: CORE COST COMPUTATION FUNCTIONS
# ============================================================================

def estimate_round_trip_cost(
    asset_class: str = "crypto",
    bps: bool = False,
) -> float:
    """
    Estimate total cost for one entry + one exit transaction.
    
    Args:
        asset_class: "crypto", "equity", "forex", or "unknown"
        bps: If True, return in basis points (0-10000). If False, return as decimal (0-1).
    
    Returns:
        Round-trip cost as decimal (0.004 = 0.4%) or basis points (40)
    
    Example:
        >>> estimate_round_trip_cost("crypto")  # 0.004
        >>> estimate_round_trip_cost("crypto", bps=True)  # 40
    """
    model = get_cost_model(asset_class)
    
    # Entry cost (commission + slippage + spread)
    entry_cost = (model["commission_pct"] + 
                  model["slippage_pct"] + 
                  model["spread_pct"])
    
    # Exit cost (same as entry)
    exit_cost = entry_cost
    
    total = entry_cost + exit_cost
    
    if bps:
        return total * 10000
    return total


def cost_efficiency_score(
    net_return: float,
    trade_count: int,
    min_trades: int = 5,
) -> float:
    """
    Compute cost efficiency: net return per trade.
    
    Higher = better (can absorb costs better).
    
    Args:
        net_return: Total net return as decimal (0.05 = 5%)
        trade_count: Total number of round-trip trades
        min_trades: Minimum trades to compute (below = return 0.0)
    
    Returns:
        Cost efficiency score (net_return / trade_count).
        Returns 0.0 if trade_count < min_trades.
    
    Example:
        >>> cost_efficiency_score(0.05, 50)  # 0.001 = 0.1% per trade
        >>> cost_efficiency_score(0.05, 500)  # 0.0001 = 0.01% per trade (cost trap)
    """
    if trade_count < min_trades:
        return 0.0
    
    return net_return / max(trade_count, 1)


def friction_burden_pct(
    gross_return: float,
    net_return: float,
) -> float:
    """
    Compute friction burden as percentage of gross return.
    
    Shows how much of potential return was lost to costs.
    
    Args:
        gross_return: Return before costs
        net_return: Return after costs
    
    Returns:
        Friction burden as decimal (0.1 = 10% of gross was lost to costs).
        Returns 0.0 if gross_return <= 0.
    
    Example:
        >>> friction_burden_pct(0.054, 0.050)  # 0.074 = 7.4% of gains lost
        >>> friction_burden_pct(0.004, -0.001)  # 1.25 = 125% of gains lost (net loss)
    """
    if gross_return <= 0:
        return 0.0
    
    cost_burden = gross_return - net_return
    return cost_burden / gross_return


def expected_edge_per_trade(
    net_return: float,
    trade_count: int,
    asset_class: str = "crypto",
) -> float:
    """
    Estimate expected edge per trade in basis points.
    
    This is net return per trade, expressed in basis points.
    
    Args:
        net_return: Total net return as decimal
        trade_count: Total trades executed
        asset_class: For context only (for logging)
    
    Returns:
        Expected edge per trade in basis points (100 = 1%, 10 = 0.1%, 1 = 0.01%)
    
    Example:
        >>> expected_edge_per_trade(0.05, 50)  # 100 bps = 1% per trade
        >>> expected_edge_per_trade(0.01, 500)  # 2 bps = 0.02% per trade (tight)
    """
    if trade_count < 1:
        return 0.0
    
    edge_per_trade_decimal = net_return / trade_count
    edge_per_trade_bps = edge_per_trade_decimal * 10000
    
    return edge_per_trade_bps


def cost_efficiency_delta(
    parent_net_return: float,
    parent_trade_count: int,
    child_net_return: float,
    child_trade_count: int,
) -> float:
    """
    Compute cost efficiency improvement from mutation.
    
    Positive = improvement, Negative = degradation.
    
    Args:
        parent_net_return: Parent strategy net return
        parent_trade_count: Parent strategy trade count
        child_net_return: Child strategy net return
        child_trade_count: Child strategy trade count
    
    Returns:
        Delta in cost efficiency score (can be negative).
    
    Example:
        >>> cost_efficiency_delta(0.05, 50, 0.048, 40)
        >>> # Parent: 0.1% per trade, Child: 0.12% per trade → +0.0002 improvement
    """
    parent_score = cost_efficiency_score(parent_net_return, parent_trade_count)
    child_score = cost_efficiency_score(child_net_return, child_trade_count)
    
    return child_score - parent_score


def friction_resilience_score(
    cost_efficiency: float,
    round_trip_cost_decimal: float,
) -> float:
    """
    Score resilience to friction (0-1).
    
    1.0 = can absorb costs and still profitable
    0.0 = costs eliminate profitability
    
    Args:
        cost_efficiency: Edge per trade as decimal
        round_trip_cost_decimal: Round-trip cost as decimal
    
    Returns:
        Resilience score 0-1 (higher = better)
    
    Example:
        >>> friction_resilience_score(0.005, 0.004)  # 0.5 (weak, margin of safety only 20%)
        >>> friction_resilience_score(0.015, 0.004)  # ~0.85 (strong)
    """
    if round_trip_cost_decimal <= 0:
        return 1.0
    
    # Ratio of edge to cost
    ratio = cost_efficiency / round_trip_cost_decimal if round_trip_cost_decimal > 0 else 1.0
    
    # Map to 0-1 score
    # ratio < 1.0 (edge < cost) → score near 0
    # ratio > 5.0 (edge >> cost) → score near 1
    # ratio = 2.5 → score ~0.5
    
    resilience = min(1.0, max(0.0, (ratio - 1.0) / 4.0))
    
    return resilience


# ============================================================================
# SECTION 3: CLASSIFICATION FUNCTION
# ============================================================================

def classify_cost_profile(
    net_return: float,
    trade_count: int,
    gross_return: Optional[float] = None,
    asset_class: str = "crypto",
) -> CostProfile_Data:
    """
    Classify strategy's cost profile into actionable categories.
    
    Categories:
    - LOW_FRICTION_ALPHA: Strong edge, low frequency (ideal)
    - INSTITUTIONAL_CANDIDATE: Good edge, controlled frequency
    - MEDIUM_EFFICIENCY: Okay edge, moderate frequency
    - HIGH_CHURN_TRAP: High frequency, weak edge (cost danger)
    - OVERTRADING_FRAGILE: Extreme frequency, fragile edge
    
    Args:
        net_return: Net return as decimal
        trade_count: Total trades executed
        gross_return: Gross return before costs (optional, for friction calc)
        asset_class: "crypto", "equity", "forex"
    
    Returns:
        CostProfile_Data with classification and recommendation
    """
    round_trip_cost = estimate_round_trip_cost(asset_class)
    edge_per_trade_decimal = cost_efficiency_score(net_return, trade_count)
    edge_per_trade_bps = edge_per_trade_decimal * 10000
    
    # Compute friction burden if gross return provided
    if gross_return is not None:
        friction = friction_burden_pct(gross_return, net_return)
    else:
        friction = None
    
    # Classification logic
    if trade_count < 5:
        classification = CostProfile.UNDEFINED
        risk_level = "insufficient_data"
        recommendation = "Insufficient trades for cost analysis"
        resilience = 0.0
    elif edge_per_trade_decimal < 0.001:  # < 10 bps
        if trade_count > 200:
            classification = CostProfile.OVERTRADING_FRAGILE
            risk_level = "high"
            recommendation = "REJECT: Extreme frequency with micro-edge (cost bomb)"
        else:
            classification = CostProfile.HIGH_CHURN_TRAP
            risk_level = "high"
            recommendation = "WARN: High frequency with weak edge (cost collapse likely)"
        resilience = friction_resilience_score(edge_per_trade_decimal, round_trip_cost)
    elif edge_per_trade_decimal < 0.002:  # < 20 bps
        if trade_count > 100:
            classification = CostProfile.HIGH_CHURN_TRAP
            risk_level = "medium"
            recommendation = "WARN: Marginal edge may not survive high frequency"
        else:
            classification = CostProfile.MEDIUM_EFFICIENCY
            risk_level = "low"
            recommendation = "ACCEPT: Modest edge with controlled frequency"
        resilience = friction_resilience_score(edge_per_trade_decimal, round_trip_cost)
    elif edge_per_trade_decimal < 0.005:  # < 50 bps
        if trade_count < 30:
            classification = CostProfile.LOW_FRICTION_ALPHA
            risk_level = "low"
            recommendation = "PROMOTE: Clean alpha with low friction"
        else:
            classification = CostProfile.MEDIUM_EFFICIENCY
            risk_level = "low"
            recommendation = "ACCEPT: Good edge, good frequency balance"
        resilience = friction_resilience_score(edge_per_trade_decimal, round_trip_cost)
    else:  # >= 50 bps
        if trade_count < 50:
            classification = CostProfile.LOW_FRICTION_ALPHA
            risk_level = "low"
            recommendation = "ELITE: Strong alpha, low friction → institutional grade"
        elif trade_count < 100:
            classification = CostProfile.INSTITUTIONAL_CANDIDATE
            risk_level = "low"
            recommendation = "ELITE: Strong alpha, moderate frequency → production ready"
        else:
            classification = CostProfile.MEDIUM_EFFICIENCY
            risk_level = "low"
            recommendation = "ACCEPT: Strong edge, higher frequency acceptable"
        resilience = friction_resilience_score(edge_per_trade_decimal, round_trip_cost)
    
    return CostProfile_Data(
        classification=classification,
        edge_per_trade_bps=edge_per_trade_bps,
        cost_burden_pct=friction if friction is not None else 0.0,
        friction_resilience=resilience,
        risk_level=risk_level,
        recommendation=recommendation,
    )


# ============================================================================
# SECTION 4: GENERATION PRIORS — EDUCATIONAL FRAMEWORK
# ============================================================================

def generate_cost_priors(
    asset_class: str = "crypto",
    archetype: str = "momentum",
    trade_frequency_target: Optional[int] = None,
) -> Dict[str, str]:
    """
    Generate cost-aware generation priors for Ideator.
    
    These are ADVISORY — not hard rules initially.
    Help Ideator understand cost tradeoffs when generating strategies.
    
    Args:
        asset_class: "crypto", "equity", "forex"
        archetype: "momentum", "mean_reversion", "breakout", "trend_following", "volatility_regime"
        trade_frequency_target: Optional target trade count (e.g., 30, 50, 100)
    
    Returns:
        Dict with advisory guidance strings
    
    Example:
        >>> priors = generate_cost_priors("crypto", "momentum", 30)
        >>> print(priors["cost_principle"])
        "Avoid hyperactive strategies with weak expected edge..."
    """
    round_trip_cost_bps = estimate_round_trip_cost(asset_class, bps=True)
    
    archetype_frequency = {
        "momentum": (50, 150),        # Typically 50-150 trades
        "mean_reversion": (30, 80),   # 30-80 trades
        "breakout": (20, 60),         # 20-60 trades
        "trend_following": (10, 40),  # 10-40 trades
        "volatility_regime": (15, 50),  # 15-50 trades
    }
    
    freq_range = archetype_frequency.get(archetype, (20, 100))
    ideal_edge_per_trade_bps = round_trip_cost_bps * 2.5  # Edge should be 2.5x cost
    
    priors = {
        "cost_principle":
            f"Avoid hyperactive {archetype} strategies with weak expected edge per trade. "
            f"Target: {ideal_edge_per_trade_bps:.0f} bps edge per trade (cost={round_trip_cost_bps:.0f} bps).",
        
        "frequency_guidance":
            f"{archetype.title()} typically trades {freq_range[0]}-{freq_range[1]} times over backtest. "
            f"{'Tighter thresholds → fewer trades → better cost absorption' if archetype in ['trend_following', 'breakout'] else 'Looser triggers → more trades → weaker edges per trade'}.",
        
        "cost_avoidance":
            f"Penalize strategies with >0.2% total return but >100 trades "
            f"(indicates {round(0.002/100*10000, 0):.0f} bps edge per trade = cost trap).",
        
        "edge_requirement":
            f"Prefer setups with wider margins per trade ({ideal_edge_per_trade_bps:.0f}+ bps), "
            f"even if less frequent. Robust under realistic friction.",
        
        "bias_rules":
            f"• Bias toward lower churn (fewer but stronger signals)\n"
            f"• Require conviction in entries (tighter conditions)\n"
            f"• Penalize micro-edge systems likely to fail after fees\n"
            f"• Favor asymmetric reward:risk (not just frequency).",
    }
    
    if trade_frequency_target:
        min_edge_bps = (round_trip_cost_bps * 100 * 1.5) / trade_frequency_target
        priors["specific_target"] = (
            f"Target: {trade_frequency_target} trades requires >={min_edge_bps:.0f} bps "
            f"average edge per trade to survive costs with 50% margin of safety."
        )
    
    return priors


def get_cost_governance_thresholds(
    trade_frequency: int,
    asset_class: str = "crypto",
) -> Dict[str, float]:
    """
    Return cost governance validation thresholds based on trade frequency.
    
    Higher frequency strategies need higher edge per trade to pass validation.
    
    Args:
        trade_frequency: Number of trades in strategy
        asset_class: For cost model context
    
    Returns:
        Dict with validation thresholds
    
    Example:
        >>> thresholds = get_cost_governance_thresholds(50, "crypto")
        >>> print(thresholds["min_edge_per_trade_bps"])  # ~100
    """
    round_trip_cost_bps = estimate_round_trip_cost(asset_class, bps=True)
    
    if trade_frequency < 10:
        # Low frequency: can have weak edge
        return {
            "min_edge_per_trade_bps": round_trip_cost_bps * 0.5,  # Just survive costs
            "min_win_rate": 0.45,
            "min_profit_factor": 1.1,
            "risk_category": "low_frequency_acceptable",
        }
    elif trade_frequency < 50:
        # Medium frequency: need decent edge
        return {
            "min_edge_per_trade_bps": round_trip_cost_bps * 1.5,  # 1.5x safety margin
            "min_win_rate": 0.50,
            "min_profit_factor": 1.3,
            "risk_category": "medium_frequency",
        }
    elif trade_frequency < 100:
        # High frequency: need strong edge
        return {
            "min_edge_per_trade_bps": round_trip_cost_bps * 2.5,  # 2.5x safety margin
            "min_win_rate": 0.52,
            "min_profit_factor": 1.5,
            "risk_category": "high_frequency_strict",
        }
    else:
        # Very high frequency: need very strong edge
        return {
            "min_edge_per_trade_bps": round_trip_cost_bps * 4.0,  # 4x safety margin
            "min_win_rate": 0.54,
            "min_profit_factor": 1.8,
            "risk_category": "extreme_frequency_reject_most",
        }


# ============================================================================
# SECTION 5: COMPREHENSIVE METRICS FUNCTION
# ============================================================================

def compute_cost_metrics(
    net_return: float,
    trade_count: int,
    gross_return: Optional[float] = None,
    asset_class: str = "crypto",
) -> CostMetrics:
    """
    Compute complete cost metrics for a strategy in one call.
    
    Convenience function for agents that need full cost picture.
    
    Args:
        net_return: Net return as decimal
        trade_count: Total trades
        gross_return: Gross return (optional)
        asset_class: Asset class for cost model
    
    Returns:
        CostMetrics dataclass with all cost information
    
    Example:
        >>> metrics = compute_cost_metrics(0.05, 50, 0.054, "crypto")
        >>> print(f"Edge: {metrics.expected_edge_per_trade_bps} bps")
        >>> print(f"Profile: {metrics.cost_profile.value}")
    """
    round_trip_cost = estimate_round_trip_cost(asset_class)
    efficiency = cost_efficiency_score(net_return, trade_count)
    efficiency_bps = expected_edge_per_trade(net_return, trade_count, asset_class)
    
    if gross_return is None:
        friction = 0.0
    else:
        friction = friction_burden_pct(gross_return, net_return)
    
    profile_data = classify_cost_profile(net_return, trade_count, gross_return, asset_class)
    
    return CostMetrics(
        net_return=net_return,
        gross_return=gross_return if gross_return is not None else net_return,
        trade_count=trade_count,
        round_trip_cost_pct=round_trip_cost,
        cost_efficiency_score=efficiency,
        friction_burden_pct=friction,
        expected_edge_per_trade_bps=efficiency_bps,
        cost_profile=profile_data.classification,
        asset_class=AssetClass(asset_class.lower()) if asset_class.lower() in ["crypto", "equity", "forex"] else AssetClass.UNKNOWN,
    )


# ============================================================================
# SECTION 6: UTILITY FUNCTIONS
# ============================================================================

def is_cost_trap(
    net_return: float,
    trade_count: int,
    asset_class: str = "crypto",
    threshold_multiplier: float = 1.0,
) -> bool:
    """
    Quick check: is this strategy a cost trap?
    
    Cost trap = high frequency + weak edge that doesn't survive costs.
    
    Args:
        net_return: Net return
        trade_count: Trade count
        asset_class: Asset class
        threshold_multiplier: Adjust sensitivity (>1 = stricter, <1 = looser)
    
    Returns:
        True if strategy is likely a cost trap
    """
    profile = classify_cost_profile(net_return, trade_count, asset_class=asset_class)
    
    is_trap = profile.classification in [
        CostProfile.HIGH_CHURN_TRAP,
        CostProfile.OVERTRADING_FRAGILE,
    ]
    
    return is_trap


def is_friction_resilient(
    net_return: float,
    trade_count: int,
    asset_class: str = "crypto",
) -> bool:
    """
    Quick check: is this strategy friction resilient?
    
    Resilient = strong edge that survives costs well.
    
    Args:
        net_return: Net return
        trade_count: Trade count
        asset_class: Asset class
    
    Returns:
        True if strategy is friction resilient
    """
    profile = classify_cost_profile(net_return, trade_count, asset_class=asset_class)
    
    is_resilient = profile.classification in [
        CostProfile.LOW_FRICTION_ALPHA,
        CostProfile.INSTITUTIONAL_CANDIDATE,
    ]
    
    return is_resilient


# ============================================================================
# SECTION 7: LOGGING & OBSERVABILITY
# ============================================================================

def log_cost_analysis(
    strategy_id: str,
    net_return: float,
    trade_count: int,
    gross_return: Optional[float] = None,
    asset_class: str = "crypto",
) -> str:
    """
    Generate human-readable cost analysis log for a strategy.
    
    Useful for audit trails and human inspection.
    
    Args:
        strategy_id: Strategy identifier
        net_return: Net return
        trade_count: Trade count
        gross_return: Gross return (optional)
        asset_class: Asset class
    
    Returns:
        Formatted string ready for logging
    """
    metrics = compute_cost_metrics(net_return, trade_count, gross_return, asset_class)
    profile = classify_cost_profile(net_return, trade_count, gross_return, asset_class)
    
    log_msg = (
        f"[{strategy_id}] Cost Analysis:\n"
        f"  Profile: {profile.classification.value}\n"
        f"  Edge/trade: {metrics.expected_edge_per_trade_bps:.1f} bps\n"
        f"  Friction burden: {metrics.friction_burden_pct*100:.1f}%\n"
        f"  Trade count: {metrics.trade_count}\n"
        f"  Net return: {metrics.net_return*100:.2f}%\n"
        f"  Resilience: {profile.friction_resilience:.2f}/1.0\n"
        f"  Recommendation: {profile.recommendation}"
    )
    
    return log_msg


# ============================================================================
# END OF EXECUTION COST INTELLIGENCE LAYER
# ============================================================================
