"""
Mutation Metrics — telemetry and win-rate analysis for MutatorAgent.

Queries mutation_memory to compute:
  - Win rate per mutation family and type
  - Average Sharpe, entry, and trade deltas
  - Complexity delta trends
  - Family effectiveness rankings
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class FamilyMetrics:
    family: str
    total_mutations: int = 0
    sharpe_improved: int = 0
    sharpe_degraded: int = 0
    avg_sharpe_delta: float = 0.0
    avg_entry_delta: float = 0.0
    avg_trade_delta: float = 0.0
    complexity_delta: float = 0.0
    win_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "total_mutations": self.total_mutations,
            "win_rate": round(self.win_rate, 3),
            "avg_sharpe_delta": round(self.avg_sharpe_delta, 4),
            "avg_entry_delta": round(self.avg_entry_delta, 2),
            "avg_trade_delta": round(self.avg_trade_delta, 2),
            "complexity_delta": round(self.complexity_delta, 2),
            "sharpe_improved": self.sharpe_improved,
            "sharpe_degraded": self.sharpe_degraded,
        }


@dataclass
class TypeMetrics:
    mutation_type: str
    total: int = 0
    sharpe_improved: int = 0
    avg_sharpe_delta: float = 0.0
    avg_entry_delta: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mutation_type": self.mutation_type,
            "total": self.total,
            "win_rate": round(self.sharpe_improved / self.total, 3)
            if self.total
            else 0.0,
            "avg_sharpe_delta": round(self.avg_sharpe_delta, 4),
            "avg_entry_delta": round(self.avg_entry_delta, 2),
        }


@dataclass
class MutationMetricsReport:
    total_mutations: int = 0
    families: dict[str, FamilyMetrics] = field(default_factory=dict)
    types: dict[str, TypeMetrics] = field(default_factory=dict)
    top_family: str = ""
    bottom_family: str = ""

    def to_dict(self) -> dict:
        return {
            "total_mutations": self.total_mutations,
            "families": {k: v.to_dict() for k, v in sorted(self.families.items())},
            "types": {
                k: v.to_dict()
                for k, v in sorted(
                    self.types.items(), key=lambda x: x[1].total, reverse=True
                )
            },
            "top_family": self.top_family,
            "bottom_family": self.bottom_family,
        }


async def compute_mutation_metrics(db_client) -> MutationMetricsReport:
    """Query mutation_memory and compute per-family and per-type metrics."""
    from sqlalchemy.sql import text as sql_text

    report = MutationMetricsReport()

    async with db_client.engine.connect() as conn:
        rows = await conn.execute(
            sql_text("""
                SELECT
                    mutation_type,
                    sharpe_delta,
                    child_entry_count - parent_entry_count AS entry_delta,
                    child_trades - parent_trades AS trade_delta
                FROM mutation_memory
                ORDER BY created_at DESC
            """)
        )
        records = rows.fetchall()

    if not records:
        logger.info("No mutation records found for metrics")
        return report

    report.total_mutations = len(records)
    family_buckets: dict[str, list[dict]] = {}
    type_buckets: dict[str, list[dict]] = {}

    for row in records:
        mut_type: str = row[0] or "unknown"
        sharpe_delta: float = float(row[1] or 0)
        entry_delta: int = int(row[2] or 0)
        trade_delta: int = int(row[3] or 0)

        family = mut_type.split("::")[0] if "::" in mut_type else "unknown"
        raw_type = mut_type.split("::")[-1] if "::" in mut_type else mut_type

        family_buckets.setdefault(family, []).append(
            {
                "sharpe_delta": sharpe_delta,
                "entry_delta": entry_delta,
                "trade_delta": trade_delta,
            }
        )
        type_buckets.setdefault(raw_type, []).append(
            {"sharpe_delta": sharpe_delta, "entry_delta": entry_delta}
        )

    for family, bucket in family_buckets.items():
        n = len(bucket)
        sharpe_deltas = [r["sharpe_delta"] for r in bucket]
        entry_deltas = [r["entry_delta"] for r in bucket]
        trade_deltas = [r["trade_delta"] for r in bucket]
        fm = FamilyMetrics(
            family=family,
            total_mutations=n,
            sharpe_improved=sum(1 for d in sharpe_deltas if d > 0),
            sharpe_degraded=sum(1 for d in sharpe_deltas if d < 0),
            avg_sharpe_delta=sum(sharpe_deltas) / n,
            avg_entry_delta=sum(entry_deltas) / n,
            avg_trade_delta=sum(trade_deltas) / n,
            win_rate=sum(1 for d in sharpe_deltas if d > 0) / n if n else 0.0,
        )
        report.families[family] = fm

    for raw_type, bucket in type_buckets.items():
        n = len(bucket)
        sharpe_deltas = [r["sharpe_delta"] for r in bucket]
        entry_deltas = [r["entry_delta"] for r in bucket]
        tm = TypeMetrics(
            mutation_type=raw_type,
            total=n,
            sharpe_improved=sum(1 for d in sharpe_deltas if d > 0),
            avg_sharpe_delta=sum(sharpe_deltas) / n,
            avg_entry_delta=sum(entry_deltas) / n,
        )
        report.types[raw_type] = tm

    if report.families:
        sorted_families = sorted(
            report.families.values(), key=lambda f: f.win_rate, reverse=True
        )
        report.top_family = sorted_families[0].family if sorted_families else ""
        report.bottom_family = (
            sorted_families[-1].family if len(sorted_families) > 1 else ""
        )

    return report


async def print_mutation_scorecard(db_client):
    """Pretty-print mutation metrics to logger."""
    report = await compute_mutation_metrics(db_client)
    if report.total_mutations == 0:
        logger.info("Mutation scorecard: no data yet")
        return

    logger.info("=" * 60)
    logger.info("  MUTATION SCORECARD")
    logger.info(f"  Total mutations tracked: {report.total_mutations}")
    logger.info("=" * 60)

    for family_name in sorted(report.families):
        fm = report.families[family_name]
        trend = "+" if fm.avg_sharpe_delta > 0 else ""
        logger.info(
            f"  [{family_name:16s}]  n={fm.total_mutations:3d}  "
            f"win={fm.win_rate:.1%}  "
            f"sharpe_delta={trend}{fm.avg_sharpe_delta:.4f}  "
            f"entry_delta={fm.avg_entry_delta:+.1f}"
        )

    if report.top_family:
        logger.info(f"  Best family: {report.top_family}")
    if report.bottom_family and report.bottom_family != report.top_family:
        logger.info(f"  Worst family: {report.bottom_family}")
    logger.info("=" * 60)
