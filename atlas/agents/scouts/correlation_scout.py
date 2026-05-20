"""
CorrelationScout — Portfolio-Level Correlation Intelligence Agent.

Detects:
- Rolling pairwise correlations between tracked symbols
- Portfolio clustering (diversified, clustered, panic_correlation)
- Correlation spikes (regime breaks)
- Dominant factors driving correlation structure

RUN INTERVAL: 300 seconds (5 min)

Integrations:
- Ideator: avoid generating strategies for over-concentrated symbols
- Validator: require stronger robustness during panic correlation
- Portfolio risk: correlate with kill switch for beta compression
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.core.scout_contracts.scout_contract import (
    CorrelationPayload,
    SCOUT_CHANNELS,
    scout_summary_for_ideator,
)


class CorrelationScout(BaseAgent):
    """
    Portfolio-level correlation intelligence.
    Computes rolling pairwise correlations across tracked symbols
    and classifies the portfolio risk state.
    """

    name = "CorrelationScout"
    agent_type = "scout"
    layer = "L1"

    RUN_INTERVAL_SECONDS = 300

    # Correlation thresholds
    CLUSTERED_THRESHOLD = 0.70      # avg pairwise corr above = clustered
    PANIC_THRESHOLD = 0.85          # avg pairwise corr above = panic
    SPIKE_DELTA = 0.15              # corr increase > this = spike

    # Minimum bars for correlation computation
    MIN_BARS = 50
    CORR_WINDOW = 40                # rolling window for pairwise corr

    # Default cluster assignments by asset class
    CLUSTER_MAP = {
        "BTCUSDT": "crypto_majors",
        "ETHUSDT": "crypto_majors",
        "SOLUSDT": "crypto_majors",
        "SPY": "broad_equity",
        "QQQ": "tech_heavy",
        "AAPL": "tech_heavy",
        "MSFT": "tech_heavy",
        "NVDA": "tech_heavy",
        "TSLA": "high_beta_equity",
    }

    def __init__(
        self,
        redis_client: Redis,
        db_client: TimescaleClient,
        symbols: Optional[list[str]] = None,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.messaging = MessagingClient(redis_client)

        self.symbols = symbols or [
            "BTCUSDT", "ETHUSDT", "SOLUSDT",
            "SPY", "QQQ", "AAPL", "MSFT", "NVDA",
        ]

        self._latest_payload: Optional[CorrelationPayload] = None
        self._prev_avg_corr: Optional[float] = None

    async def run(self):
        logger.info(f"{self.name} started — tracking {len(self.symbols)} symbols")
        while self.status == "running":
            try:
                payload = await self._analyze_correlations()
                if payload:
                    await self._persist(payload)
                    await self._publish(payload)
                    await self._publish_summary()
                    self._latest_payload = payload
                    self._prev_avg_corr = payload.avg_pairwise_corr

                    logger.info(
                        f"{self.name}: cluster={payload.cluster_name}, "
                        f"avg_corr={payload.avg_pairwise_corr:.2f}, "
                        f"risk={payload.risk_state}, "
                        f"spike={'YES' if payload.correlation_spike_detected else 'no'}"
                    )
            except Exception as e:
                logger.error(f"{self.name} cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _analyze_correlations(self) -> Optional[CorrelationPayload]:
        """Compute rolling correlations across all tracked symbols."""
        returns_matrix = {}
        valid_symbols = []

        for symbol in self.symbols:
            try:
                df = await self.db.fetch_recent_bars(symbol, limit=self.CORR_WINDOW + 10)
                if df is None or len(df) < self.MIN_BARS:
                    continue

                close = df["close"].values.astype(float)
                ret = np.diff(np.log(close + 1e-10))
                if len(ret) < self.CORR_WINDOW:
                    continue

                returns_matrix[symbol] = ret[-self.CORR_WINDOW:]
                valid_symbols.append(symbol)
            except Exception as e:
                logger.debug(f"{self.name}: Error fetching {symbol}: {e}")
                continue

        if len(valid_symbols) < 2:
            logger.debug(f"{self.name}: Only {len(valid_symbols)} symbols with data — skipping")
            return None

        # Build pairwise correlation matrix
        n = len(valid_symbols)
        corr_matrix = np.ones((n, n))
        pairs = {}
        for i in range(n):
            for j in range(i + 1, n):
                min_len = min(len(returns_matrix[valid_symbols[i]]), len(returns_matrix[valid_symbols[j]]))
                r_i = returns_matrix[valid_symbols[i]][-min_len:]
                r_j = returns_matrix[valid_symbols[j]][-min_len:]
                corr = np.corrcoef(r_i, r_j)[0, 1]
                if not np.isfinite(corr):
                    corr = 0.0
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr
                pairs[f"{valid_symbols[i]}_{valid_symbols[j]}"] = round(float(corr), 4)

        avg_corr = float(np.mean(corr_matrix[np.triu_indices(n, k=1)]))

        # Cluster determination: group by correlation similarity
        clusters = {}
        for sym in valid_symbols:
            cluster = self.CLUSTER_MAP.get(sym, "other")
            if cluster not in clusters:
                clusters[cluster] = []
            clusters[cluster].append(sym)

        dominant_cluster = max(clusters, key=lambda c: len(clusters[c]))
        dominant_factor = self._infer_dominant_factor(valid_symbols, returns_matrix)

        # Risk state classification
        spike_detected = False
        if self._prev_avg_corr is not None:
            delta = avg_corr - self._prev_avg_corr
            spike_detected = delta > self.SPIKE_DELTA

        if avg_corr >= self.PANIC_THRESHOLD:
            risk_state = "panic_correlation"
        elif avg_corr >= self.CLUSTERED_THRESHOLD:
            risk_state = "clustered"
        elif spike_detected:
            risk_state = "regime_break"
        else:
            risk_state = "diversified"

        # Top correlated pairs
        sorted_pairs = sorted(pairs.items(), key=lambda x: abs(x[1]), reverse=True)
        top_pairs = dict(sorted_pairs[:5])

        return CorrelationPayload(
            timestamp=datetime.now(timezone.utc),
            cluster_name=dominant_cluster,
            avg_pairwise_corr=round(float(avg_corr), 4),
            dominant_factor=dominant_factor,
            risk_state=risk_state,
            symbols_analyzed=valid_symbols,
            top_correlated_pairs=top_pairs,
            correlation_spike_detected=spike_detected,
        )

    def _infer_dominant_factor(
        self, symbols: list[str], returns: dict[str, np.ndarray]
    ) -> str:
        """Find the symbol with highest average pairwise correlation = dominant factor."""
        best_sym = symbols[0]
        best_avg = -1.0

        for sym_i in symbols:
            corrs = []
            for sym_j in symbols:
                if sym_i == sym_j:
                    continue
                min_len = min(len(returns[sym_i]), len(returns[sym_j]))
                r_i = returns[sym_i][-min_len:]
                r_j = returns[sym_j][-min_len:]
                c = np.corrcoef(r_i, r_j)[0, 1]
                if np.isfinite(c):
                    corrs.append(abs(c))
            if corrs:
                avg = np.mean(corrs)
                if avg > best_avg:
                    best_avg = avg
                    best_sym = sym_i

        return best_sym

    async def _persist(self, payload: CorrelationPayload):
        """Insert correlation intelligence into correlation_memory table."""
        query = """
            INSERT INTO correlation_memory (
                timestamp, cluster_name, avg_pairwise_corr,
                dominant_factor, risk_state, symbols_analyzed,
                top_correlated_pairs, correlation_spike_detected,
                metadata
            ) VALUES (
                :timestamp, :cluster_name, :avg_pairwise_corr,
                :dominant_factor, :risk_state, :symbols_analyzed,
                :top_correlated_pairs, :correlation_spike_detected,
                :metadata
            )
        """
        params = {
            "timestamp": payload.timestamp,
            "cluster_name": payload.cluster_name,
            "avg_pairwise_corr": payload.avg_pairwise_corr,
            "dominant_factor": payload.dominant_factor,
            "risk_state": payload.risk_state,
            "symbols_analyzed": payload.symbols_analyzed,
            "top_correlated_pairs": json.dumps(payload.top_correlated_pairs),
            "correlation_spike_detected": payload.correlation_spike_detected,
            "metadata": json.dumps(payload.metadata),
        }
        await self.db._execute_insert(query, params)

    async def _publish(self, payload: CorrelationPayload):
        """Publish correlation intelligence to Redis."""
        channel = SCOUT_CHANNELS["correlation_updates"]
        await self._redis.publish(channel, json.dumps(payload.to_dict()))

    async def _publish_summary(self):
        """Publish a compressed summary for Ideator/Validator consumption."""
        if self._latest_payload is None:
            return
        summary = scout_summary_for_ideator(correlation=self._latest_payload)
        await self._redis.set("scout:correlation_summary", summary, ex=600)

    def get_latest(self) -> Optional[CorrelationPayload]:
        return self._latest_payload
