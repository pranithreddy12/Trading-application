"""
MutationPatternAgent — Evolutionary Intelligence Ranker.

Purpose:
  Queries mutation_memory to compute per-mutation-type KPIs:
    - Mutation Conversion Rate: % of children that improved parent composite_score
    - Average Score Delta: mean(child_composite_score - parent_composite_score)
    - Total mutations sampled
    - Average parent and child composite scores

Output:
  Ranked leaderboard printed to stdout.
  Certification-grade summary for DAY8_5_MUTATION_PATTERN_CERTIFICATION.md.

Usage:
  python -m agents.l2_strategy.mutation_pattern_agent
  python scripts/rank_mutations.py
"""

import asyncio
from loguru import logger
from sqlalchemy import create_engine, text
from atlas.config.settings import get_settings


def _family(mutation_type: str) -> str:
    """Extract the family prefix from a qualified mutation type (e.g. 'repair::threshold_adjustment' → 'repair')."""
    return mutation_type.split("::")[0] if "::" in mutation_type else "unknown"


def _base_type(mutation_type: str) -> str:
    """Extract the base type from a qualified mutation type."""
    return mutation_type.split("::")[-1] if "::" in mutation_type else mutation_type


def rank_mutations(engine) -> list[dict]:
    """
    Compute mutation KPIs grouped by mutation_type.
    Returns list of dicts sorted by conversion_rate DESC.
    """
    query = """
        SELECT
            mutation_type,
            COUNT(*)                                                AS total,
            COUNT(*) FILTER (WHERE improved = TRUE)                AS improved_count,
            COUNT(*) FILTER (WHERE improved = FALSE)               AS failed_count,
            COUNT(*) FILTER (WHERE improved IS NULL)               AS pending_count,
            ROUND(AVG(parent_composite_score)::numeric, 2)         AS avg_parent_score,
            ROUND(AVG(child_composite_score)::numeric, 2)          AS avg_child_score,
            ROUND(AVG(score_delta)::numeric, 2)                    AS avg_score_delta,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE improved = TRUE)
                / NULLIF(COUNT(*) FILTER (WHERE improved IS NOT NULL), 0),
                1
            )                                                       AS conversion_rate_pct
        FROM mutation_memory
        GROUP BY mutation_type
        ORDER BY conversion_rate_pct DESC NULLS LAST, avg_score_delta DESC NULLS LAST
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    results = []
    for r in rows:
        results.append({
            "mutation_type":      r[0],
            "family":             _family(r[0]),
            "base_type":          _base_type(r[0]),
            "total":              int(r[1]),
            "improved":           int(r[2]),
            "failed":             int(r[3]),
            "pending":            int(r[4]),
            "avg_parent_score":   float(r[5]) if r[5] is not None else None,
            "avg_child_score":    float(r[6]) if r[6] is not None else None,
            "avg_score_delta":    float(r[7]) if r[7] is not None else None,
            "conversion_rate":    float(r[8]) if r[8] is not None else None,
        })
    return results


def print_leaderboard(results: list[dict]) -> None:
    """Pretty-print the mutation leaderboard."""
    print("\n" + "=" * 90)
    print("  ATLAS MUTATION PATTERN LEADERBOARD")
    print("=" * 90)
    print(f"  {'MUTATION TYPE':<40} {'TOTAL':>6} {'CONV%':>7} {'AVG DELTA':>10} {'AVG PARENT':>11} {'AVG CHILD':>10}")
    print("-" * 90)

    for r in results:
        conv  = f"{r['conversion_rate']:.1f}%" if r['conversion_rate'] is not None else "  N/A  "
        delta = f"{r['avg_score_delta']:+.2f}"  if r['avg_score_delta'] is not None else "   N/A"
        p_sc  = f"{r['avg_parent_score']:.1f}"  if r['avg_parent_score'] is not None else "  N/A"
        c_sc  = f"{r['avg_child_score']:.1f}"   if r['avg_child_score'] is not None else "  N/A"
        print(f"  {r['mutation_type']:<40} {r['total']:>6} {conv:>7} {delta:>10} {p_sc:>11} {c_sc:>10}")

    print("=" * 90)

    # Summary stats
    total_mutations = sum(r["total"] for r in results)
    total_improved  = sum(r["improved"] for r in results)
    total_failed    = sum(r["failed"] for r in results)
    total_pending   = sum(r["pending"] for r in results)
    scored = total_mutations - total_pending

    print(f"\n  Total mutations in ledger : {total_mutations}")
    print(f"  Scored (improved/failed)  : {scored}")
    print(f"  Pending backtest          : {total_pending}")
    if scored > 0:
        overall_conv = 100.0 * total_improved / scored
        print(f"  Overall conversion rate   : {overall_conv:.1f}%")
    print()

    # Best / Worst
    scored_results = [r for r in results if r["conversion_rate"] is not None]
    if scored_results:
        best = scored_results[0]
        worst = scored_results[-1]
        print(f"  [BEST] Best  mutation type: {best['mutation_type']} "
              f"(conv={best['conversion_rate']}%, delta={best['avg_score_delta']:+.2f})")
        worst_delta = f"{worst['avg_score_delta']:+.2f}" if worst['avg_score_delta'] is not None else "N/A"
        print(f"  [WORST]  Worst mutation type: {worst['mutation_type']} "
              f"(conv={worst['conversion_rate']}%, delta={worst_delta})")
    print("=" * 90 + "\n")


async def main():
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)

    logger.info("MutationPatternAgent — querying mutation_memory...")
    results = rank_mutations(engine)

    if not results:
        logger.warning("No mutation records found in mutation_memory. Run mutator_agent first.")
        return

    print_leaderboard(results)

    # Check for all-pending (no scores yet)
    all_pending = all(r["conversion_rate"] is None for r in results)
    if all_pending:
        logger.warning(
            "All mutations are still pending backtest. "
            "Run backtest_runner then validator_agent to populate composite scores."
        )
    else:
        logger.info(f"Ranked {len(results)} mutation type(s) by conversion rate.")


if __name__ == "__main__":
    asyncio.run(main())
