"""
copy_capital_allocator.py — Phase 21C

Intelligent follower exposure allocation:
- Volatility targeting
- Leverage normalization
- Exposure caps
- Liquidity-aware scaling
- Portfolio overlap constraints
- Follower risk profile
- Capital efficiency

NEVER blindly scales quantities.
"""

from __future__ import annotations

import asyncio
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


@dataclass
class FollowerProfile:
    """Risk profile for a copy follower account."""
    follower_id: str
    account_ref: str
    total_capital: float = 10000.0
    max_exposure_pct: float = 0.80     # Max 80% of capital exposed
    max_single_position_pct: float = 0.15  # Max 15% per symbol
    max_leverage: float = 2.0
    target_volatility: float = 0.15    # 15% annualized target vol
    min_order_value: float = 10.0      # Minimum order size
    risk_tier: str = "standard"        # conservative / standard / aggressive


@dataclass
class AllocationDecision:
    """Result of capital allocation computation."""
    follower_id: str
    symbol: str
    leader_qty: float
    allocated_qty: float
    scaling_factor: float
    rejection_reason: str | None = None
    adjustments: list[str] = field(default_factory=list)
    capital_utilization: float = 0.0


class CopyCapitalAllocator(BaseAgent):
    """L6 Agent — Intelligent follower capital allocation."""

    name = "CopyCapitalAllocator"
    agent_type = "copy_capital_allocator"
    layer = "L6"

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client)
        self.db = db_client
        self._profiles_cache: dict[str, FollowerProfile] = {}
        self._cache_ttl = 300  # Refresh every 5 min

    async def run(self):
        logger.info(f"{self.name}: Starting capital allocation engine")
        while self.status == "running":
            try:
                await self._refresh_profiles()
            except Exception as e:
                logger.error(f"{self.name}: Profile refresh error: {e}")
            await asyncio.sleep(self._cache_ttl)

    async def _refresh_profiles(self):
        """Load follower profiles from DB."""
        try:
            async with self.db.engine.connect() as conn:
                r = await conn.execute(text("""
                    SELECT follower_id, account_ref, allocation_ratio,
                           max_position_pct
                    FROM copy_follower_accounts
                    WHERE is_active = TRUE
                """))
                for row in r.fetchall():
                    fid = str(row[0])
                    self._profiles_cache[fid] = FollowerProfile(
                        follower_id=fid,
                        account_ref=str(row[1]),
                        max_single_position_pct=float(row[3] or 0.15),
                    )
            logger.debug(
                f"{self.name}: Loaded {len(self._profiles_cache)} profiles"
            )
        except Exception as e:
            logger.debug(f"{self.name}: Profile load: {e}")

    def compute_allocation(
        self,
        follower_id: str,
        symbol: str,
        leader_qty: float,
        leader_price: float,
        leader_total_exposure: float,
        current_follower_exposure: float,
        symbol_volatility: float = 0.02,
        liquidity_score: float = 1.0,
        overlap_penalty: float = 0.0,
    ) -> AllocationDecision:
        """
        Compute intelligent allocation for a follower copy order.
        Returns AllocationDecision with adjusted quantity and rationale.
        """
        profile = self._profiles_cache.get(follower_id)
        if not profile:
            profile = FollowerProfile(
                follower_id=follower_id, account_ref=follower_id
            )

        adjustments = []
        scaling = 1.0

        # Step 1: Base allocation ratio (capital proportional)
        if leader_total_exposure > 0:
            base_ratio = profile.total_capital / max(leader_total_exposure, 1.0)
            scaling = min(base_ratio, 1.0)
            adjustments.append(f"base_ratio={scaling:.3f}")
        else:
            scaling = 1.0

        # Step 2: Volatility targeting
        if symbol_volatility > 0:
            vol_target_scale = profile.target_volatility / max(
                symbol_volatility * math.sqrt(252), 0.01
            )
            vol_target_scale = min(vol_target_scale, 2.0)  # Cap at 2x
            if vol_target_scale < 1.0:
                scaling *= vol_target_scale
                adjustments.append(f"vol_target_scale={vol_target_scale:.3f}")

        # Step 3: Exposure cap enforcement
        position_value = abs(leader_qty * leader_price * scaling)
        max_position_value = profile.total_capital * profile.max_single_position_pct
        if position_value > max_position_value and position_value > 0:
            cap_scale = max_position_value / position_value
            scaling *= cap_scale
            adjustments.append(f"exposure_cap={cap_scale:.3f}")

        # Step 4: Total exposure limit
        projected_total = current_follower_exposure + abs(
            leader_qty * leader_price * scaling
        )
        max_total = profile.total_capital * profile.max_exposure_pct
        if projected_total > max_total:
            remaining = max(0, max_total - current_follower_exposure)
            order_value = abs(leader_qty * leader_price * scaling)
            if order_value > 0 and remaining > 0:
                total_cap = remaining / order_value
                scaling *= min(total_cap, 1.0)
                adjustments.append(f"total_exposure_cap={total_cap:.3f}")
            else:
                return AllocationDecision(
                    follower_id=follower_id,
                    symbol=symbol,
                    leader_qty=leader_qty,
                    allocated_qty=0,
                    scaling_factor=0,
                    rejection_reason="total_exposure_limit_exceeded",
                    adjustments=adjustments,
                )

        # Step 5: Leverage limit
        if scaling > profile.max_leverage:
            scaling = profile.max_leverage
            adjustments.append(f"leverage_cap={profile.max_leverage}")

        # Step 6: Liquidity-aware reduction
        if liquidity_score < 0.5:
            liq_scale = max(0.3, liquidity_score)
            scaling *= liq_scale
            adjustments.append(f"liquidity_reduction={liq_scale:.3f}")

        # Step 7: Portfolio overlap penalty
        if overlap_penalty > 0:
            overlap_scale = max(0.5, 1.0 - overlap_penalty)
            scaling *= overlap_scale
            adjustments.append(f"overlap_penalty={overlap_scale:.3f}")

        # Compute final quantity
        allocated_qty = abs(leader_qty) * scaling
        final_value = allocated_qty * leader_price

        # Step 8: Minimum order filter
        if final_value < profile.min_order_value and final_value > 0:
            return AllocationDecision(
                follower_id=follower_id,
                symbol=symbol,
                leader_qty=leader_qty,
                allocated_qty=0,
                scaling_factor=0,
                rejection_reason="below_minimum_order_value",
                adjustments=adjustments,
            )

        # Capital utilization
        cap_util = (
            (current_follower_exposure + final_value) / profile.total_capital
            if profile.total_capital > 0 else 0
        )

        return AllocationDecision(
            follower_id=follower_id,
            symbol=symbol,
            leader_qty=leader_qty,
            allocated_qty=round(allocated_qty, 6),
            scaling_factor=round(scaling, 6),
            adjustments=adjustments,
            capital_utilization=round(cap_util, 4),
        )
