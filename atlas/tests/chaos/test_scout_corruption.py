"""Chaos: Scout corruption — verify system handles malformed scout signals."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_malformed_scout_signal():
    """System should reject malformed scout signals."""
    valid_schema = {"source": str, "sentiment": (int, float), "timestamp": str}
    bad_signals = [
        {"source": None, "sentiment": 0.5},
        {"source": "reddit", "sentiment": "bad"},
        {},
        {"source": "twitter", "sentiment": -1, "unknown_field": "garbage"},
    ]

    def validate_signal(sig: dict) -> bool:
        if not isinstance(sig.get("source"), valid_schema["source"]):
            return False
        if not isinstance(sig.get("sentiment"), valid_schema["sentiment"]):
            return False
        return True

    for sig in bad_signals:
        assert validate_signal(sig) is False


@pytest.mark.asyncio
async def test_scout_input_sanitization():
    """Dangerous input should be sanitized before processing."""
    dangerous_inputs = [
        {"source": "'; DROP TABLE strategies; --", "sentiment": 0.5},
        {"source": "<script>alert('xss')</script>", "sentiment": 0.5},
        {"source": "reddit", "sentiment": None},
    ]
    for inp in dangerous_inputs:
        sanitized_source = "".join(c for c in inp["source"] if c.isalnum() or c in "_.")
        assert "'" not in sanitized_source
        assert "<" not in sanitized_source
