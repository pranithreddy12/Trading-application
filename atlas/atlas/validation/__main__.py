"""CI entry point for the ValidationHarness. Exits with code 1 on failure."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger

from .harness import ValidationHarness


async def main():
    output_dir = Path("validation_output")
    harness = ValidationHarness(output_dir=output_dir)
    await harness.initialize()
    output = await harness.run_all()

    if output.overall_status.value != "PASS":
        logger.error(
            f"Validation FAILED — overall status: {output.overall_status.value}"
        )
        sys.exit(1)

    logger.info("Validation PASSED — platform gate certified")
    sys.exit(0)


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    logger.add("validation_output/validation.log", level="DEBUG", rotation="10 MB")
    asyncio.run(main())
