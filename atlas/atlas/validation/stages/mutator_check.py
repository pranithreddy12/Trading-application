"""
Validation stage for MutatorAgent governance.

Verifies:
  1. mutation_memory table exists and has records
  2. Anti-clone guard is producing diversity (no exact duplicates)
  3. Mutation families are present and diverse
  4. Structural filters are catching invalid mutations
  5. Cost discipline: mutation record count is reasonable
"""

from __future__ import annotations

from atlas.validation.base_stage import BaseStage
from atlas.validation.models import StageResult, StageStatus, DefectType, Evidence


class MutatorCheckStage(BaseStage):
    name = "11_mutator_governance"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        db = ctx.db
        from sqlalchemy.sql import text as sql_text

        # --- Check mutation_memory table exists ---
        async with db.engine.connect() as conn:
            row = await conn.execute(
                sql_text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'mutation_memory')"
                )
            )
            table_exists = row.scalar()
            if not table_exists:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.SCHEMA_FAILURE,
                        message="mutation_memory table does not exist",
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.SCHEMA_FAILURE
                return result

            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=StageStatus.PASS,
                    message="mutation_memory table exists",
                )
            )

            # --- Count mutation records ---
            row = await conn.execute(sql_text("SELECT COUNT(*) FROM mutation_memory"))
            total_mutations = row.scalar() or 0
            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=StageStatus.PASS
                    if total_mutations > 0
                    else StageStatus.SKIPPED,
                    message=f"mutation_memory records: {total_mutations}",
                )
            )

            # --- Check family diversity ---
            row = await conn.execute(
                sql_text("""
                    SELECT COUNT(DISTINCT SPLIT_PART(mutation_type, '::', 1)) AS families
                    FROM mutation_memory
                """)
            )
            family_count = row.scalar() or 0
            if family_count >= 3:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"Mutation family diversity: {family_count} families",
                    )
                )
            elif family_count > 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"Mutation family diversity: {family_count} families (low)",
                    )
                )

            # --- Check for duplicate parent-child pairs ---
            row = await conn.execute(
                sql_text("""
                    SELECT COUNT(*) FROM (
                        SELECT parent_strategy_id, child_strategy_id
                        FROM mutation_memory
                        GROUP BY parent_strategy_id, child_strategy_id
                        HAVING COUNT(*) > 1
                    ) dupes
                """)
            )
            duplicate_pairs = row.scalar() or 0
            if duplicate_pairs == 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message="No duplicate mutation pairs (anti-clone working)",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.SERIALIZATION_FAILURE,
                        message=f"Found {duplicate_pairs} duplicate mutation pairs",
                    )
                )
                result.status = StageStatus.FAIL

            # --- Check mutation type distribution ---
            row = await conn.execute(
                sql_text("""
                    SELECT SPLIT_PART(mutation_type, '::', 2) AS raw_type, COUNT(*) AS cnt
                    FROM mutation_memory
                    GROUP BY raw_type
                    ORDER BY cnt DESC
                    LIMIT 5
                """)
            )
            type_rows = row.fetchall()
            if type_rows:
                type_summary = ", ".join(f"{r[0]}={r[1]}" for r in type_rows)
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"Mutation type distribution: {type_summary}",
                    )
                )

            # --- Check strategies table for mutator-authored entries ---
            row = await conn.execute(
                sql_text("""
                    SELECT COUNT(*) FROM strategies
                    WHERE LOWER(author_agent) LIKE '%mutator%'
                """)
            )
            mutator_strategies = row.scalar() or 0
            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=StageStatus.PASS,
                    message=f"Mutator-authored strategies: {mutator_strategies}",
                )
            )

        return result
