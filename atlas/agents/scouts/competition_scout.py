"""
competition_scout.py — Real Kaggle API v1 implementation.

Replaces the old np.random-simulated CompetitionScout.
Fetches active data science competitions from Kaggle,
extracts trading-strategy-relevant insights via Claude,
and persists to external_scout_memory for pipeline consumption.

Requires: KAGGLE_USERNAME and KAGGLE_API_KEY in .env / settings.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any

from loguru import logger

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.serialization import safe_json_dumps
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings


# Keywords to filter for trading/finance-relevant competitions
FINANCE_TAGS = [
    "finance", "trading", "stock", "market", "crypto", "algorithmic",
    "quant", "portfolio", "risk", "prediction", "forecast", "time series",
    "price", "return", "volatility", "asset", "investment", "hedge",
]



HYPOTHESIS_SYSTEM = """You are a quantitative analyst extracting trading strategy insights from data science competitions.
Given a competition title, description, and evaluation metric, extract any signal.
If no clear trading insight exists, return null.
If a signal exists, return JSON only:
{
  "hypothesis": "one sentence describing the strategy-relevant insight",
  "ticker": null,
  "timeframe": "unknown",
  "strategy_type": "feature_engineering/modeling_technique/risk_method/execution_strategy/other",
  "confidence": 0.0-1.0,
  "technique": "the specific ML/AI technique or feature engineering approach"
}"""


class CompetitionScout(BaseAgent):
    """
    Real Kaggle API v1 scout.

    Fetches active competitions from Kaggle, filters for
    trading/finance relevance, extracts insights via Claude,
    and persists to external_scout_memory.
    No simulated data — real API calls only.
    """

    name = "CompetitionScout"
    agent_type = "external_scout"
    layer = "L7"
    RUN_INTERVAL = 7200  # every 2 hours (competitions don't change rapidly)
    API_BASE = "https://www.kaggle.com/api/v1"

    def __init__(
        self,
        redis_client=None,
        db_client: TimescaleClient | None = None,
        run_interval: int | None = None,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self._ssl_ctx = ssl.create_default_context()
        self._kaggle_username = getattr(settings, "kaggle_username", "") or ""
        self._kaggle_key = getattr(settings, "kaggle_api_key", "") or ""
        if run_interval is not None:
            self.RUN_INTERVAL = run_interval

        # Competition dedup cache: competition_ref -> datetime seen
        self._seen_competitions: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=24)  # re-check after 24 hours

    def _headers(self) -> dict[str, str]:
        """Build auth headers for Kaggle API."""
        creds = f"{self._kaggle_username}:{self._kaggle_key}"
        b64 = base64.b64encode(creds.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {b64}",
            "User-Agent": "ATLAS-CompetitionScout/1.0",
        }

    async def run(self):
        if not self._kaggle_username or not self._kaggle_key:
            logger.warning(
                f"{self.name}: KAGGLE_USERNAME/KAGGLE_API_KEY not set — scout disabled"
            )
            while self.status == "running":
                await asyncio.sleep(3600)
            return

        logger.info(
            f"{self.name}: started — real Kaggle API v1, "
            f"user={self._kaggle_username}"
        )
        while self.status == "running":
            try:
                await self._gather_signals()
            except Exception as e:
                logger.error(f"{self.name}: cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL)

    async def _gather_signals(self):
        """Main cycle: fetch competitions and extract insights."""
        # Prune expired entries from seen-competition cache
        now = datetime.now(timezone.utc)
        expired = [
            cid for cid, ts in self._seen_competitions.items()
            if now - ts > self._cache_ttl
        ]
        for cid in expired:
            del self._seen_competitions[cid]

        competitions = await self._fetch_competitions()
        if not competitions:
            logger.warning(f"{self.name}: no competitions returned from API")
            return

        logger.info(
            f"{self.name}: fetched {len(competitions)} total competitions"
        )

        # Filter to finance/trading-relevant ones
        relevant = [
            c for c in competitions
            if self._is_finance_relevant(c)
        ]
        logger.info(
            f"{self.name}: {len(relevant)} finance-relevant competitions "
            f"(out of {len(competitions)})"
        )

        hypotheses_extracted = 0
        for comp in relevant[:10]:  # max 10 per cycle
            comp_ref = comp.get("ref", "") or str(comp.get("id", ""))
            if not comp_ref or comp_ref in self._seen_competitions:
                continue
            self._seen_competitions[comp_ref] = now

            try:
                hypothesis = await self._analyze_competition(comp)
                if hypothesis:
                    await self._save_signal(hypothesis, comp)
                    hypotheses_extracted += 1
            except Exception as e:
                logger.debug(f"{self.name}: skip competition {comp_ref}: {e}")

        logger.info(
            f"{self.name}: {hypotheses_extracted}/{len(relevant)} "
            f"hypotheses extracted"
        )

    # ------------------------------------------------------------------
    # Kaggle API calls
    # ------------------------------------------------------------------

    def _kaggle_get(self, path: str) -> list[dict] | dict:
        """Synchronous Kaggle REST API GET request via urllib."""
        url = f"{self.API_BASE}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as r:
            return json.loads(r.read())

    async def _fetch_competitions(self) -> list[dict]:
        """
        Fetch all active competitions from Kaggle.
        Returns competition list sorted by deadline (most recent first).
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, lambda: self._kaggle_get("/competitions/list")
            )
            if isinstance(result, list):
                # Sort by deadline descending — most urgent first
                result.sort(
                    key=lambda c: c.get("deadline", ""),
                    reverse=True,
                )
                return result
            logger.warning(
                f"{self.name}: unexpected response type from Kaggle API"
            )
            return []
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", errors="replace")[:200]
            logger.warning(
                f"{self.name}: Kaggle API HTTP {status}: {body}"
            )
            return []
        except Exception as e:
            logger.warning(f"{self.name}: Kaggle API error: {e}")
            return []

    # ------------------------------------------------------------------
    # Competition analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _is_finance_relevant(comp: dict) -> bool:
        """Check if a competition is relevant to trading/finance."""
        text_fields = [
            comp.get("title", ""),
            comp.get("subtitle", ""),
            comp.get("description", ""),
            comp.get("category", ""),
            comp.get("evaluationMetric", ""),
            str(comp.get("tags", [])),
        ]
        combined = " ".join(text_fields).lower()

        # Check for finance keywords
        return any(tag in combined for tag in FINANCE_TAGS)

    async def _analyze_competition(self, comp: dict) -> dict | None:
        """Use Claude to extract trading insight from a competition."""
        title = comp.get("title", "Untitled")
        subtitle = comp.get("subtitle", "")
        description = comp.get("description", "")[:600]
        category = comp.get("category", "")
        metric = comp.get("evaluationMetric", "")
        reward = comp.get("reward", "")
        deadline = comp.get("deadline", "")

        user_prompt = (
            f"Kaggle Competition:\n"
            f"Title: {title}\n"
            f"Subtitle: {subtitle}\n"
            f"Category: {category}\n"
            f"Evaluation Metric: {metric}\n"
            f"Reward: {reward}\n"
            f"Deadline: {deadline}\n"
            f"Description: {description[:500]}\n\n"
            "Extract any trading strategy insight from this competition."
        )

        try:
            raw = await _claude.complete(
                user=user_prompt,
                system=HYPOTHESIS_SYSTEM,
                max_tokens=250,
                temperature=0.2,
            )
            raw = raw.strip()
            if raw.lower() == "null" or not raw.startswith("{"):
                return None
            hypothesis = json.loads(raw)
            # Augment with competition metadata
            hypothesis["competition_title"] = title
            hypothesis["competition_url"] = (
                f"https://kaggle.com/competitions/{comp.get('ref', '')}"
            )
            hypothesis["reward"] = reward
            hypothesis["deadline"] = deadline
            return hypothesis
        except (json.JSONDecodeError, Exception):
            return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_signal(self, hypothesis: dict, comp: dict) -> None:
        """
        Persist to external_scout_memory.
        Auto-mirrors to scout_signals via _SCOUT_TABLE_MIRROR_MAP.
        """
        strategy_type = hypothesis.get("strategy_type", "other")
        confidence = float(hypothesis.get("confidence", 0.4))
        technique = hypothesis.get("technique", "unknown")
        hypothesis_text = hypothesis.get("hypothesis", "")
        comp_title = hypothesis.get("competition_title", "Untitled")
        comp_url = hypothesis.get("competition_url", "")

        if not self.db:
            logger.warning(f"{self.name}: no DB client, can't persist")
            return

        # Competition signals are always neutral (insight, not directional)
        sentiment = 0.15  # positive insight signal
        signal_dir = "insight"

        try:
            await self.db._execute_insert(
                """
                INSERT INTO external_scout_memory
                    (id, source, source_sub, source_reliability,
                     timestamp, sentiment, mentioned_tickers,
                     hypothesis_score, signal_direction, metadata)
                VALUES
                    (:id, :source, :source_sub, :reliability,
                     NOW(), :sentiment, :tickers,
                     :score, :direction, CAST(:metadata AS jsonb))
                """,
                {
                    "id": self.select_trace_id(),
                    "source": "competition",
                    "source_sub": "kaggle",
                    "reliability": 0.7,
                    "sentiment": sentiment,
                    "tickers": safe_json_dumps([]),
                    "score": round(confidence, 4),
                    "direction": signal_dir,
                    "metadata": safe_json_dumps({
                        "hypothesis": hypothesis_text,
                        "strategy_type": strategy_type,
                        "technique": technique,
                        "competition_title": comp_title,
                        "competition_url": comp_url,
                        "reward": hypothesis.get("reward", ""),
                        "deadline": hypothesis.get("deadline", ""),
                        "category": comp.get("category", ""),
                        "evaluation_metric": comp.get("evaluationMetric", ""),
                    }),
                },
            )

            logger.info(
                f"{self.name}: saved {strategy_type} insight "
                f"confidence={confidence:.2f} — '{comp_title[:60]}'"
            )

        except Exception as e:
            logger.error(f"{self.name}: save failed: {e}")
