"""P6 T1 — single authority flag accessor for the metrics→fitness→validator→governor
stack cutover (see scratch/P5_CUTOVER_DESIGN.md, scratch/P6_IMPLEMENTATION_PLAN.md §1.1).

ONE flag, three states, read by all four consumers:
    ATLAS_STACK_VERSION ∈ { legacy , shadow , canonical }

  legacy    — old columns + old gates have authority (DEFAULT). v1 write path off.
  shadow    — v1 write path on; v1 validator/governor compute decisions but ACT ON NOTHING.
  canonical — v1 columns + P3/P4 policy have authority.

This module is PURE — no DB access — so atlas/core carries no storage dependency.
Source of truth for T1 is the ATLAS_STACK_VERSION env var (mirrored by the
settings field), default 'legacy'. The DB-backed hot-reload path (system_config
table, created additively in migration_004_system_config.sql) is wired in later
when the consumers actually branch; until then the default guarantees ZERO
production behavior change.
"""
from __future__ import annotations

import os
from enum import Enum


class StackVersion(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


VALID: frozenset[str] = frozenset(v.value for v in StackVersion)
DEFAULT: str = StackVersion.LEGACY.value


def _raw() -> str | None:
    """Resolve the configured value: env override first (break-glass), then the
    settings field, then None. Never raises."""
    val = os.environ.get("ATLAS_STACK_VERSION")
    if val is not None:
        return val
    try:  # settings import kept lazy + guarded so this module stays import-safe
        from atlas.config.settings import settings

        return getattr(settings, "stack_version", None)
    except Exception:
        return None


def get_stack_version() -> str:
    """Return the active stack version, always one of VALID. Unknown/empty → 'legacy'."""
    val = (_raw() or DEFAULT).strip().lower()
    return val if val in VALID else DEFAULT


def is_legacy() -> bool:
    return get_stack_version() == StackVersion.LEGACY.value


def is_shadow() -> bool:
    return get_stack_version() == StackVersion.SHADOW.value


def is_canonical() -> bool:
    return get_stack_version() == StackVersion.CANONICAL.value
