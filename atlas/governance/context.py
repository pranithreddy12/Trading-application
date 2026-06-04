from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class IdentityOperationType(str, Enum):
    CREATE = "CREATE"
    PROPAGATE = "PROPAGATE"
    INHERIT = "INHERIT"
    MUTATE = "MUTATE"
    REPLAY = "REPLAY"
    PERSIST = "PERSIST"
    RECONSTRUCT = "RECONSTRUCT"
    RECOVER = "RECOVER"
    RETIRE = "RETIRE"
    VALIDATE = "VALIDATE"


@dataclass
class GovernanceExecutionContext:
    trace_id: Optional[str] = None
    lineage_id: Optional[str] = None
    parent_id: Optional[str] = None
    causal_depth: Optional[int] = None
    replay_id: Optional[str] = None
    execution_mode: Optional[str] = None
    governance_mode: Optional[str] = None
    mutation_generation: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
