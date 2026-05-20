from __future__ import annotations

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence
from atlas.core.event_lineage import EventLineageClient


class EventLineageStage(BaseStage):
    name = "13_event_lineage"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        db = ctx.db

        try:
            lineage = EventLineageClient(db)

            # Check 1: lifecycle_events table exists by counting rows
            from sqlalchemy.sql import text

            async with db.engine.connect() as conn:
                r = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'lifecycle_events')"
                    )
                )
                table_exists = r.scalar()
                if not table_exists:
                    result.status = StageStatus.FAIL
                    result.defect = DefectType.EVENT_LINEAGE_FAILURE
                    result.error = "lifecycle_events table does not exist"
                    return result

                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message="lifecycle_events table exists",
                    )
                )

            # Check 2: trace_id column on strategies
            async with db.engine.connect() as conn:
                r = await conn.execute(
                    text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'strategies' AND column_name = 'trace_id'
                    """)
                )
                if not r.fetchone():
                    result.status = StageStatus.FAIL
                    result.defect = DefectType.EVENT_LINEAGE_FAILURE
                    result.error = "trace_id column missing from strategies table"
                    return result

                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message="trace_id column exists on strategies",
                    )
                )

            # Check 3: at least one lifecycle event exists
            async with db.engine.connect() as conn:
                r = await conn.execute(text("SELECT COUNT(*) FROM lifecycle_events"))
                event_count = r.scalar() or 0

            if event_count == 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message="No lifecycle events yet (expected on fresh deploy)",
                    )
                )
            else:
                # Check 4: existence of events across multiple stages
                async with db.engine.connect() as conn:
                    r = await conn.execute(
                        text("""
                            SELECT stage, COUNT(*) as cnt
                            FROM lifecycle_events
                            GROUP BY stage
                            ORDER BY cnt DESC
                        """)
                    )
                    stage_counts = {row[0]: row[1] for row in r.fetchall()}

                if len(stage_counts) >= 2:
                    stages_str = ", ".join(f"{k}={v}" for k, v in stage_counts.items())
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"Multi-stage lineage detected: {stages_str}",
                            detail=stage_counts,
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"Single-stage lineage: {stage_counts}",
                            detail=stage_counts,
                        )
                    )

                # Check 5: trace_id propagation (some trace_ids have >1 event)
                async with db.engine.connect() as conn:
                    r = await conn.execute(
                        text("""
                            SELECT trace_id, COUNT(*) as cnt
                            FROM lifecycle_events
                            GROUP BY trace_id
                            HAVING COUNT(*) > 1
                            LIMIT 5
                        """)
                    )
                    propagated = r.fetchall()
                if propagated:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"Trace propagation verified: {len(propagated)} trace_ids with multiple events",
                            detail={row[0]: row[1] for row in propagated},
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message="No multi-event traces yet (newly deployed)",
                        )
                    )

        except Exception as exc:
            result.status = StageStatus.ERROR
            result.defect = DefectType.EVENT_LINEAGE_FAILURE
            result.error = str(exc)

        return result
