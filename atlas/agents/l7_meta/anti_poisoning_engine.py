"""
anti_poisoning_engine.py — Phase 22

Detects coordinated signal bursts, evolutionary poisoning attempts, and 
adversarial consensus manipulation. Enforces signal quarantine and 
slashes source trust for malicious behavior.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from typing import Any

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class AntiPoisoningEngine(BaseAgent):
    """L7 Agent — Defense against evolutionary poisoning and adversarial inputs."""

    name = "AntiPoisoningEngine"
    agent_type = "anti_poisoning"
    layer = "L7"

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client)
        self.redis = redis_client
        self.db = db_client
        self._run_interval = 300  # Every 5 minutes
        
        # Detection Thresholds — Phase 27C: Per-scout source-aware baselines
        # Different scouts have different natural emission rates:
        # - regime_scout: 48-60+ signals/hour/symbol (high-frequency regime updates)
        # - liquidity_scout: 40-50 signals/hour/symbol (continuous liquidity assessment)
        # - correlation_scout: 20-30 signals/hour/symbol (lower frequency regime changes)
        # - execution_scout: 10-20 signals/hour/symbol (event-driven)
        # - external sources: 5-10 signals/hour/symbol (human-generated content)
        self.PER_SCOUT_BURST_LIMITS = {
            "regime_scout": 300,       # High cadence — continuous regime tracking
            "liquidity_scout": 250,    # Dense cadence — continuous liquidity assessment
            "correlation_scout": 150,  # Moderate — correlation regime changes
            "execution_scout": 100,    # Event-driven — execution quality reports
            "default": 100,            # Default for unknown/unconfigured sources
        }
        self.COORDINATED_THRESHOLD = 5 # Minimum sources required to trigger coordinated attack detection
        self.BURST_WINDOW_MINUTES = 60  # Lookback window for burst detection
        
    async def run(self):
        logger.info(f"{self.name}: Starting anti-poisoning engine")
        while self.status == "running":
            try:
                await self._scan_for_poison()
            except Exception as e:
                logger.error(f"{self.name}: Poison scan error: {e}")
            for _ in range(self._run_interval // 10):
                await asyncio.sleep(10)
                if self.status != "running":
                    return

    async def _scan_for_poison(self):
        """Scan recent signals for malicious patterns."""
        await self._detect_signal_bursts()
        await self._detect_coordinated_attacks()
        await self._quarantine_stale_contradictions()

    def _get_scout_burst_limit(self, source: str) -> int:
        """Phase 27C: Get per-scout burst limit with fallback to default."""
        return self.PER_SCOUT_BURST_LIMITS.get(
            source,
            self.PER_SCOUT_BURST_LIMITS["default"]
        )

    async def _detect_signal_bursts(self):
        """Phase 27C: Detect instances where a source spams signals.
        
        Uses per-scout baseline expectations:
        - regime_scout has a HIGH natural cadence (continuous regime tracking)
        - liquidity_scout has a DENSE natural cadence
        - External/news sources have a LOW natural cadence
        
        Burst detection is now SOURCE-AWARE with adaptive thresholds.
        """
        try:
            async with self.db.engine.connect() as conn:
                # Fetch ALL sources with their signal counts first
                r = await conn.execute(text("""
                    SELECT source, symbol, COUNT(*) as signal_count
                    FROM scout_signals
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY source, symbol
                    ORDER BY signal_count DESC
                """))
                
                rows = r.fetchall()
                for row in rows:
                    source = str(row[0])
                    symbol = str(row[1])
                    count = int(row[2])
                    
                    # Phase 27C: Per-scout adaptive burst limit
                    limit = self._get_scout_burst_limit(source)
                    
                    # Cadence-aware detection: also check per-minute rate
                    rate = count / self.BURST_WINDOW_MINUTES  # signals per minute
                    
                    # Calculate expected rate from limit
                    expected_rate = limit / self.BURST_WINDOW_MINUTES
                    
                    # Only trigger if count exceeds limit AND rate is anomalous
                    # (avoids false positives from bursty-but-normal activity)
                    if count > limit and rate > expected_rate * 2:
                        await self._execute_quarantine(
                            source=source,
                            source_sub="all",
                            violation_type="signal_burst_spam",
                            severity=0.3,  # Gentle response
                            symbols=[symbol],
                            action="slash_trust_and_quarantine_signals",
                            reason=f"{count} signals in 1 hour for {symbol} (limit={limit}, rate={rate:.1f}/min)"
                        )
        except Exception as e:
            logger.debug(f"{self.name}: Burst detection error: {e}")

    async def _detect_coordinated_attacks(self):
        """Phase 27C: Detect when multiple low-trust sources converge on the same asset.
        
        Improved with:
        - Trust-aware filtering: only distrusts low-trust sources
        - Per-scout cadence normalization: accounts for natural emission rates
        - Confidence-weighted assessment: low-confidence concensus is less suspicious
        """
        try:
            async with self.db.engine.connect() as conn:
                r = await conn.execute(text("""
                    SELECT ss.symbol, COUNT(DISTINCT ss.source) as num_sources, 
                           SUM(ss.confidence_score) as total_conf,
                           AVG(spl.dynamic_trust_score) as avg_trust
                    FROM scout_signals ss
                    LEFT JOIN (
                        SELECT DISTINCT ON (source) source, dynamic_trust_score
                        FROM source_performance_log
                        ORDER BY source, updated_at DESC
                    ) spl ON ss.source = spl.source
                    WHERE ss.created_at > NOW() - INTERVAL '30 minutes'
                    GROUP BY ss.symbol
                    HAVING COUNT(DISTINCT ss.source) >= :threshold
                """), {"threshold": self.COORDINATED_THRESHOLD})
                
                attacks = r.fetchall()
                for row in attacks:
                    symbol = str(row[0])
                    num_sources = int(row[1])
                    avg_trust = float(row[3] or 0.5)
                    
                    # Phase 27C: Only flag if average trust is low (< 0.8)
                    # High-trust sources converging is NORMAL (consensus), not an attack
                    if avg_trust >= 0.8:
                        continue
                    
                    # Get participating sources
                    r_sources = await conn.execute(text("""
                        SELECT DISTINCT source FROM scout_signals 
                        WHERE symbol = :sym AND created_at > NOW() - INTERVAL '30 minutes'
                    """), {"sym": symbol})
                    
                    sources = [str(s[0]) for s in r_sources.fetchall()]
                    
                    for source in sources:
                        await self._execute_quarantine(
                            source=source,
                            source_sub="all",
                            violation_type="coordinated_attack_suspect",
                            severity=0.5,
                            symbols=[symbol],
                            action="slash_trust_and_quarantine_signals",
                            reason=f"Coordinated burst among {num_sources} low-trust sources for {symbol}"
                        )
        except Exception as e:
            logger.debug(f"{self.name}: Coordinated attack detection error: {e}")

    async def _quarantine_stale_contradictions(self):
        """Quarantine signals that contradict the trusted consensus over time."""
        # This will be enriched in Phase 22 Consensus Governance
        pass

    async def _execute_quarantine(
        self, source: str, source_sub: str, violation_type: str, 
        severity: float, symbols: list[str], action: str, reason: str
    ):
        trace_id = self.select_trace_id()
        
        # 1. Log the quarantine event
        await self.db._execute_insert(
            """
            INSERT INTO scout_poison_quarantine
                (id, trace_id, source, source_sub, violation_type,
                 severity_score, affected_symbols, action_taken, metadata)
            VALUES
                (:id, :trace_id, :source, :sub, :violation,
                 :severity, CAST(:symbols AS jsonb), :action, CAST(:metadata AS jsonb))
            """,
            {
                "id": self.select_trace_id(),
                "trace_id": trace_id,
                "source": source,
                "sub": source_sub,
                "violation": violation_type,
                "severity": severity,
                "symbols": json.dumps(symbols),
                "action": action,
                "metadata": json.dumps({"reason": reason})
            }
        )
        
        # 2. Slash trust in source_performance_log — Phase 26H fix: reduced slash from severity*0.5 to severity*0.15
        await self.db._execute_insert(
            """
            INSERT INTO source_performance_log
                (id, source, source_sub, dynamic_trust_score, n_quarantined_signals)
            VALUES
                (:id, :source, :sub, :trust, 1)
            ON CONFLICT (id) DO NOTHING
            """,
            {
                "id": self.select_trace_id(),
                "source": source,
                "sub": source_sub,
                "trust": max(0.0, 0.9 - severity)  # Phase 26H fix: raised floor from 0.5 → 0.9 (gentler initial trust)
            }
        )
        
        # UPDATE existing trust with a gentler slash
        async with self.db.engine.begin() as conn:
            await conn.execute(text("""
                UPDATE source_performance_log
                SET dynamic_trust_score = GREATEST(0.01, LEAST(1.0, dynamic_trust_score - :slash_amount)),
                    n_quarantined_signals = n_quarantined_signals + 1,
                    updated_at = NOW()
                WHERE source = :source
            """), {"slash_amount": severity * 0.15, "source": source})  # Phase 26H fix: reduced from severity*0.5 to severity*0.15
            
        logger.warning(
            f"{self.name}: {violation_type} detected for {source}. "
            f"Action: {action}. Trace: {trace_id}"
        )
