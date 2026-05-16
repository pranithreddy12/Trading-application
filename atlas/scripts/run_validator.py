import asyncio
from loguru import logger
from sqlalchemy.sql import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent
from atlas.config.settings import settings


async def main():
    db = TimescaleClient("postgresql+asyncpg://postgres:password@localhost:5433/atlas")
    await db.connect()

    # Reset previously failed strategies for re-validation
    async with db.engine.begin() as conn:
        result = await conn.execute(
            text("""
                UPDATE strategies
                SET status = 'pending_validation'
                WHERE status = 'failed_validation'
                RETURNING id
            """)
        )
        reset_count = len(result.fetchall())

    if reset_count > 0:
        logger.info(f"Reset {reset_count} failed strategies to pending_validation")

    # Then run validation as before
    pending = await db.get_strategies_by_status("pending_validation")
    logger.info(
        f"Validating {len(pending)} strategies with {settings.environment} thresholds"
    )

    agent = ValidatorAgent(db_client=db)
    for s in pending:
        await agent._validate_one(s["id"], s.get("name", "unknown"))

    va = await db.get_strategies_by_status("validated_A")
    vb = await db.get_strategies_by_status("validated_B")
    rc = await db.get_strategies_by_status("research_candidate")
    failed = await db.get_strategies_by_status("failed_validation")
    all_scored = len(va) + len(vb) + len(rc) + len(failed)

    logger.info("=" * 50)
    logger.info(f"VALIDATION COMPLETE ({settings.environment} mode)")
    logger.info(f"  validated_A        {len(va)}")
    logger.info(f"  validated_B        {len(vb)}")
    logger.info(f"  research_candidate {len(rc)}")
    logger.info(f"  failed_validation  {len(failed)}")
    if all_scored > 0:
        passed = len(va) + len(vb) + len(rc)
        logger.info(
            f"  Pass rate          {passed}/{all_scored} ({passed / all_scored * 100:.1f}%)"
        )
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
