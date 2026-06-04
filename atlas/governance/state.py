from __future__ import annotations

from enum import Enum


class GovernanceEventState(Enum):
    OBSERVED = "OBSERVED"
    VALIDATED = "VALIDATED"
    REPAIRED = "REPAIRED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    REPLAY_PENDING = "REPLAY_PENDING"
    REPLAY_VERIFIED = "REPLAY_VERIFIED"
    DIVERGED = "DIVERGED"
    ESCALATED = "ESCALATED"



class InvalidGovernanceTransition(Exception):
    pass


# Deterministic allowed transitions
ALLOWED_TRANSITIONS = {
    GovernanceEventState.OBSERVED: {GovernanceEventState.VALIDATED, GovernanceEventState.REJECTED, GovernanceEventState.QUARANTINED, GovernanceEventState.REPAIRED},
    GovernanceEventState.VALIDATED: {GovernanceEventState.REPAIRED, GovernanceEventState.REPLAY_PENDING, GovernanceEventState.ESCALATED},
    GovernanceEventState.REPAIRED: {GovernanceEventState.VALIDATED, GovernanceEventState.REPLAY_PENDING},
    GovernanceEventState.REPLAY_PENDING: {GovernanceEventState.REPLAY_VERIFIED, GovernanceEventState.DIVERGED},
    GovernanceEventState.DIVERGED: {GovernanceEventState.ESCALATED, GovernanceEventState.QUARANTINED},
    GovernanceEventState.QUARANTINED: {GovernanceEventState.ESCALATED},
    GovernanceEventState.REJECTED: set(),
    GovernanceEventState.REPLAY_VERIFIED: {GovernanceEventState.VALIDATED},
    GovernanceEventState.ESCALATED: {GovernanceEventState.QUARANTINED},
}


def validate_transition(fr: GovernanceEventState | None, to: GovernanceEventState) -> bool:
    """Validate a transition from `fr` to `to`.

    - If `fr` is None, only allow transition to OBSERVED.
    - Raises InvalidGovernanceTransition on illegal transitions.
    Returns True if valid.
    """
    if fr is None:
        if to is GovernanceEventState.OBSERVED:
            return True
        raise InvalidGovernanceTransition(f"Initial transition to {to} is not allowed; must start at OBSERVED")

    allowed = ALLOWED_TRANSITIONS.get(fr, set())
    if to in allowed:
        return True
    raise InvalidGovernanceTransition(f"Illegal transition from {fr} to {to}")
