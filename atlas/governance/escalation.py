from typing import Optional, Tuple
from .decision import GovernanceDecision
from .state import GovernanceEventState


def decide_escalation(prev: Optional[GovernanceEventState], attempted: GovernanceEventState) -> Tuple[GovernanceDecision, str]:
    """Deterministically decide an escalation action for an illegal transition.

    Returns (GovernanceDecision, reason)
    """
    # If attempted to start not at OBSERVED, treat as REJECT
    if prev is None and attempted is not GovernanceEventState.OBSERVED:
        return GovernanceDecision.REJECT, "initial_state_violation"

    # If attempting to move from REJECTED to something else, it's severe
    if prev is GovernanceEventState.REJECTED:
        return GovernanceDecision.HALT_RUNTIME, "recovery_from_rejected_illegal"

    # Divergent recoveries (e.g., REPLAY_VERIFIED -> ???) escalate
    if attempted is GovernanceEventState.ESCALATED or prev is GovernanceEventState.DIVERGED:
        return GovernanceDecision.HALT_RUNTIME, "divergent_escalation"

    # Default: quarantine the resource for investigation
    return GovernanceDecision.QUARANTINE, "default_quarantine"
