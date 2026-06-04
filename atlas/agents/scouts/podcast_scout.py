"""
podcast_scout.py — Real Podcast RSS Feed implementation.

Replaces the old np.random-simulated PodcastScout.
Fetches episode metadata from finance/trading podcast RSS feeds,
filters for trading-relevant content, extracts hypotheses via Claude,
and persists to external_scout_memory for pipeline consumption.

Requires: Nothing beyond feedparser and requests.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import feedparser
import requests
from loguru import logger

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.serialization import safe_json_dumps
from atlas.data.storage.timescale_client import TimescaleClient


# Curated list of finance/trading podcast RSS feeds (verified working)
PODCAST_FEEDS = [
    # General market & macro
    {"name": "Macro Voices", "url": "https://feed.podbean.com/macrovoices/feed.xml", "weight": 0.75},
    {"name": "The Compound and Friends", "url": "https://feeds.megaphone.fm/TCP6464651487", "weight": 0.60},
    {"name": "Macro Hive", "url": "https://macrohive.libsyn.com/rss", "weight": 0.65},
    # Trading-focused
    {"name": "Chat With Traders", "url": "https://chatwithtraders.libsyn.com/rss", "weight": 0.80},
    {"name": "Top Traders Unplugged", "url": "https://feeds.captivate.fm/top-traders-unplugged/", "weight": 0.75},
    {"name": "Better System Trader", "url": "https://bettersystemtrader.libsyn.com/rss", "weight": 0.85},
]

# Keywords suggesting an episode might contain trading/finance signals
TRADING_KEYWORDS = [
    "trade", "trading", "strategy", "market", "stock", "equity",
    "option", "futures", "crypto", "bitcoin", "ethereum",
    "signal", "entry", "exit", "breakout", "momentum",
    "reversal", "mean reversion", "volatility", "risk",
    "portfolio", "allocat", "hedge", "macro", "yield",
    "dividend", "earning", "fed", "treasury", "bond",
    "commodity", "gold", "oil", "forex", "currency",
    "recession", "inflation", "gdp", "economic",
    "bullish", "bearish", "correction", "rally",
    "quant", "algorithmic", "systematic", "factor",
]

# Regex to find potential ticker symbols
TICKER_PATTERN = re.compile(r'\$([A-Z]{2,6})\b')

# Common false-positive words that look like tickers
FALSE_TICKERS = {
    "THE", "AND", "FOR", "BUT", "HAS", "ARE", "NEW", "NOW",
    "NOT", "YOU", "ALL", "CAN", "WAS", "OUT", "ONE", "GET",
    "ITS", "DID", "SAY", "WAY", "USE", "MAY", "SEE", "HOW",
    "LOW", "HIGH", "BIG", "TOP", "END", "LET", "TRY",
    "BULL", "BEAR", "MOON", "FOMO", "HODL", "DCA", "ATH",
    "GDP", "ETF", "IPO", "CEO", "CFO", "CPI", "PPI", "EPS",
}

HYPOTHESIS_SYSTEM = """You are a quantitative analyst extracting trading hypotheses from podcast episodes.
Given a podcast episode title and description, extract any trading strategy signal or market insight.
If no clear trading signal exists, return null.
If a signal exists, return JSON only:
{
  "hypothesis": "one sentence signal description",
  "ticker": "symbol or null",
  "timeframe": "intraday/swing/position/unknown",
  "strategy_type": "momentum/mean_reversion/breakout/macro/sentiment/market_commentary/other",
  "confidence": 0.0-1.0,
  "direction": "bullish/bearish/neutral"
}"""


class PodcastScout(BaseAgent):
    """
    Real Podcast RSS Feed scout.

    Fetches episode metadata from curated finance/trading podcast RSS feeds,
    filters for trading-relevant content, extracts hypotheses via Claude,
    and persists to external_scout_memory.
    No simulated data -- real RSS feed data only.
    """

    name = "PodcastScout"
    agent_type = "external_scout"
    layer = "L7"
    RUN_INTERVAL = 7200  # every 2 hours (podcasts publish daily/weekly)
    REQUEST_TIMEOUT = 20  # seconds per RSS fetch

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
        if run_interval is not None:
            self.RUN_INTERVAL = run_interval

        # Episode dedup cache: episode_guid -> datetime seen
        self._seen_episodes: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=12)
        self._max_seen = 2000

    async def run(self):
        logger.info(
            f"{self.name}: started -- real RSS feed podcast scout, "
            f"{len(PODCAST_FEEDS)} feed(s) configured"
        )
        while self.status == "running":
            try:
                await self._gather_signals()
            except Exception as e:
                logger.error(f"{self.name}: cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL)

    async def _gather_signals(self):
        """Main cycle: fetch all podcast RSS feeds and extract hypotheses."""
        # Prune expired entries from seen-episode cache
        now = datetime.now(timezone.utc)
        self._prune_seen_episodes(now)

        total_hypotheses = 0
        total_episodes = 0
        feeds_errored = 0

        for feed_info in PODCAST_FEEDS:
            try:
                episodes = await self._fetch_feed_episodes(feed_info)
                if not episodes:
                    continue

                # Filter to recent episodes (last 7 days)
                cutoff = now - timedelta(days=7)
                recent = [
                    ep for ep in episodes
                    if ep.get("published") is None or ep["published"] >= cutoff
                ]

                if not recent:
                    logger.debug(
                        f"{self.name}: {feed_info['name']} -- no recent episodes"
                    )
                    continue

                # Check each episode for trading content
                hypotheses_from_feed = 0
                for episode in recent[:5]:  # max 5 episodes per feed
                    ep_guid = episode.get("guid") or episode.get("link", "")
                    if not ep_guid or ep_guid in self._seen_episodes:
                        continue
                    self._seen_episodes[ep_guid] = now
                    total_episodes += 1

                    try:
                        hypothesis = await self._analyze_episode(episode, feed_info)
                        if hypothesis:
                            await self._save_signal(hypothesis, episode, feed_info)
                            hypotheses_from_feed += 1
                            total_hypotheses += 1
                    except Exception as e:
                        logger.debug(
                            f"{self.name}: skip episode {ep_guid[:30]}: {e}"
                        )

                logger.info(
                    f"{self.name}: {feed_info['name']} -- "
                    f"{hypotheses_from_feed}/{len(recent)} hypotheses"
                )

            except Exception as e:
                logger.warning(
                    f"{self.name}: feed '{feed_info['name']}' error: {e}"
                )
                feeds_errored += 1

        # Prune cache if it exceeds limit
        if len(self._seen_episodes) > self._max_seen:
            self._prune_seen_episodes(datetime.now(timezone.utc))

        logger.info(
            f"{self.name}: cycle complete -- {total_hypotheses} hypotheses "
            f"from {total_episodes} episodes across "
            f"{len(PODCAST_FEEDS) - feeds_errored}/{len(PODCAST_FEEDS)} feeds"
        )

    # ------------------------------------------------------------------
    # RSS feed fetching
    # ------------------------------------------------------------------

    async def _fetch_feed_episodes(
        self, feed_info: dict
    ) -> list[dict[str, Any]]:
        """Fetch and parse a podcast RSS feed asynchronously."""
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                # Use requests for better SSL handling on Windows
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                }
                resp = requests.get(
                    feed_info["url"],
                    headers=headers,
                    timeout=self.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                raw_xml = resp.text
                parsed = feedparser.parse(raw_xml)
                return parsed
            except Exception as e:
                logger.debug(
                    f"{self.name}: HTTP fetch failed for {feed_info['name']}: {e}"
                )
                return None

        try:
            parsed = await loop.run_in_executor(None, _fetch)
        except Exception as e:
            logger.warning(f"{self.name}: executor error for {feed_info['name']}: {e}")
            return []

        if parsed is None or not parsed.entries:
            logger.debug(f"{self.name}: {feed_info['name']} -- no entries found")
            return []

        episodes = []
        for entry in parsed.entries[:10]:  # max 10 per feed per cycle
            # Extract description (may be in summary, description, or content)
            description = ""
            if hasattr(entry, "summary") and entry.summary:
                description = self._clean_html(entry.summary)[:500]
            elif hasattr(entry, "description") and entry.description:
                description = self._clean_html(entry.description)[:500]
            elif hasattr(entry, "content") and entry.content:
                description = self._clean_html(entry.content[0].value)[:500]

            title = getattr(entry, "title", "")
            if not title:
                continue

            # Published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass

            # GUID or link for dedup
            guid = getattr(entry, "id", None) or getattr(entry, "link", "")
            link = getattr(entry, "link", "")

            # Pre-filter: check for trading content in title/description
            combined = f"{title} {description}"
            if not self._has_trading_content(combined):
                continue

            episodes.append({
                "title": title,
                "description": description,
                "link": link,
                "guid": guid,
                "published": published,
                "feed_name": feed_info["name"],
                "feed_weight": feed_info["weight"],
            })

        return episodes

    @staticmethod
    def _clean_html(raw: str) -> str:
        """Strip HTML tags from text."""
        cleaned = re.sub(r"<[^>]+>", " ", raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # ------------------------------------------------------------------
    # Episode analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _has_trading_content(text: str) -> bool:
        """Pre-filter: check if episode content contains trading/finance keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in TRADING_KEYWORDS)

    @staticmethod
    def _extract_tickers(text: str) -> list[str]:
        """Extract potential ticker symbols from text."""
        matches = TICKER_PATTERN.findall(text)
        tickers = set()
        for match in matches:
            if match not in FALSE_TICKERS:
                tickers.add(match)
        return list(tickers)[:5]

    async def _analyze_episode(
        self, episode: dict, feed_info: dict
    ) -> dict | None:
        """Use Claude to extract a trading hypothesis from episode metadata."""
        title = episode.get("title", "")
        description = episode.get("description", "")
        feed_name = feed_info["name"]

        user_prompt = (
            f"Podcast: {feed_name}\n"
            f"Episode title: {title}\n"
            f"Description: {description[:600]}\n\n"
            "Extract any trading strategy signal or market insight from this episode."
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
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _prune_seen_episodes(self, now: datetime):
        """Remove expired entries from the seen-episode cache."""
        expired = [
            g for g, ts in self._seen_episodes.items()
            if now - ts > self._cache_ttl
        ]
        for g in expired:
            del self._seen_episodes[g]

        if len(self._seen_episodes) > self._max_seen:
            sorted_by_age = sorted(
                self._seen_episodes.items(),
                key=lambda x: x[1],
            )
            to_remove = len(self._seen_episodes) - self._max_seen
            for g, _ in sorted_by_age[:to_remove]:
                del self._seen_episodes[g]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_signal(
        self,
        hypothesis: dict,
        episode: dict,
        feed_info: dict,
    ) -> None:
        """
        Persist to external_scout_memory.
        Auto-mirrors to scout_signals via _SCOUT_TABLE_MIRROR_MAP.
        """
        ticker = hypothesis.get("ticker") or "unknown"
        strategy_type = hypothesis.get("strategy_type", "other")
        confidence = float(hypothesis.get("confidence", 0.5))
        direction = hypothesis.get("direction", "neutral")
        hypothesis_text = hypothesis.get("hypothesis", "")

        if not self.db:
            logger.warning(f"{self.name}: no DB client, can't persist")
            return

        # Compute sentiment from direction
        sentiment = 0.3 if direction == "bullish" else (
            -0.3 if direction == "bearish" else 0.0
        )
        sentiment = round(sentiment * confidence, 4)
        signal_dir = (
            "bullish" if sentiment > 0.15
            else "bearish" if sentiment < -0.15
            else "neutral"
        )

        # Build mentioned tickers list
        tickers_list = [{"ticker": ticker, "sentiment": sentiment}]

        episode_title = episode.get("title", "")
        feed_name = feed_info["name"]
        episode_link = episode.get("link", "")

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
                    "source": "podcast",
                    "source_sub": feed_name,
                    "reliability": feed_info["weight"],
                    "sentiment": sentiment,
                    "tickers": safe_json_dumps(tickers_list),
                    "score": round(confidence, 4),
                    "direction": signal_dir,
                    "metadata": safe_json_dumps({
                        "hypothesis": hypothesis_text,
                        "strategy_type": strategy_type,
                        "timeframe": hypothesis.get("timeframe"),
                        "feed": feed_name,
                        "episode_title": episode_title,
                        "episode_link": episode_link,
                        "episode_published": (
                            episode["published"].isoformat()
                            if episode.get("published")
                            else ""
                        ),
                        "raw_confidence": confidence,
                    }),
                },
            )

            logger.info(
                f"{self.name}: saved {strategy_type} signal "
                f"({ticker}) confidence={confidence:.2f} "
                f"from '{feed_name}: {episode_title[:50]}'"
            )

        except Exception as e:
            logger.error(f"{self.name}: save failed: {e}")
