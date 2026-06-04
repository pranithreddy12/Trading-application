"""
phase38_identity_governance.py - Phase 38 Identity + Causal Governance Runner.

Usage:
    python scripts/phase38_identity_governance.py --duration-minutes 720
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

from loguru import logger
from atlas.governance import GovernanceRuntimeContext, IdentityViolationJournal, GovernanceViolationEngine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STRICT_IDENTITY_CONTRACT_ENV = "ATLAS_STRICT_IDENTITY_CONTRACTS"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 38 identity + causal governance runner")
    parser.add_argument("--duration-minutes", type=int, default=720)
    parser.add_argument("--metrics-interval", type=int, default=300)
    parser.add_argument(
        "--strict-identity-contracts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce strict UUID identity contracts instead of auto-healing core IDs.",
    )
    parser.add_argument(
        "--governance-mode",
        choices=("enforce", "shadow"),
        default=os.getenv("ATLAS_GOVERNANCE_MODE", "shadow"),
        help="Governance runtime mode: 'enforce' or 'shadow' (default from ATLAS_GOVERNANCE_MODE)",
    )
    args = parser.parse_args()

    # Initialize governance runtime
    runtime = GovernanceRuntimeContext(strict_mode=bool(args.strict_identity_contracts), governance_mode=args.governance_mode)
    journal = IdentityViolationJournal()
    engine = GovernanceViolationEngine(runtime, journal)

    if args.strict_identity_contracts:
        os.environ[STRICT_IDENTITY_CONTRACT_ENV] = "1"
        logger.info("Phase 38 strict identity governance enabled")
    else:
        os.environ.pop(STRICT_IDENTITY_CONTRACT_ENV, None)
        logger.warning("Phase 38 running without strict identity governance")

    # Branding: Phase 38 governance runtime banner (keeps Phase 37 core intact)
    os.environ["ATLAS_PHASE_NAME"] = "Phase38-Governance"
    logger.info("=======================================================================")
    logger.info("PHASE 38 - CAUSAL GOVERNANCE ENGINE (Phase38-Governance)")
    logger.info("Governance runtime: strict_mode=%s quarantine_enabled=%s", runtime.strict_mode, runtime.quarantine_enabled)
    logger.info("=======================================================================")

    phase37_runner = ROOT / "scripts" / "phase37_long_horizon_intelligence.py"
    sys.argv = [
        str(phase37_runner),
        "--duration-minutes",
        str(args.duration_minutes),
        "--metrics-interval",
        str(args.metrics_interval),
    ]
    runpy.run_path(str(phase37_runner), run_name="__main__")


if __name__ == "__main__":
    main()