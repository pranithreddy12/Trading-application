"""
discord_scout.py — Real-time Discord self-bot (discord.py-self) implementation.

Replaces the old REST API v10 polling implementation with a real-time
WebSocket gateway connection via discord.py-self.

Connects using a **user account token** (self-bot), listens for messages
in configured guilds/channels via the on_message event, extracts trading
hypotheses via Claude, and persists to external_scout_memory.

Requires: DISCORD_USER_TOKEN and DISCORD_GUILD_IDS in .env / settings.

⚠ WARNING: Self-botting violates Discord's Terms of Service. Use at your
   own risk. This is intentionally scoped for the ATLAS scout network
   where bot accounts are not feasible.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import discord
from loguru import logger

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.serialization import safe_json_dumps
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from atlas.agents.scouts.scout_group_config import (
    ScoutGroup,
    parse_scout_groups,
    build_guild_channel_map,
    resolve_groups_for_channel,
)


# Keywords suggesting a message might contain a trading signal
TRADING_KEYWORDS = [
    "buy",
    "sell",
    "short",
    "long",
    "call",
    "put",
    "breakout",
    "rally",
    "crash",
    "dump",
    "pump",
    "entry",
    "exit",
    "stop",
    "target",
    "support",
    "resistance",
    "trend",
    "momentum",
    "divergence",
    "pattern",
    "signal",
    "alert",
    "setup",
    "position",
    "trade",
    "bullish",
    "bearish",
    "moon",
    "liquidation",
    "squeeze",
    "break",
    "retest",
    "ATH",
    "accumulate",
    "distribution",
    "volume",
    "orderflow",
]

# Regex to find potential ticker symbols ($AAPL, BTC, ETH, etc.)
TICKER_PATTERN = re.compile(
    r"\$([A-Z]{2,6})\b"  # $TICKER
    r"|(?<![A-Z])([A-Z]{3,5})(?![A-Z])"  # standalone TICKER (3-5 uppercase)
)

# Common false-positive words that look like tickers
FALSE_TICKERS = {
    "THE",
    "AND",
    "FOR",
    "BUT",
    "HAS",
    "ARE",
    "NEW",
    "NOW",
    "NOT",
    "YOU",
    "ALL",
    "CAN",
    "WAS",
    "OUT",
    "ONE",
    "GET",
    "ITS",
    "DID",
    "SAY",
    "WAY",
    "USE",
    "MAY",
    "SEE",
    "HOW",
    "LOW",
    "HIGH",
    "BIG",
    "TOP",
    "END",
    "LET",
    "TRY",
    "BULL",
    "BEAR",
    "MOON",
    "FOMO",
    "HODL",
    "DCA",
    "ATH",
}

HYPOTHESIS_SYSTEM = """You are a quantitative analyst extracting trading hypotheses from Discord messages.
Given a Discord message, extract any trading strategy signal or idea.
If no clear trading signal exists, return null.
If a signal exists, return JSON only:
{
  "hypothesis": "one sentence signal description",
  "ticker": "symbol or null",
  "timeframe": "intraday/swing/position/unknown",
  "strategy_type": "momentum/mean_reversion/breakout/sentiment/other",
  "confidence": 0.0-1.0,
  "direction": "bullish/bearish/neutral"
}"""


class DiscordScout(BaseAgent):
    """
    Real-time Discord self-bot scout using discord.py-self.

    Connects to Discord via the real-time WebSocket gateway, listens for
    messages in configured guilds/channels, pre-filters for trading keywords,
    extracts hypotheses via Claude, and persists to external_scout_memory.

    Uses a user account token (self-bot) instead of a Bot token.
    """

    name = "DiscordScout"
    agent_type = "external_scout"
    layer = "L7"

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
        self._user_token = getattr(settings, "discord_user_token", "") or ""

        # ── Scout group configuration ─────────────────────────────────
        raw_guilds = getattr(settings, "discord_guild_ids", "") or ""
        raw_scout_groups = getattr(settings, "scout_groups", "") or ""
        self._groups: list[ScoutGroup] = (
            groups
            if groups is not None
            else parse_scout_groups(raw_scout_groups, fallback_guild_ids=raw_guilds)
        )
        # Flat {guild_id -> {allowed_channel_names}} for fast lookup
        self._guild_channel_map: dict[str, set[str]] = build_guild_channel_map(
            self._groups
        )
        # Keep set of all guild IDs for backward-compat checks
        self._guild_ids: set[str] = set(self._guild_channel_map.keys())

        # run_interval retained for interface backward-compatibility
        # (the new architecture is real-time via gateway, not polling)
        # Queue-based rate limiter: single consumer processes messages
        # at a controlled rate instead of spawning many delayed tasks
        self._analysis_queue: asyncio.Queue[discord.Message] = asyncio.Queue(
            maxsize=200
        )
        self._min_analysis_interval: float = 2.0  # seconds between Claude calls
        self._queue_consumer_task: asyncio.Task | None = None

        # Message dedup cache: message_id -> datetime seen
        self._seen_messages: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=2)
        self._max_seen = 5000

        # Track whether we've had a successful gateway connection
        self._gateway_connected = asyncio.Event()

        # discord.py-self client — real-time WebSocket gateway
        # Note: discord.py-self 2.1.0 does NOT have Intents class.
        # Self-bot accounts handle message content and events automatically.
        self._client = discord.Client()

        # Register event handlers via closures with correct event names.
        # client.event() uses the function's __name__ to setattr() on the
        # client. The dispatch system looks for 'on_ready' and 'on_message'.
        # Using closures avoids bound-method __name__ issues.
        async def on_ready():
            await self._on_ready()

        async def on_message(message: discord.Message):
            await self._on_message(message)

        self._client.event(on_ready)
        self._client.event(on_message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self):
        """Connect to Discord gateway and stream messages in real-time."""
        if not self._user_token:
            logger.warning(f"{self.name}: DISCORD_USER_TOKEN not set — scout disabled")
            while self.status == "running":
                await asyncio.sleep(3600)
            return

        if not self._guild_ids:
            logger.warning(f"{self.name}: DISCORD_GUILD_IDS not set — scout disabled")
            while self.status == "running":
                await asyncio.sleep(3600)
            return

        logger.info(
            f"{self.name}: starting — real-time WebSocket gateway, "
            f"{len(self._guild_ids)} guild(s) monitored"
        )

        # Start the queue consumer for rate-limited Claude analysis
        self._queue_consumer_task = asyncio.create_task(self._analysis_consumer())

        # Start the Discord gateway connection (blocking until disconnect)
        # Note: start() manages login + connect lifecycle internally.
        # stop() calls client.close() which triggers clean disconnect.
        await self._client.start(self._user_token)

    async def stop(self):
        """Close the gateway connection and stop the agent."""
        # Cancel the queue consumer first
        if self._queue_consumer_task and not self._queue_consumer_task.done():
            self._queue_consumer_task.cancel()
            try:
                await self._queue_consumer_task
            except asyncio.CancelledError:
                pass
            self._queue_consumer_task = None

        # Close the Discord gateway connection
        try:
            if self._client and not self._client.is_closed():
                await self._client.close()
        except Exception as e:
            logger.debug(f"{self.name}: close error (expected during shutdown): {e}")
        await super().stop()

    # ------------------------------------------------------------------
    # Discord gateway event handlers
    # ------------------------------------------------------------------

    async def _on_ready(self):
        """Fired when the gateway connection is established and ready."""
        logger.info(
            f"{self.name}: logged in as {self._client.user} "
            f"(ID: {self._client.user.id})"
        )
        connected_guilds = set()
        for g in self._client.guilds:
            if str(g.id) in self._guild_ids:
                connected_guilds.add(g.id)
                allowed = self._guild_channel_map.get(str(g.id))
                if allowed:
                    logger.info(
                        f"{self.name}: monitoring guild '{g.name}' ({g.id}) "
                        f"— allowed channels: {sorted(allowed)}"
                    )
                else:
                    logger.info(
                        f"{self.name}: monitoring guild '{g.name}' ({g.id}) "
                        f"— all text channels (no channel filter)"
                    )

        if not connected_guilds:
            logger.warning(
                f"{self.name}: account not in any configured guild. "
                f"Joined guilds: {[g.name for g in self._client.guilds]}"
            )
        else:
            logger.info(
                f"{self.name}: monitoring {len(connected_guilds)}/"
                f"{len(self._client.guilds)} configured guilds "
                f"across {len(self._groups)} group(s): "
                f"{[g.name for g in self._groups]}"
            )

        self._gateway_connected.set()

    async def _on_message(self, message: discord.Message):
        """Fired on every new message in any accessible channel."""
        # ── Skip own messages ──
        if message.author == self._client.user:
            return

        # ── Skip non-guild messages (DMs, group chats) ──
        if not message.guild:
            return

        # ── Guild whitelist ──
        guild_id = str(message.guild.id)
        if guild_id not in self._guild_ids:
            return

        # ── Channel whitelist (per-group) ──
        channel_name = getattr(message.channel, "name", "") or ""
        allowed_channels = self._guild_channel_map.get(guild_id)

        # If allowed_channels is empty (no channel filter), accept all.
        # Otherwise only accept messages from whitelisted channels.
        if allowed_channels is not None and allowed_channels:
            if channel_name.lower() not in allowed_channels:
                return

        # Resolve which groups this channel belongs to
        matched_groups = resolve_groups_for_channel(
            self._groups, guild_id, channel_name
        )

        # ── Message dedup ──
        msg_id = str(message.id)
        if msg_id in self._seen_messages:
            return
        self._seen_messages[msg_id] = datetime.now(timezone.utc)
        # Prune if cache exceeds limit
        if len(self._seen_messages) > self._max_seen:
            self._prune_seen_messages()

        # ── Pre-filter: check for trading content (fast path) ──
        content = message.content or ""
        if not content:
            return

        has_keywords = self._has_trading_content(content)
        has_tickers = bool(self._extract_tickers(content))
        if not has_keywords and not has_tickers:
            return

        # ── Queue for rate-limited Claude analysis ──
        try:
            self._analysis_queue.put_nowait((message, matched_groups))
        except asyncio.QueueFull:
            logger.debug(
                f"{self.name}: analysis queue full, dropping message {message.id}"
            )

    # ------------------------------------------------------------------
    # Queue consumer — single-throttled analysis pipeline
    # ------------------------------------------------------------------

    async def _analysis_consumer(self):
        """
        Single consumer that processes queued messages at a controlled rate.
        Prevents overwhelming Claude during high-volume Discord activity.
        """
        try:
            while self.status == "running":
                message, matched_groups = await self._analysis_queue.get()
                channel_name = getattr(message.channel, "name", "") or ""
                await self._analyze_and_save(message, channel_name, matched_groups)
                # Rate-limit: wait between analyses
                await asyncio.sleep(self._min_analysis_interval)
        except asyncio.CancelledError:
            logger.debug(f"{self.name}: analysis consumer cancelled")

    # ------------------------------------------------------------------
    # Message analysis
    # ------------------------------------------------------------------

    async def _analyze_and_save(
        self,
        message: discord.Message,
        channel_name: str,
        matched_groups: list[str] | None = None,
    ):
        """Run Claude analysis and persist if a hypothesis is found."""
        try:
            hypothesis = await self._analyze_message(message, channel_name)
            if hypothesis:
                await self._save_signal(
                    hypothesis, message, channel_name, matched_groups
                )
        except Exception as e:
            logger.debug(f"{self.name}: analysis error: {e}")

    async def _analyze_message(
        self, message: discord.Message, channel_name: str
    ) -> dict | None:
        """
        Analyze a single Discord message for trading signals via Claude.
        """
        content = message.content
        if not content:
            return None

        author_name = str(message.author)
        timestamp = message.created_at.isoformat()

        user_prompt = (
            f"Discord message from user '{author_name}' "
            f"in channel '#{channel_name}':\n"
            f"Timestamp: {timestamp}\n"
            f"Content: {content[:800]}\n\n"
            "Extract any trading strategy signal or hypothesis from this message."
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

    @staticmethod
    def _is_trading_channel(channel_name: str) -> bool:
        """Check if a channel name looks trading-relevant."""
        name_lower = channel_name.lower()
        trading_indicators = [
            "trade",
            "signal",
            "call",
            "alert",
            "entry",
            "analysis",
            "chart",
            "discussion",
            "general",
            "market",
            "crypto",
            "stock",
            "option",
            "futures",
            "ideas",
            "strategy",
            "breakout",
            "momentum",
            "flow",
            "order",
            "technical",
        ]
        return any(ind in name_lower for ind in trading_indicators)

    @staticmethod
    def _has_trading_content(text: str) -> bool:
        """Pre-filter: check if message contains potential trading signal keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in TRADING_KEYWORDS)

    @staticmethod
    def _extract_tickers(text: str) -> list[str]:
        """Extract potential ticker symbols from message text."""
        matches = TICKER_PATTERN.findall(text)
        tickers = set()
        for dollar_match, bare_match in matches:
            if dollar_match:
                tickers.add(dollar_match)
            elif bare_match and bare_match not in FALSE_TICKERS:
                tickers.add(bare_match)
        return list(tickers)[:5]

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _prune_seen_messages(self):
        """Remove expired entries from the seen-message cache."""
        now = datetime.now(timezone.utc)
        expired = [
            mid for mid, ts in self._seen_messages.items() if now - ts > self._cache_ttl
        ]
        for mid in expired:
            del self._seen_messages[mid]
        # If still over limit, trim oldest entries
        if len(self._seen_messages) > self._max_seen:
            sorted_by_age = sorted(
                self._seen_messages.items(),
                key=lambda x: x[1],
            )
            to_remove = len(self._seen_messages) - self._max_seen
            for mid, _ in sorted_by_age[:to_remove]:
                del self._seen_messages[mid]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_signal(
        self,
        hypothesis: dict,
        message: discord.Message,
        channel_name: str,
        matched_groups: list[str] | None = None,
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
        sentiment = (
            0.3 if direction == "bullish" else (-0.3 if direction == "bearish" else 0.0)
        )
        # Boost by confidence
        sentiment = round(sentiment * confidence, 4)
        signal_dir = (
            "bullish"
            if sentiment > 0.15
            else "bearish"
            if sentiment < -0.15
            else "neutral"
        )

        # Build mentioned tickers list
        tickers_list = [{"ticker": ticker, "sentiment": sentiment}]

        # Helper to build a guild label from the guild_id
        guild_label = f"guild_{str(message.guild.id)[:8]}" if message.guild else "dm"

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
                    "source": "discord",
                    "source_sub": f"{guild_label}/{channel_name}",
                    "reliability": 0.5,  # base reliability for Discord
                    "sentiment": sentiment,
                    "tickers": safe_json_dumps(tickers_list),
                    "score": round(confidence, 4),
                    "direction": signal_dir,
                    "metadata": safe_json_dumps(
                        {
                            "hypothesis": hypothesis_text,
                            "strategy_type": strategy_type,
                            "timeframe": hypothesis.get("timeframe"),
                            "channel": channel_name,
                            "guild_id": str(message.guild.id) if message.guild else "",
                            "guild_name": message.guild.name if message.guild else "",
                            "author": str(message.author),
                            "author_id": str(message.author.id),
                            "message_id": str(message.id),
                            "message_timestamp": message.created_at.isoformat(),
                            "raw_confidence": confidence,
                            "gateway": "real_time",
                            "groups": matched_groups or [],
                        }
                    ),
                },
            )

            logger.info(
                f"{self.name}: saved {strategy_type} signal "
                f"({ticker}) confidence={confidence:.2f} "
                f"from #{channel_name}"
            )

        except Exception as e:
            logger.error(f"{self.name}: save failed: {e}")
