import os
import uuid
import pytest

from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine
from atlas.governance.context import GovernanceExecutionContext
from atlas.core.persistence_integrity import IdentityContractViolation


def test_select_trace_id_prefers_execution_context():
    engine = ScoutSynthesisEngine(redis_client=None, db_client=None)
    provided = str(uuid.uuid4())
    engine.execution_context = GovernanceExecutionContext(trace_id=provided)
    # _select_trace_id may be async
    tid = pytest.run(asyncio=False, func=lambda: engine._select_trace_id()) if False else None
    # call directly using asyncio
    import asyncio

    tid = asyncio.get_event_loop().run_until_complete(engine._select_trace_id())
    assert tid == provided


def test_select_trace_id_strict_mode_raises_when_missing():
    os.environ["ATLAS_STRICT_IDENTITY_CONTRACTS"] = "true"
    engine = ScoutSynthesisEngine(redis_client=None, db_client=None)
    engine.execution_context = GovernanceExecutionContext()  # no trace_id
    import asyncio

    with pytest.raises(IdentityContractViolation):
        asyncio.get_event_loop().run_until_complete(engine._select_trace_id())
