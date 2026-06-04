from __future__ import annotations

import os
import uuid
from typing import Dict, Any

STRICT_ENV = "ATLAS_STRICT_IDENTITY_CONTRACTS"


IDENTITY_AUTHORITIES = {
    "trace_id": "governance_runtime",
    "lineage_id": "mutation_lineage_tracker",
    "parent_event_id": "governance_runtime",
    "root_event_id": "governance_runtime",
}


class IdentityAuthorityViolation(Exception):
    pass


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False


def enforce_event_id_authority(event_meta: Dict[str, Any]) -> None:
    """Enforce that non-recoverable causal identity fields are present and valid when strict mode is enabled.

    Reads ATLAS_STRICT_IDENTITY_CONTRACTS env var — if set truthy, missing or invalid causal ids raise an exception.
    """
    strict = os.getenv(STRICT_ENV, "0")
    if not strict or strict in ("0", "false", "False"):
        return

    # For each non-recoverable identity, ensure a valid UUID is present
    for field in ("trace_id", "lineage_id", "parent_event_id", "root_event_id"):
        # root_event_id may be None for root nodes; only enforce presence for non-root nodes
        if field not in event_meta or event_meta.get(field) in (None, ""):
            # If this is root_event_id and parent_event_id is None, allow
            if field == "root_event_id" and not event_meta.get("parent_event_id"):
                continue
            if field == "parent_event_id" and not event_meta.get("parent_event_id") and event_meta.get("root_event_id") == event_meta.get("event_id"):
                continue
            raise IdentityAuthorityViolation(f"Missing required causal identity field '{field}' under strict identity contracts")
        # validate uuid format
        if not _is_valid_uuid(event_meta.get(field)):
            raise IdentityAuthorityViolation(f"Invalid UUID format for causal identity field '{field}'")
