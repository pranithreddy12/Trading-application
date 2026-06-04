from __future__ import annotations

from typing import Any, Dict
import logging

from .runtime import GovernanceRuntimeContext
from .journal import IdentityViolationJournal
from .decision import GovernanceDecision, ViolationSeverity, severity_from_violation
from .context import IdentityOperationType, GovernanceExecutionContext
from .persistence import GovernancePersistenceLayer
from .escalation import decide_escalation
from .state import InvalidGovernanceTransition, GovernanceEventState

logger = logging.getLogger(__name__)

try:
    from atlas.core.persistence_integrity import IdentityContractViolation
except Exception:  # pragma: no cover - best-effort import
    class IdentityContractViolation(Exception):
        pass


class GovernanceViolationEngine:
    """Handles governance violations: deterministic evaluation, journaling, and enforcement."""

    def __init__(self, runtime: GovernanceRuntimeContext, journal: IdentityViolationJournal) -> None:
        self.runtime = runtime
        self.journal = journal
        # ensure a persistence layer is available on runtime
        if getattr(self.runtime, "persistence", None) is None:
            try:
                self.runtime.persistence = GovernancePersistenceLayer()
            except Exception:
                logger.exception("Unable to initialize GovernancePersistenceLayer")
        self.persistence: GovernancePersistenceLayer | None = getattr(self.runtime, "persistence", None)

    def evaluate(self, violation: Dict[str, Any]) -> GovernanceDecision:
        """Deterministically evaluate a violation and return a GovernanceDecision.

        Decision is computed purely from the violation payload and the runtime
        configuration (e.g., `strict_mode`, `quarantine_enabled`) to ensure
        deterministic outcomes given identical inputs and config.
        """
        # Allow explicit override
        explicit = violation.get("decision")
        if explicit:
            try:
                return GovernanceDecision(explicit)
            except Exception:
                # fallthrough to deterministic mapping
                pass

        sev = severity_from_violation(violation)

        # Highest-severity decisions first.
        if sev >= ViolationSeverity.SYSTEMIC:
            return GovernanceDecision.HALT_RUNTIME
        if sev >= ViolationSeverity.FATAL:
            return GovernanceDecision.HALT_RUNTIME
        if sev >= ViolationSeverity.CRITICAL:
            return GovernanceDecision.REJECT
        if sev >= ViolationSeverity.WARNING:
            # quarantine if enabled, else attempt repair
            if self.runtime.quarantine_enabled:
                return GovernanceDecision.QUARANTINE
            return GovernanceDecision.REPAIR
        return GovernanceDecision.ALLOW

    def handle_violation(self, violation: Dict[str, Any]) -> GovernanceDecision:
        """Process a violation: persist, update metrics, and enforce the decision.

        Returns the final `GovernanceDecision` taken.
        """
        decision = self.evaluate(violation)

        entry = {"violation": violation, "decision": decision.name}
        try:
            self.journal.append(entry)
        except Exception as e:
            logger.exception("Failed to persist violation to journal: %s", e)

        # persist decision to DB if possible
        try:
            if self.persistence:
                # include event meta if present on violation
                event_meta = violation.get("event_meta") if isinstance(violation, dict) else None
                # enrich event_meta with previous state if available
                try:
                    if event_meta and self.persistence:
                        prev_state = self.persistence._get_last_state(event_meta.get("event_id"))
                        event_meta["_prev_state"] = prev_state.name if prev_state is not None else None
                except Exception:
                    logger.exception("Failed to enrich violation.event_meta with _prev_state")
                try:
                    self.persistence.persist_decision(self.runtime.session_id, decision.name, (violation.get("severity") or ""), str(violation), event_meta=event_meta)
                except InvalidGovernanceTransition as e:
                    # deterministic escalation handling
                    logger.warning("Illegal transition detected while persisting decision: %s", e)
                    self._handle_invalid_transition(event_meta, e)
        except Exception:
            logger.exception("Failed to persist decision to DB")

        self.runtime.increment_metric("identity_contract_violations")

        # update counters for specific decision types

        # Enforcement depends on governance mode. In 'shadow' mode we do not raise,
        # instead we journal and increment discovery counters to find bypasses.
        if decision is GovernanceDecision.REJECT:
            self.runtime.increment_metric("rejected_operations")
            logger.error("Governance decision: REJECT -> %s", violation)
            if self.runtime.governance_mode == "enforce":
                raise IdentityContractViolation(violation)
            else:
                # shadow: record as bypass attempt
                self.runtime.increment_metric("bypass_attempts")
                logger.warning("Shadow mode: REJECT recorded but not enforced")
                if self.persistence:
                    try:
                        event_meta = violation.get("event_meta") if isinstance(violation, dict) else None
                        self.persistence.persist_bypass(self.runtime.session_id, "REJECT", str(violation), shadow_tag="shadow", event_meta=event_meta)
                    except Exception:
                        logger.exception("Failed to persist bypass event")

        if decision is GovernanceDecision.HALT_RUNTIME:
            self.runtime.increment_metric("rejected_operations")
            logger.critical("Governance decision: HALT_RUNTIME -> %s", violation)
            if self.runtime.governance_mode == "enforce":
                raise IdentityContractViolation(violation)
            else:
                self.runtime.increment_metric("bypass_attempts")
                logger.warning("Shadow mode: HALT_RUNTIME recorded but not enforced")
                if self.persistence:
                    try:
                            event_meta = violation.get("event_meta") if isinstance(violation, dict) else None
                            self.persistence.persist_bypass(self.runtime.session_id, "HALT_RUNTIME", str(violation), shadow_tag="shadow", event_meta=event_meta)
                    except Exception:
                        logger.exception("Failed to persist bypass event")

        if decision is GovernanceDecision.QUARANTINE:
            self.runtime.increment_metric("quarantine_events")
            logger.warning("Governance decision: QUARANTINE -> %s", violation)
            if self.persistence:
                try:
                    event_meta = violation.get("event_meta") if isinstance(violation, dict) else None
                    try:
                        self.persistence.persist_quarantine(self.runtime.session_id, violation.get("resource_id", "unknown"), str(violation), shadow_tag=("shadow" if self.runtime.governance_mode=="shadow" else None), event_meta=event_meta)
                    except InvalidGovernanceTransition as e:
                        logger.warning("Illegal transition detected while persisting quarantine: %s", e)
                        self._handle_invalid_transition(event_meta, e)
                except Exception:
                    logger.exception("Failed to persist quarantine event")

        if decision is GovernanceDecision.REPAIR:
            logger.info("Governance decision: REPAIR -> %s", violation)
            if self.persistence:
                try:
                    event_meta = violation.get("event_meta") if isinstance(violation, dict) else None
                    try:
                        self.persistence.persist_repair(self.runtime.session_id, violation.get("operation", "repair"), str(violation.get("original", "")), str(violation.get("repaired", "")), shadow_tag=("shadow" if self.runtime.governance_mode=="shadow" else None), event_meta=event_meta)
                    except InvalidGovernanceTransition as e:
                        logger.warning("Illegal transition detected while persisting repair: %s", e)
                        self._handle_invalid_transition(event_meta, e)
                except Exception:
                    logger.exception("Failed to persist repair event")

        # ALLOW falls through
        return decision

    def _handle_invalid_transition(self, event_meta: dict | None, exc: Exception) -> None:
        """Deterministic escalation path when an InvalidGovernanceTransition is encountered.

        This method avoids further DB writes that could re-trigger the same enforcement loop.
        """
        prev = None
        attempted = None
        try:
            if event_meta:
                prev = None
                attempted = None
                prev_s = event_meta.get("_prev_state")
                if prev_s:
                    try:
                        prev = GovernanceEventState(prev_s)
                    except Exception:
                        prev = None
                attempted_s = event_meta.get("event_state")
                if attempted_s:
                    try:
                        attempted = GovernanceEventState(attempted_s)
                    except Exception:
                        attempted = None
        except Exception:
            prev = None
            attempted = None

        # determine decision
        try:
            decision, reason = decide_escalation(prev, attempted if attempted is not None else GovernanceEventState.ESCALATED)
        except Exception:
            decision, reason = GovernanceDecision.QUARANTINE, "escalation_error"

        logger.warning("Escalation decision %s due to illegal transition: %s", decision.name, reason)
        self.runtime.increment_metric("illegal_transitions_detected")

        # Enforce deterministic runtime actions
        if decision is GovernanceDecision.HALT_RUNTIME:
            logger.critical("Escalation HALT_RUNTIME triggered by illegal transition: %s", reason)
            if self.runtime.governance_mode == "enforce":
                raise IdentityContractViolation({"reason": "escalation_halt", "detail": reason})
            else:
                # shadow: record bypass attempt and continue
                self.runtime.increment_metric("bypass_attempts")
                logger.warning("Shadow mode: HALT_RUNTIME recorded but not enforced")
                try:
                    if self.persistence and event_meta:
                        self.persistence.persist_bypass(self.runtime.session_id, "ESCALATION_HALT", reason, shadow_tag="shadow", event_meta=event_meta)
                except Exception:
                    logger.exception("Failed to persist escalation bypass")
        elif decision is GovernanceDecision.QUARANTINE:
            logger.warning("Escalation QUARANTINE triggered by illegal transition: %s", reason)
            self.runtime.increment_metric("quarantine_events")
            try:
                if self.persistence and event_meta:
                    self.persistence.persist_quarantine(self.runtime.session_id, event_meta.get("resource_id", "unknown"), f"escalation:{reason}", shadow_tag=("shadow" if self.runtime.governance_mode=="shadow" else None), event_meta=event_meta)
            except Exception:
                logger.exception("Failed to persist escalation quarantine")
        elif decision is GovernanceDecision.REJECT:
            logger.error("Escalation REJECT triggered by illegal transition: %s", reason)
            if self.runtime.governance_mode == "enforce":
                raise IdentityContractViolation({"reason": "escalation_reject", "detail": reason})
            else:
                self.runtime.increment_metric("bypass_attempts")
                try:
                    if self.persistence and event_meta:
                        self.persistence.persist_bypass(self.runtime.session_id, "ESCALATION_REJECT", reason, shadow_tag="shadow", event_meta=event_meta)
                except Exception:
                    logger.exception("Failed to persist escalation bypass")
        else:
            logger.info("Escalation decision %s is not explicitly handled", decision.name)

    def handle_replay_verification_result(self, replay_id: str, canonical_session_id: str, replay_session_id: str, result) -> None:
        """Persist replay verification result and deterministically route to escalation pipeline."""
        # Persist must happen before enforcement (already handled by caller in scripts),
        # but here we implement deterministic routing based on the result.
        try:
            # derive verification state
            if getattr(result, 'illegal_transition_detected', False):
                vstate = 'ILLEGAL_TRANSITION'
            elif getattr(result, 'divergence_reason', None) == 'missing_event':
                vstate = 'MISSING_LINEAGE'
            elif getattr(result, 'divergence_reason', None) is not None:
                vstate = 'DIVERGED'
            elif result.hash_match and result.sequence_match and result.state_transition_match:
                vstate = 'VERIFIED'
            else:
                vstate = 'CORRUPTED'

            # deterministic mapping
            if vstate == 'VERIFIED':
                decision = None
            elif vstate == 'DIVERGED':
                decision = 'QUARANTINE'
            elif vstate == 'ILLEGAL_TRANSITION':
                decision = 'ESCALATE'
            elif vstate == 'CORRUPTED':
                decision = 'HALT_RUNTIME'
            elif vstate == 'MISSING_LINEAGE':
                decision = 'REJECT'
            else:
                decision = 'QUARANTINE'

            # metrics
            try:
                if vstate == 'VERIFIED':
                    self.runtime.increment_metric('replay_verified_total')
                if vstate == 'DIVERGED':
                    self.runtime.increment_metric('replay_diverged_total')
                if vstate == 'ILLEGAL_TRANSITION':
                    self.runtime.increment_metric('replay_illegal_transition_total')
                if vstate == 'CORRUPTED':
                    self.runtime.increment_metric('replay_halt_total')
                if vstate == 'DIVERGED' or vstate == 'ILLEGAL_TRANSITION':
                    self.runtime.increment_metric('replay_quarantine_total')
            except Exception:
                logger.exception('Failed to increment replay metrics')

            # route into same escalation pipeline
            if decision is None:
                logger.info('Replay verified: no enforcement required')
                return

            # create a synthetic event_meta for escalation context
            event_meta = {
                'event_id': getattr(result, 'divergence_event_id', None),
                '_prev_state': None,
                'event_state': None,
                'resource_id': None,
            }

            # Map decision to GovernanceDecision and call _handle_invalid_transition semantics
            from .decision import GovernanceDecision as GD

            if decision == 'HALT_RUNTIME':
                gdec = GD.HALT_RUNTIME
            elif decision == 'REJECT':
                gdec = GD.REJECT
            elif decision == 'ESCALATE':
                gdec = GD.HALT_RUNTIME
            elif decision == 'QUARANTINE':
                gdec = GD.QUARANTINE
            else:
                gdec = GD.QUARANTINE

            # Persisting should have already occurred; now invoke the same enforcement path
            if gdec is GD.HALT_RUNTIME:
                # deterministic halt
                if self.runtime.governance_mode == 'enforce':
                    raise IdentityContractViolation({'reason': 'replay_enforced_halt', 'replay_id': replay_id})
                else:
                    self.runtime.increment_metric('bypass_attempts')
                    logger.warning('Shadow mode: replay HALT_RUNTIME not enforced')
            elif gdec is GD.REJECT:
                if self.runtime.governance_mode == 'enforce':
                    raise IdentityContractViolation({'reason': 'replay_enforced_reject', 'replay_id': replay_id})
                else:
                    self.runtime.increment_metric('bypass_attempts')
            elif gdec is GD.QUARANTINE:
                try:
                    if self.persistence:
                        self.persistence.persist_quarantine(self.runtime.session_id, event_meta.get('resource_id', 'unknown'), f'replay_escalation:{vstate}', shadow_tag=("shadow" if self.runtime.governance_mode=='shadow' else None), event_meta=event_meta)
                except InvalidGovernanceTransition as e:
                    logger.warning('Illegal transition during replay quarantine persistence: %s', e)
                    self._handle_invalid_transition(event_meta, e)
                except Exception:
                    logger.exception('Failed to persist replay quarantine')

        except Exception:
            logger.exception('Failed to handle replay verification result')

    # Middleware hooks for identity lifecycle
    def before_identity_operation(self, op: IdentityOperationType, payload: Dict[str, Any], ctx: GovernanceExecutionContext | None = None) -> GovernanceDecision:
        """Evaluate an identity operation before it executes. May raise on REJECT/HALT."""
        # include operation type into payload for deterministic evaluation
        import json

        p = dict(payload)
        p.setdefault("operation", op.value)
        if ctx:
            p["execution_context"] = ctx.__dict__

        # generate deterministic event identity for pre-op interception
        try:
            event_meta = self.runtime.generate_event_identity(op.value, p, interception_stage="pre")
            p["event_meta"] = event_meta
        except Exception:
            event_meta = None

        # enrich event_meta with previous state if persistence available
        try:
            if event_meta and self.persistence:
                prev_state = self.persistence._get_last_state(event_meta.get("event_id"))
                event_meta["_prev_state"] = prev_state.name if prev_state is not None else None
                p["event_meta"] = event_meta
        except Exception:
            logger.exception("Failed to enrich event_meta with _prev_state")

        decision = self.evaluate(p)

        # persist pre-op operation
        try:
            if self.persistence:
                payload_str = json.dumps(p, default=str)
                self.persistence.persist_operation(self.runtime.session_id, op.value, p.get("identity_type", "unknown"), str(ctx.__dict__ if ctx else ""), payload_str)
        except Exception:
            logger.exception("Failed to persist pre-op operation")

        # enforce immediate blocking decisions
        if decision is GovernanceDecision.REJECT or decision is GovernanceDecision.HALT_RUNTIME:
            # persist the decision and either raise (enforce) or record as shadow bypass
            try:
                self.journal.append({"operation": op.value, "payload": p, "decision": decision.name})
            except Exception:
                logger.exception("Failed to persist pre-op governance decision")
            if self.runtime.governance_mode == "enforce":
                self.runtime.increment_metric("bypass_attempts")
                raise IdentityContractViolation({"operation": op.value, "reason": "governance_pre_reject", "decision": decision.name})
            else:
                # shadow mode: count discovery and allow execution to continue
                self.runtime.increment_metric("bypass_attempts")
                logger.warning("Shadow mode pre-op decision: %s on %s", decision.name, op.value)
                # record bypass in DB
                try:
                    if self.persistence:
                        self.persistence.persist_bypass(self.runtime.session_id, op.value, f"pre_op_{decision.name}", shadow_tag=("shadow" if self.runtime.governance_mode=="shadow" else None), event_meta=event_meta)
                except Exception:
                    logger.exception("Failed to persist pre-op bypass")

        # for other decisions, just return and allow caller to proceed
        return decision

    def after_identity_operation(self, op: IdentityOperationType, payload: Dict[str, Any], decision: GovernanceDecision, ctx: GovernanceExecutionContext | None = None, snapshot: Dict[str, Any] | None = None) -> None:
        """Record the post-operation governance snapshot and update metrics."""
        import json

        record = {
            "operation": op.value,
            "payload": payload,
            "decision": decision.name,
            "snapshot": snapshot or {},
        }
        if ctx:
            record["execution_context"] = ctx.__dict__
        try:
            self.journal.append(record)
        except Exception:
            logger.exception("Failed to persist post-op governance snapshot")

        # persist post-op result
        try:
            if self.persistence:
                # generate post-op event identity (child of pre-op)
                try:
                    event_meta = self.runtime.generate_event_identity(op.value, record.get("payload", {}), interception_stage="post", parent_event_id=(record.get("payload", {}).get("event_meta", {}).get("event_id") if isinstance(record.get("payload", {}), dict) else None))
                    record["event_meta"] = event_meta
                except Exception:
                    event_meta = None
                # enrich post-op event_meta with previous state
                try:
                    if event_meta and self.persistence:
                        prev_state = self.persistence._get_last_state(event_meta.get("event_id"))
                        event_meta["_prev_state"] = prev_state.name if prev_state is not None else None
                        record["event_meta"] = event_meta
                except Exception:
                    logger.exception("Failed to enrich post-op event_meta with _prev_state")
                payload_str = json.dumps(record, default=str)
                self.persistence.persist_operation(self.runtime.session_id, op.value, record.get("payload", {}).get("identity_type", "unknown"), str(ctx.__dict__ if ctx else ""), payload_str)
        except Exception:
            logger.exception("Failed to persist post-op operation")

        # update counters
        if decision is GovernanceDecision.QUARANTINE:
            self.runtime.increment_metric("quarantined_operations")
        if decision is GovernanceDecision.REPAIR:
            self.runtime.increment_metric("repaired_operations")
        if decision is GovernanceDecision.ALLOW:
            self.runtime.increment_metric("intercepted_operations")
