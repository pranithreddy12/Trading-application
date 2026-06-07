"""
exit_policy.py — Single source of truth for strategy exit resolution.

Sprint 0 unifies the exit regime across the entire pipeline so that a
strategy is validated under the SAME exits it trades under:

    Ideator    — designs stop_loss_pct / take_profit_pct (PERCENT numbers)
                 and hold_time_max (bars) per archetype.
    Backtest   — resolves those params via this module and applies them in
                 the trade state machine (plus the signal/time-stop already
                 embedded in the generated code).
    Validation — consumes the backtest output, which now reflects the
                 designed exits (composite_fitness_score, trade list, MC).
    Execution  — the live MTM loop resolves the SAME params via this module
                 and applies identical SL / TP / time-stop logic.

CONVENTION (this is the bug Sprint 0 fixes):
  * ``stop_loss_pct`` / ``take_profit_pct`` in strategy params are
    PERCENT NUMBERS, e.g. ``0.3`` means 0.3%, ``1.5`` means 1.5%. This
    matches ``IdeatorAgentV2.ARCHETYPE_RISK_PROFILES`` and the
    ``strategy_normalizer`` defaults (2.0% / 5.0%).
  * Price math needs FRACTIONS (0.003, 0.015). This module performs the
    single, canonical ``percent / 100`` conversion so backtest and live
    can never disagree about units again.
  * ``hold_time_max`` is in BARS; on the live 1-minute feed 1 bar == 1
    minute, so the live time-stop compares elapsed minutes to it.

Before Sprint 0:
  * Backtest read ``getattr(strategy, "stop_loss_pct", 0.0)`` — the
    generated class never set it, so SL/TP were silently DISABLED, and the
    inline math treated the percent number as a fraction (a "2.0 stop"
    would have meant -200%).
  * Live execution used a hardcoded ``-5% / +10%`` bracket that ignored
    the strategy entirely and had no time-stop.

Keep this module dependency-free (stdlib only) so both L3 and L5 can import
it without creating cycles.
"""

from __future__ import annotations

import json

# Defaults mirror strategy_normalizer.py so a param-less strategy behaves
# identically here and there.
DEFAULT_STOP_LOSS_PCT: float = 2.0   # percent number (2.0 == 2%)
DEFAULT_TAKE_PROFIT_PCT: float = 5.0  # percent number (5.0 == 5%)
DEFAULT_HOLD_TIME_MAX: int = 40       # bars (== minutes on the 1m feed)

# Sane clamps on the resulting fractions / bars.
_MIN_FRAC: float = 0.0005   # 0.05% — anything tighter is noise
_MAX_SL_FRAC: float = 0.50  # 50% — guard against absurd params
_MAX_TP_FRAC: float = 1.00  # 100%
_MIN_HOLD: int = 1
_MAX_HOLD: int = 1000


def _coerce_float(value, default: float) -> float:
    """Best-effort float coercion; returns ``default`` on None/garbage."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_exit_policy(params) -> dict:
    """Resolve a strategy's parameters into a canonical exit policy.

    Accepts the strategy ``parameters`` payload as a dict or JSON string.
    Returns a dict with both the raw percents (for logging/audit) and the
    fractions used by price math::

        {
          "stop_loss_pct":    float,  # percent number, as designed
          "take_profit_pct":  float,
          "stop_loss_frac":   float,  # fraction for price math (pct / 100)
          "take_profit_frac": float,
          "hold_time_max":    int,    # bars / minutes
        }

    A ``*_pct`` of 0 (or negative) disables that leg (frac == 0.0).
    """
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    if not isinstance(params, dict):
        params = {}

    sl_pct = _coerce_float(params.get("stop_loss_pct"), DEFAULT_STOP_LOSS_PCT)
    tp_pct = _coerce_float(params.get("take_profit_pct"), DEFAULT_TAKE_PROFIT_PCT)
    hold_max = _coerce_float(params.get("hold_time_max"), DEFAULT_HOLD_TIME_MAX)

    # The single canonical percent -> fraction conversion.
    sl_frac = sl_pct / 100.0
    tp_frac = tp_pct / 100.0

    # Clamp; a non-positive leg stays disabled (0.0) rather than snapping up.
    sl_frac = min(max(sl_frac, _MIN_FRAC), _MAX_SL_FRAC) if sl_frac > 0 else 0.0
    tp_frac = min(max(tp_frac, _MIN_FRAC), _MAX_TP_FRAC) if tp_frac > 0 else 0.0
    hold_max = int(min(max(hold_max, _MIN_HOLD), _MAX_HOLD))

    return {
        "stop_loss_pct": sl_pct,
        "take_profit_pct": tp_pct,
        "stop_loss_frac": sl_frac,
        "take_profit_frac": tp_frac,
        "hold_time_max": hold_max,
    }


def check_price_exit(
    side: str,
    entry_price: float,
    current_price: float,
    stop_loss_frac: float,
    take_profit_frac: float,
) -> tuple[bool, str | None]:
    """Canonical stop-loss / take-profit check.

    This is the ONE implementation of the price-exit decision. The backtest
    state machine and the live MTM loop both route through it so they can
    never diverge.

    ``side`` accepts ``buy``/``long`` or ``sell``/``short``. Returns
    ``(triggered, reason)`` where ``reason`` is ``"stop_loss"`` or
    ``"take_profit"`` (stop-loss takes precedence, matching the backtest).

    The thresholds use the multiplicative form ``entry * (1 ± frac)`` — the
    EXACT formulation in backtest_runner's state machine — so backtest and
    live agree bit-for-bit even at the trigger price (the equivalent
    ``pct_move`` form can differ by one float ULP at the boundary).
    """
    if not entry_price or entry_price <= 0:
        return False, None

    s = str(side).lower()
    if s in ("buy", "long"):
        sl_hit = stop_loss_frac > 0 and current_price <= entry_price * (1.0 - stop_loss_frac)
        tp_hit = take_profit_frac > 0 and current_price >= entry_price * (1.0 + take_profit_frac)
    else:  # sell / short
        sl_hit = stop_loss_frac > 0 and current_price >= entry_price * (1.0 + stop_loss_frac)
        tp_hit = take_profit_frac > 0 and current_price <= entry_price * (1.0 - take_profit_frac)

    # Stop-loss precedence mirrors backtest_runner's state machine.
    if sl_hit:
        return True, "stop_loss"
    if tp_hit:
        return True, "take_profit"
    return False, None


def check_time_exit(held: float, hold_time_max: int) -> bool:
    """Time-stop check. ``held`` is bars (backtest) or minutes (live, 1m feed).

    Returns True once a position has been open at least ``hold_time_max``.
    A non-positive ``hold_time_max`` disables the time-stop.
    """
    if not hold_time_max or hold_time_max <= 0:
        return False
    return held >= hold_time_max
