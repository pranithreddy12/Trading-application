from atlas.governance.escalation import decide_escalation
from atlas.governance.state import GovernanceEventState
from atlas.governance.decision import GovernanceDecision


def test_decide_escalation_initial_violation():
    dec, reason = decide_escalation(None, GovernanceEventState.VALIDATED)
    assert dec == GovernanceDecision.REJECT
    assert reason == 'initial_state_violation'


def test_decide_escalation_from_rejected():
    dec, reason = decide_escalation(GovernanceEventState.REJECTED, GovernanceEventState.VALIDATED)
    assert dec == GovernanceDecision.HALT_RUNTIME


def test_decide_escalation_default_quarantine():
    dec, reason = decide_escalation(GovernanceEventState.OBSERVED, GovernanceEventState.ESCALATED)
    assert dec in (GovernanceDecision.QUARANTINE, GovernanceDecision.HALT_RUNTIME)
