"""
scout_contract.py — Standardized payload schemas for Internal Scout Network.

All scouts MUST publish intelligence using these standardized payload schemas.
Consuming agents (Ideator, Mutator, Validator, ExecutionGateway) can rely on
consistent field names and types.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# ============================================================================
# REDIS CHANNELS
# ============================================================================

SCOUT_CHANNELS = {
    "market_regime_updates": "scout:regime",
    "liquidity_updates": "scout:liquidity",
    "correlation_updates": "scout:correlation",
    "execution_updates": "scout:execution",
}


# ============================================================================
# REGIME SCOUT PAYLOAD
# ============================================================================

@dataclass
class RegimePayload:
    """Standardized regime intelligence payload."""
    symbol: str
    timestamp: datetime
    asset_class: str = "crypto"
    timeframe: str = "1m"

    # Classifications
    volatility_regime: str = "normal_vol"       # low_vol, normal_vol, high_vol, panic_vol
    trend_regime: str = "choppy"                # trending_up, trending_down, mean_reverting, choppy
    liquidity_regime: str = "normal"            # deep_liquid, normal, thin, dangerous
    correlation_regime: str = "diversified"     # diversified, clustered, panic_correlation, regime_break

    # Measurements
    atr_percentile: float = 50.0
    realized_volatility: float = 0.0
    relative_volume: float = 1.0
    spread_bps: float = 0.0

    # Structural flags
    compression_detected: bool = False
    expansion_detected: bool = False
    vwap_deviation_pct: float = 0.0

    # Confidence
    confidence_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        d["type"] = "regime_intelligence"
        return d


# ============================================================================
# LIQUIDITY SCOUT PAYLOAD
# ============================================================================

@dataclass
class LiquidityPayload:
    """Standardized liquidity intelligence payload."""
    symbol: str
    timestamp: datetime

    # Measurements
    avg_spread_bps: float = 0.0
    depth_imbalance: float = 1.0       # bid_volume / ask_volume
    liquidity_score: float = 50.0      # 0-100
    slippage_risk: float = 0.5         # 0-1
    market_impact_estimate: float = 0.0

    # Classification
    liquidity_regime: str = "normal"   # excellent, stable, thin, dangerous

    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        d["type"] = "liquidity_intelligence"
        return d


# ============================================================================
# CORRELATION SCOUT PAYLOAD
# ============================================================================

@dataclass
class CorrelationPayload:
    """Standardized correlation intelligence payload."""
    timestamp: datetime

    # Cluster analysis
    cluster_name: str = "unknown"
    avg_pairwise_corr: float = 0.0
    dominant_factor: str = ""
    risk_state: str = "diversified"     # diversified, clustered, panic_correlation, regime_break

    # Portfolio context
    symbols_analyzed: list = field(default_factory=list)
    top_correlated_pairs: dict = field(default_factory=dict)
    correlation_spike_detected: bool = False

    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        d["type"] = "correlation_intelligence"
        return d


# ============================================================================
# EXECUTION SCOUT PAYLOAD
# ============================================================================

@dataclass
class ExecutionPayload:
    """Standardized execution intelligence payload."""
    symbol: str
    broker: str
    timestamp: datetime

    # Execution quality
    avg_slippage_bps: float = 0.0
    fill_latency_ms: float = 0.0
    rejection_rate: float = 0.0
    fill_quality_score: float = 100.0   # 0-100

    # Classification
    execution_regime: str = "optimal"    # optimal, degraded, stressed, unstable

    # Context
    sample_size: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        d["type"] = "execution_intelligence"
        return d


# ============================================================================
# HELPER: Build a summary string from latest scout data for Ideator prompts
# ============================================================================

def scout_summary_for_ideator(
    regime: RegimePayload | None = None,
    liquidity: LiquidityPayload | None = None,
    correlation: CorrelationPayload | None = None,
    execution: ExecutionPayload | None = None,
) -> str:
    """Build a compressed one-paragraph scout intelligence summary for Ideator prompts."""
    parts = []

    if regime:
        vol = regime.volatility_regime
        trend = regime.trend_regime
        liq = regime.liquidity_regime
        conf = f"{regime.confidence_score:.0%}" if regime.confidence_score > 0 else ""
        parts.append(
            f"Market: vol={vol}, trend={trend}, liq={liq}"
            + (f" (conf={conf})" if conf else "")
        )

    if liquidity:
        parts.append(
            f"Liquidity: regime={liquidity.liquidity_regime}, "
            f"score={liquidity.liquidity_score:.0f}/100, "
            f"risk={liquidity.slippage_risk:.1f}"
        )

    if correlation:
        parts.append(
            f"Correlation: cluster={correlation.cluster_name}, "
            f"avg_corr={correlation.avg_pairwise_corr:.2f}, "
            f"risk={correlation.risk_state}"
        )

    if execution:
        parts.append(
            f"Execution: regime={execution.execution_regime}, "
            f"fill_score={execution.fill_quality_score:.0f}/100, "
            f"slippage={execution.avg_slippage_bps:.1f}bps"
        )

    return " | ".join(parts) if parts else "Scout intelligence unavailable."
