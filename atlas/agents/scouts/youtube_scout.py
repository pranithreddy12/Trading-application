"""
youtube_scout.py — Real YouTube Data API v3 implementation.

Replaces the old np.random-simulated YouTubeScout.
Searches YouTube for trading strategy videos via the Data API v3,
extracts hypotheses via Claude, and persists to scout_signals
and external_scout_memory for pipeline consumption.

Requires: YOUTUBE_API_KEY in .env / settings.
"""

from __future__ import annotations

import asyncio
import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any

from loguru import logger

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.serialization import safe_json_dumps
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from atlas.agents.scouts.scout_group_config import (
    ScoutGroup,
    parse_scout_groups,
)


DEFAULT_SEARCH_QUERIES = [
    "algorithmic trading strategy 2026",
    "quantitative trading momentum",
    "stock market breakout strategy",
    "crypto trading signals technical analysis",
    "mean reversion trading strategy",
    "options flow trading signals",
    "high frequency trading strategy",
]

HYPOTHESIS_SYSTEM = """You are a quantitative analyst extracting trading hypotheses.
Given a YouTube video title and description, extract any trading strategy idea.
If no clear strategy exists, return null.
If a strategy exists, return JSON only:
{
  "hypothesis": "one sentence strategy description",
  "ticker": "symbol or null",
  "timeframe": "intraday/swing/position",
  "strategy_type": "momentum/mean_reversion/breakout/other",
  "confidence": 0.0-1.0,
  "source_url": "url"
}"""


class YouTubeScout(BaseAgent):
    """
    Real YouTube Data API v3 scout.

    Searches for trading strategy videos and extracts hypotheses via Claude.
    No simulated data — real API calls only.
    Persists to scout_signals (for internal pipeline) and
    external_scout_memory (for synthesis engine).
    """

    name = "YouTubeScout"
    agent_type = "external_scout"
    layer = "L7"
    RUN_INTERVAL = 3600  # every hour

    def __init__(
        self,
        redis_client=None,
        db_client: TimescaleClient | None = None,
        run_interval: int | None = None,
        groups: list[ScoutGroup] | None = None,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self._ssl_ctx = ssl.create_default_context()
        self._api_key = getattr(settings, "youtube_api_key", "") or ""
        if run_interval is not None:
            self.RUN_INTERVAL = run_interval

        # ── Scout group configuration ─────────────────────────────────
        raw_scout_groups = getattr(settings, "scout_groups", "") or ""
        self._groups: list[ScoutGroup] = (
            groups
            if groups is not None
            else parse_scout_groups(
                raw_scout_groups,
                fallback_youtube_queries=DEFAULT_SEARCH_QUERIES,
            )
        )

    async def run(self):
        if not self._api_key:
            logger.warning(f"{self.name}: YOUTUBE_API_KEY not set — scout disabled")
            while self.status == "running":
                await asyncio.sleep(3600)
            return

        logger.info(
            f"{self.name}: started — real YouTube Data API v3, "
            f"{len(self._groups)} group(s): {[g.name for g in self._groups]}"
        )
        while self.status == "running":
            try:
                await self._gather_signals()
            except Exception as e:
                logger.error(f"{self.name}: cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL)

    async def _gather_signals(self):
        """Iterate over all groups and their search queries, fetch YouTube results."""
        total_hypotheses = 0
        total_videos = 0

        for group in self._groups:
            queries = group.youtube
            if not queries:
                continue

            for query in queries:
                logger.info(f"{self.name}: [{group.name}] searching '{query}'")
                videos = await self._search_videos(query, max_results=10)
                if not videos:
                    logger.debug(
                        f"{self.name}: [{group.name}] no results for '{query}'"
                    )
                    continue

                total_videos += len(videos)
                for video in videos:
                    try:
                        hypothesis = await self._extract_hypothesis(video)
                        if hypothesis:
                            await self._save_signal(hypothesis, video, group.name)
                            total_hypotheses += 1
                    except Exception as e:
                        logger.debug(
                            f"{self.name}: [{group.name}] skip video {video.get('id')}: {e}"
                        )

        logger.info(
            f"{self.name}: {total_hypotheses}/{total_videos} hypotheses extracted "
            f"across {len(self._groups)} group(s)"
        )

    def _youtube_search(self, query: str, max_results: int) -> dict:
        """Synchronous YouTube API call via urllib."""
        published_after = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params = urllib.parse.urlencode(
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "relevance",
                "maxResults": max_results,
                "publishedAfter": published_after,
                "relevanceLanguage": "en",
                "key": self._api_key,
            }
        )
        url = f"https://www.googleapis.com/youtube/v3/search?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as r:
            return json.loads(r.read())

    async def _search_videos(self, query: str, max_results: int = 10) -> list[dict]:
        """Async wrapper around the synchronous YouTube search."""
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None, lambda: self._youtube_search(query, max_results)
            )
            items = data.get("items", [])
            videos = []
            for item in items:
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                if not video_id:
                    continue
                videos.append(
                    {
                        "id": video_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:500],
                        "channel": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )
            return videos
        except Exception as e:
            logger.error(f"{self.name}: API error: {e}")
            return []

    async def _extract_hypothesis(self, video: dict) -> dict | None:
        """Use Claude to extract a trading hypothesis from video metadata."""
        user_prompt = (
            f"Video title: {video['title']}\n"
            f"Channel: {video['channel']}\n"
            f"Description: {video['description']}\n"
            f"URL: {video['url']}\n\n"
            "Extract any trading strategy hypothesis from this video."
        )

        try:
            raw = await _claude.complete(
                user=user_prompt,
                system=HYPOTHESIS_SYSTEM,
                max_tokens=300,
                temperature=0.3,
            )
            raw = raw.strip()
            if raw.lower() == "null" or not raw.startswith("{"):
                return None
            data = json.loads(raw)
            data["source_url"] = video["url"]
            return data
        except (json.JSONDecodeError, Exception):
            return None

    async def _save_signal(
        self, hypothesis: dict, video: dict, group_name: str = ""
    ) -> None:
        """
        Persist to external_scout_memory.
        Auto-mirrors to scout_signals via _SCOUT_TABLE_MIRROR_MAP in timescale_client.
        """
        ticker = hypothesis.get("ticker") or "unknown"
        strategy_type = hypothesis.get("strategy_type", "other")
        confidence = float(hypothesis.get("confidence", 0.5))
        hypothesis_text = hypothesis.get("hypothesis", "")

        if not self.db:
            logger.warning(f"{self.name}: no DB client, can't persist")
            return

        # Compute sentiment from hypothesis text
        sentiment = confidence if "bull" in hypothesis_text.lower() else -confidence
        direction = (
            "bullish"
            if sentiment > 0.2
            else "bearish"
            if sentiment < -0.2
            else "neutral"
        )

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
                    "source": "youtube",
                    "source_sub": video.get("channel", ""),
                    "reliability": 0.6,
                    "sentiment": round(sentiment, 4),
                    "tickers": safe_json_dumps(
                        [{"ticker": ticker, "sentiment": round(sentiment, 4)}]
                    ),
                    "score": round(confidence, 4),
                    "direction": direction,
                    "metadata": safe_json_dumps(
                        {
                            "hypothesis": hypothesis_text,
                            "strategy_type": strategy_type,
                            "timeframe": hypothesis.get("timeframe"),
                            "source_url": hypothesis.get("source_url"),
                            "video_title": video.get("title"),
                            "channel": video.get("channel"),
                            "published_at": video.get("published_at"),
                            "groups": [group_name] if group_name else [],
                        }
                    ),
                },
            )

            logger.info(
                f"{self.name}: [{group_name}] saved signal — {strategy_type} "
                f"({ticker}) confidence={confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"{self.name}: save failed: {e}")
