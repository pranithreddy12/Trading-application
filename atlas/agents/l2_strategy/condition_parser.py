"""
Condition Parser — structured condition AST for mutation precision.

Transforms raw condition strings like:
    "trend_strength > 0.002"
    "rsi_14 < 30"
    "macd > macd_signal"

Into structured objects:
    {"feature": "trend_strength", "operator": ">", "value": 0.002}
    {"feature": "macd", "operator": ">", "value": None, "right_feature": "macd_signal"}

This replaces fragile regex mutation with precise AST manipulation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Feature registry (shared with strategy_normalizer.py)
KNOWN_FEATURES = {
    "returns",
    "log_returns",
    "rsi_14",
    "macd",
    "macd_signal",
    "sma_5",
    "sma_20",
    "ema_12",
    "ema_26",
    "vwap",
    "bollinger_upper",
    "bollinger_lower",
    "rolling_volatility",
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
    "close",
    "open",
    "high",
    "low",
    "volume",
}

OPERATORS = [">=", "<=", "!=", "==", ">", "<"]

# Longest-first so >= matches before >
_OP_PATTERN = re.compile(
    r"\s*("
    + "|".join(re.escape(op) for op in sorted(OPERATORS, key=len, reverse=True))
    + r")\s*"
)


@dataclass
class ParsedCondition:
    feature: str
    operator: str
    value: Optional[float] = None
    right_feature: Optional[str] = None
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "operator": self.operator,
            "value": self.value,
            "right_feature": self.right_feature,
        }

    def serialize(self) -> str:
        if self.right_feature:
            return f"{self.feature} {self.operator} {self.right_feature}"
        val_str = (
            f"{self.value:.6f}".rstrip("0").rstrip(".")
            if self.value is not None
            else ""
        )
        return f"{self.feature} {self.operator} {val_str}"


def parse_condition(expr: str) -> Optional[ParsedCondition]:
    """Parse a condition string into a structured AST node."""
    expr = expr.strip()
    if not expr:
        return None

    parts = _OP_PATTERN.split(expr, maxsplit=1)
    if len(parts) != 3:
        return None

    left = parts[0].strip()
    operator = parts[1].strip()
    right = parts[2].strip()

    if not left or not operator or not right:
        return None

    # Extract feature name from left side (may be wrapped in df['...'] or just a bare name)
    feature = _extract_feature_name(left)
    if not feature or feature not in KNOWN_FEATURES:
        return None

    # Right side: numeric value or feature name
    right_feature = _extract_feature_name(right)
    if right_feature and right_feature in KNOWN_FEATURES:
        return ParsedCondition(
            feature=feature,
            operator=operator,
            value=None,
            right_feature=right_feature,
            raw=expr,
        )

    # Try parsing as numeric value
    try:
        value = float(right)
        return ParsedCondition(
            feature=feature,
            operator=operator,
            value=value,
            right_feature=None,
            raw=expr,
        )
    except ValueError:
        return None


def _extract_feature_name(text: str) -> Optional[str]:
    """Extract a feature name from text, handling df['...'] wrappers."""
    text = text.strip()
    # Handle df['feature_name'] pattern
    m = re.match(r"df\s*\[\s*['\"](\w+)['\"]\s*\]", text)
    if m:
        return m.group(1)
    # Handle bare feature name
    m = re.match(r"^([a-zA-Z_]\w*)$", text)
    if m:
        return m.group(1)
    return None


def parse_conditions(conditions: list[str]) -> list[ParsedCondition]:
    """Parse a list of condition strings."""
    return [pc for pc in (parse_condition(c) for c in conditions) if pc is not None]


def mutate_threshold(parsed: ParsedCondition, factor: float) -> ParsedCondition:
    """Safely mutate a threshold value by a factor. Returns new ParsedCondition."""
    if parsed.value is None or parsed.right_feature is not None:
        return parsed
    new_value = parsed.value * factor
    return ParsedCondition(
        feature=parsed.feature,
        operator=parsed.operator,
        value=round(new_value, 6),
        right_feature=None,
        raw=parsed.raw,
    )


def flip_operator(parsed: ParsedCondition) -> ParsedCondition:
    """Flip comparison operator (e.g., > to <). Returns new ParsedCondition."""
    flipped = {">": "<", "<": ">", ">=": "<=", "<=": ">="}
    new_op = flipped.get(parsed.operator, parsed.operator)
    return ParsedCondition(
        feature=parsed.feature,
        operator=new_op,
        value=parsed.value,
        right_feature=parsed.right_feature,
        raw=parsed.raw,
    )


def condition_complexity(parsed: ParsedCondition) -> int:
    """Compute complexity score for a single condition."""
    score = 1
    if parsed.right_feature:
        score += 2
    return score


def spec_condition_stats(spec: dict) -> dict:
    """Extract structured condition stats from a strategy spec."""
    entry = parse_conditions(spec.get("entry_conditions", []))
    exit_ = parse_conditions(spec.get("exit_conditions", []))
    features_used = set(c.feature for c in entry + exit_)
    return {
        "total_conditions": len(entry) + len(exit_),
        "entry_count": len(entry),
        "exit_count": len(exit_),
        "features_used": sorted(features_used),
        "feature_diversity": len(features_used),
        "threshold_count": sum(1 for c in entry + exit_ if c.value is not None),
        "feature_comparison_count": sum(
            1 for c in entry + exit_ if c.right_feature is not None
        ),
    }
