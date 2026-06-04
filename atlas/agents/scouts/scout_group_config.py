"""
scout_group_config.py — Multi-Group Multi-Channel configuration for scouts.

Defines the ScoutGroup model that maps logical groups (e.g. "Dummy", "VIP")
to their Discord guild+channel whitelists and YouTube search queries.

Config is loaded from the SCOUT_GROUPS env var (JSON string).
If SCOUT_GROUPS is empty, a default "Dummy" group is built from the legacy
DISCORD_GUILD_IDS / YOUTUBE_API_KEY + hardcoded search queries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiscordChannelBinding:
    """A single guild + channel-list binding for a scout group."""

    guild_id: str
    channels: list[str] = field(default_factory=list)


@dataclass
class ScoutGroup:
    """
    Logical scout group with its own Discord channels and YouTube queries.

    ```
    {
      "name": "Dummy",
      "discord": [
        {"guild_id": "123456789", "channels": ["general", "trading-signals"]}
      ],
      "youtube": ["algorithmic trading strategy", "quant finance"]
    }
    ```
    """

    name: str
    discord: list[DiscordChannelBinding] = field(default_factory=list)
    youtube: list[str] = field(default_factory=list)


def parse_scout_groups(
    raw_json: str,
    fallback_guild_ids: str = "",
    fallback_youtube_queries: list[str] | None = None,
) -> list[ScoutGroup]:
    """
    Parse SCOUT_GROUPS JSON into a list of ScoutGroup.

    If raw_json is empty, builds a single default "Dummy" group from
    the legacy fallback values.
    """
    if not raw_json or not raw_json.strip():
        return _build_default_group(fallback_guild_ids, fallback_youtube_queries)

    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError:
        return _build_default_group(fallback_guild_ids, fallback_youtube_queries)

    if not isinstance(raw, list):
        raw = [raw]

    groups: list[ScoutGroup] = []
    for entry in raw:
        name = entry.get("name", "Unnamed")
        discord_bindings = []
        for d in entry.get("discord", []):
            discord_bindings.append(
                DiscordChannelBinding(
                    guild_id=str(d.get("guild_id", "")),
                    channels=[str(c) for c in d.get("channels", [])],
                )
            )
        youtube_queries = [str(q) for q in entry.get("youtube", [])]
        groups.append(
            ScoutGroup(
                name=name,
                discord=discord_bindings,
                youtube=youtube_queries,
            )
        )

    return groups


def _build_default_group(
    guild_ids: str,
    youtube_queries: list[str] | None,
) -> list[ScoutGroup]:
    """Build a single 'Dummy' group from legacy config values."""
    bindings: list[DiscordChannelBinding] = []
    for gid in [g.strip() for g in guild_ids.split(",") if g.strip()]:
        bindings.append(
            DiscordChannelBinding(
                guild_id=gid,
                channels=[],  # empty = all trading channels in guild
            )
        )

    queries = youtube_queries or []

    return [
        ScoutGroup(
            name="Dummy",
            discord=bindings,
            youtube=queries,
        )
    ]


def build_guild_channel_map(groups: list[ScoutGroup]) -> dict[str, set[str]]:
    """
    Build a flat {guild_id -> {allowed_channel_names}} map from all groups.

    Returns a dict where each guild_id maps to a set of allowed channel names.
    If the set is empty, ALL channels in that guild are allowed (broad listen).
    """
    guild_map: dict[str, set[str]] = {}
    for group in groups:
        for binding in group.discord:
            allowed = guild_map.setdefault(binding.guild_id, set())
            for ch in binding.channels:
                allowed.add(ch.lower())
    return guild_map


def resolve_groups_for_channel(
    groups: list[ScoutGroup],
    guild_id: str,
    channel_name: str,
) -> list[str]:
    """
    Return the names of all groups that include this guild+channel.

    If a binding has an empty channel list, all channels in that guild match.
    """
    matched: list[str] = []
    ch_lower = channel_name.lower()
    for group in groups:
        for binding in group.discord:
            if binding.guild_id == guild_id:
                if not binding.channels:
                    matched.append(group.name)
                elif ch_lower in [c.lower() for c in binding.channels]:
                    matched.append(group.name)
    return matched
