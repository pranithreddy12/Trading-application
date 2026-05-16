"""CLI entry point for running the ValidationHarness with options.

Usage:
    python -m atlas.validation.cli
    python -m atlas.validation.cli --api-base http://localhost:8000 --output-dir ./reports
    python -m atlas.validation.cli --stage 03_route_auth
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger


async def main():
    parser = argparse.ArgumentParser(description="ATLAS ValidationHarness CLI")
    parser.add_argument(
        "--api-base", default="http://localhost:8000", help="API server base URL"
    )
    parser.add_argument(
        "--output-dir", default="validation_output", help="Output directory for reports"
    )
    parser.add_argument("--stage", default=None, help="Run a single stage by name")
    parser.add_argument(
        "--list-stages", action="store_true", help="List available stages and exit"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    from atlas.validation.harness import ValidationHarness

    harness = ValidationHarness(output_dir=output_dir)
    harness.set_api_base(args.api_base)

    if args.list_stages:
        print("Available stages:")
        for s in harness.stages:
            print(f"  {s.name}")
        sys.exit(0)

    await harness.initialize()

    if args.stage:
        result = await harness.run_stage(args.stage)
        if result:
            print(
                f"Stage '{args.stage}': {result.status.value} ({result.latency_ms:.0f}ms)"
            )
            sys.exit(0 if result.status.value == "PASS" else 1)
        else:
            print(f"Stage '{args.stage}' not found")
            sys.exit(1)

    output = await harness.run_all()
    sys.exit(0 if output.overall_status.value == "PASS" else 1)


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    asyncio.run(main())
