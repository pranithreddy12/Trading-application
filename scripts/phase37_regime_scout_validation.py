"""
PHASE 37A - SHORT-HORIZON REGIME & SCOUT INTELLIGENCE VALIDATION

This script wraps the Phase 37 long-horizon controller with a
shorter run and custom report generation targeted at regime and scout
validation artifacts.

Usage:
    python scripts/phase37_regime_scout_validation.py --duration-minutes 30

By default this will run for 30 minutes with metrics persisted every
2 minutes. For a quick smoke, pass `--duration-minutes 1`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import types
from datetime import datetime, timezone
from typing import Any

import importlib.util
from pathlib import Path

# Import the Phase37 controller by file path to avoid package import issues
spec_path = Path(__file__).resolve().parent / "phase37_long_horizon_intelligence.py"
spec = importlib.util.spec_from_file_location("phase37_long_horizon_intelligence", str(spec_path))
ph37_mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(ph37_mod)
Phase37LongHorizonController = ph37_mod.Phase37LongHorizonController


def _dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def make_short_reports(initial: dict[str, Any], latest: dict[str, Any], duration_minutes: int) -> None:
    # Regime analysis
    regime_lines = [
        "# PHASE37_SHORT_REGIME_ANALYSIS",
        "",
        f"Duration minutes: {duration_minutes}",
        f"Active regimes observed: {len(latest.get('regime_specialization_snapshot', {}).get('regime_specialists', {}))}",
        f"Regime adaptation quality: {latest.get('regime_adaptation_quality', 0)}",
        "",
        "Regime specialization snapshot:",
        _dump_json(latest.get('regime_specialization_snapshot', {})),
    ]

    # Scout divergence
    scout_lines = [
        "# PHASE37_SCOUT_DIVERGENCE_REPORT",
        "",
        f"Scout intelligence score: {latest.get('scout_intelligence_score', 0)}",
        "",
        "Scout trust rankings:",
        _dump_json(latest.get('scout_trust_rankings', [])),
        "",
        "Scout specialization history:",
        _dump_json(latest.get('scout_specialization_history', [])),
    ]

    # Mutation response
    mutation_lines = [
        "# PHASE37_MUTATION_RESPONSE_REPORT",
        "",
        f"Mutation dominance score: {latest.get('mutation_dominance_score', 0)}",
        "",
        "Mutation family rankings:",
        _dump_json(latest.get('mutation_family_rankings', [])),
        "",
        "Mutation survival curves (sample):",
        _dump_json(latest.get('mutation_survival_curves', [])[:30]),
    ]

    # Capital flow
    capital_lines = [
        "# PHASE37_ADAPTIVE_CAPITAL_FLOW_REPORT",
        "",
        f"Capital migration score: {latest.get('capital_migration_score', 0)}",
        "",
        "Capital allocation migration:",
        _dump_json(latest.get('capital_allocation_migration', {})),
    ]

    # Certification
    cert_lines = [
        "# PHASE37_SHORT_INTELLIGENCE_CERTIFICATION",
        "",
        f"Run completed at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Summary scores:",
        _dump_json({
            "regime_adaptation_quality": latest.get('regime_adaptation_quality', 0),
            "scout_intelligence_score": latest.get('scout_intelligence_score', 0),
            "mutation_dominance_score": latest.get('mutation_dominance_score', 0),
            "capital_migration_score": latest.get('capital_migration_score', 0),
        }),
    ]

    files = {
        "PHASE37_SHORT_REGIME_ANALYSIS.md": "\n".join(regime_lines) + "\n",
        "PHASE37_SCOUT_DIVERGENCE_REPORT.md": "\n".join(scout_lines) + "\n",
        "PHASE37_MUTATION_RESPONSE_REPORT.md": "\n".join(mutation_lines) + "\n",
        "PHASE37_ADAPTIVE_CAPITAL_FLOW_REPORT.md": "\n".join(capital_lines) + "\n",
        "PHASE37_SHORT_INTELLIGENCE_CERTIFICATION.md": "\n".join(cert_lines) + "\n",
    }

    for fname, content in files.items():
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)


async def main(duration_minutes: int, metrics_interval: int) -> None:
    controller = Phase37LongHorizonController(duration_minutes=duration_minutes, metrics_interval=metrics_interval)

    # Monkeypatch the report generator to produce short-run reports
    def _generate(self, initial, latest, duration_minutes):
        make_short_reports(initial, latest, duration_minutes)

    controller._generate_reports = types.MethodType(_generate, controller)

    await controller.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-minutes", type=int, default=30)
    parser.add_argument("--metrics-interval", type=int, default=120)
    args = parser.parse_args()
    asyncio.run(main(args.duration_minutes, args.metrics_interval))
