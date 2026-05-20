from __future__ import annotations

import json
from dataclasses import is_dataclass, asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


def normalize_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return normalize_json_value(asdict(value))
    if hasattr(value, "_mapping"):
        return normalize_json_value(dict(value._mapping))
    if isinstance(value, dict):
        return {str(k): normalize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json_value(v) for v in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return normalize_json_value(value.item())
        except Exception:
            pass
    return str(value)


def normalize_db_params(params: dict[str, Any] | None) -> dict[str, Any]:
    return {str(k): normalize_json_value(v) for k, v in (params or {}).items()}


def safe_json_dumps(value: Any) -> str:
    return json.dumps(normalize_json_value(value), ensure_ascii=False)
