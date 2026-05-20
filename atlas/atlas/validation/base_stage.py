from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import StageResult, StageStatus, DefectType


class BaseStage(ABC):
    def __init__(self):
        self._start_ms: float = 0.0

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def _run(self, ctx: Any) -> StageResult: ...

    async def execute(self, ctx: Any) -> StageResult:
        self._start_ms = time.time()
        try:
            result = await self._run(ctx)
        except Exception as exc:
            result = StageResult(
                stage_name=self.name,
                status=StageStatus.ERROR,
                defect=self._classify(exc),
                error=str(exc),
                traceback_str=traceback.format_exc(),
            )
        result.latency_ms = (time.time() - self._start_ms) * 1000
        return result

    def _classify(self, exc: Exception) -> DefectType:
        return DefectType.SCHEMA_FAILURE
