from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, Dict


class ViolationSeverity(IntEnum):
    INFO = 1
    WARNING = 2
    CRITICAL = 3
    FATAL = 4
    SYSTEMIC = 5


class GovernanceDecision(Enum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    REPAIR = "REPAIR"
    HALT_RUNTIME = "HALT_RUNTIME"


def severity_from_violation(violation: Dict[str, Any]) -> ViolationSeverity:
    # Deterministic extraction of severity from violation payload.
    sev = violation.get("severity")
    if isinstance(sev, ViolationSeverity):
        return sev
    if isinstance(sev, int):
        # clamp into enum
        if sev >= ViolationSeverity.SYSTEMIC:
            return ViolationSeverity.SYSTEMIC
        if sev >= ViolationSeverity.FATAL:
            return ViolationSeverity.FATAL
        if sev >= ViolationSeverity.CRITICAL:
            return ViolationSeverity.CRITICAL
        if sev >= ViolationSeverity.WARNING:
            return ViolationSeverity.WARNING
        return ViolationSeverity.INFO

    # fallback to flags
    if violation.get("systemic"):
        return ViolationSeverity.SYSTEMIC
    if violation.get("fatal"):
        return ViolationSeverity.FATAL
    if violation.get("critical"):
        return ViolationSeverity.CRITICAL
    if violation.get("warning"):
        return ViolationSeverity.WARNING
    return ViolationSeverity.INFO
