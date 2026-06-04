from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class IdentityViolationJournal:
    """Append-only JSONL journal for identity/governance violations.

    Records are simple JSON objects with a timestamp and arbitrary
    metadata. The file is created inside the repository under
    `atlas/governance/identity_violation_journal.log` by default.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        base = Path(__file__).resolve().parent
        self.path = Path(path) if path is not None else base / "identity_violation_journal.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "record": record,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str))
            fh.write("\n")
