"""Simple CLI to export governance DAG and run replay verification."""
import argparse
from atlas.governance import exporter, replay_verifier
from atlas.governance.persistence import GovernancePersistenceLayer
from uuid import uuid4
import time
from atlas.governance.runtime import GovernanceRuntimeContext
from atlas.governance.journal import IdentityViolationJournal
from atlas.governance.engine import GovernanceViolationEngine
from atlas.governance.context import GovernanceExecutionContext


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='Path to governance.db (canonical)')
    p.add_argument('--replay-db', help='Path to replay governance.db to compare against')
    p.add_argument('--out-prefix', default='governance_dag', help='Output file prefix')
    args = p.parse_args()

    nodes, edges = exporter.build_dag(args.db)
    exporter.export_json(nodes, edges, args.out_prefix + '.json')
    exporter.export_mermaid(nodes, edges, args.out_prefix + '.mmd')
    exporter.export_graphviz(nodes, edges, args.out_prefix + '.dot')

    print(f'Exported DAG nodes={len(nodes)} edges={len(edges)}')

    if args.replay_db:
        res = replay_verifier.verify_replay(args.db, args.replay_db)
        print('Replay verification:')
        print('  hash_match:', res.hash_match)
        print('  sequence_match:', res.sequence_match)
        print('  state_transition_match:', res.state_transition_match)
        print('  divergence_reason:', res.divergence_reason)
        print('  divergence_event_id:', res.divergence_event_id)
        print('  divergence_index:', res.divergence_index)

        # Persist verification result before any enforcement
        try:
            persistence = GovernancePersistenceLayer()
            replay_id = str(uuid4())
            created_at_ns = int(time.time() * 1e9)
            # Infer verification_state
            if res.illegal_transition_detected:
                vstate = 'ILLEGAL_TRANSITION'
            elif res.divergence_reason == 'missing_event':
                vstate = 'MISSING_LINEAGE'
            elif res.divergence_reason is not None:
                vstate = 'DIVERGED'
            elif res.hash_match and res.sequence_match and res.state_transition_match:
                vstate = 'VERIFIED'
            else:
                vstate = 'CORRUPTED'

            escalation = None
            if vstate == 'VERIFIED':
                escalation = 'ALLOW'
            elif vstate == 'DIVERGED':
                escalation = 'QUARANTINE'
            elif vstate == 'ILLEGAL_TRANSITION':
                escalation = 'ESCALATE'
            elif vstate == 'CORRUPTED':
                escalation = 'HALT_RUNTIME'
            elif vstate == 'MISSING_LINEAGE':
                escalation = 'REJECT'

            persistence.persist_replay_verification(
                replay_id=replay_id,
                canonical_session_id=args.db,
                replay_session_id=args.replay_db,
                root_event_id=None,
                verification_state=vstate,
                divergence_event_id=res.divergence_event_id,
                escalation_decision=escalation,
                illegal_transition_count=(1 if res.illegal_transition_detected else 0),
                canonical_hash=getattr(res, 'canonical_hash', None),
                replay_hash=getattr(res, 'replay_hash', None),
                divergence_hash=getattr(res, 'divergence_hash', None),
                segment_hash=getattr(res, 'divergence_hash', None),
                causal_depth=None,
                replay_epoch=None,
                created_at_ns=created_at_ns,
            )
            # Now enforce deterministically via the governance engine using persisted metadata
            try:
                runtime = GovernanceRuntimeContext()
                runtime.persistence = persistence
                runtime.governance_mode = 'enforce'  # follow persisted policy; could be parameterized
                journal = IdentityViolationJournal()
                engine = GovernanceViolationEngine(runtime, journal)

                # Build execution context for replay origin
                exec_ctx = GovernanceExecutionContext(replay_id=replay_id, execution_mode='replay_verification', governance_mode=runtime.governance_mode)

                # Call engine enforcement routing
                engine.handle_replay_verification_result(replay_id=replay_id, canonical_session_id=args.db, replay_session_id=args.replay_db, result=res)
            except Exception as e:
                print('Replay enforcement raised:', e)
        except Exception as e:
            print('Failed to persist replay verification result:', e)


if __name__ == '__main__':
    main()
