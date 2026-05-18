from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class DefectType(str, Enum):
    SCHEMA_FAILURE = "schema_failure"
    AUTH_FAILURE = "auth_failure"
    SERIALIZATION_FAILURE = "serialization_failure"
    PERMISSION_FAILURE = "permission_failure"
    RATE_LIMIT_FAILURE = "rate_limit_failure"
    RESTART_FAILURE = "restart_failure"
    HEALTH_FAILURE = "health_failure"
    LATENCY_FAILURE = "latency_failure"
    AUDIT_FAILURE = "audit_failure"
    CONTRACT_FAILURE = "contract_failure"
    EVENT_LINEAGE_FAILURE = "event_lineage_failure"


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class Evidence:
    stage: str
    status: StageStatus
    defect: Optional[DefectType] = None
    message: str = ""
    detail: Any = None
    latency_ms: float = 0.0
    traceback_str: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        if self.defect:
            d["defect"] = self.defect.value
        return d


@dataclass
class StageResult:
    stage_name: str
    status: StageStatus
    defect: Optional[DefectType] = None
    evidence: list[Evidence] = field(default_factory=list)
    error: Optional[str] = None
    traceback_str: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "defect": self.defect.value if self.defect else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "error": self.error,
            "traceback": self.traceback_str,
            "latency_ms": self.latency_ms,
        }


@dataclass
class ValidationOutput:
    timestamp: str
    environment: str
    overall_status: StageStatus
    stages: dict[str, StageResult] = field(default_factory=dict)
    security_matrix: dict[str, dict[str, str]] = field(default_factory=dict)
    latency_report: dict[str, float] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "environment": self.environment,
            "trace_id": self.trace_id,
            "overall_status": self.overall_status.value,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "security_matrix": self.security_matrix,
            "latency_report": self.latency_report,
            "summary": self.summary,
        }

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8"
        )
