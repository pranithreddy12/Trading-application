import asyncio
from loguru import logger
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    # Reset code_failed back to pending_code, clear stale code
    async with db.engine.begin() as conn:
        result = await conn.execute(
            text("""
                UPDATE strategies
                SET status = 'pending_code',
                    code = ''
                WHERE status = 'code_failed'
                RETURNING id
            """)
        )
        reset = len(result.fetchall())
    logger.info(f"Reset {reset} code_failed strategies to pending_code")

    # Show current status breakdown
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT status, COUNT(*)
                FROM strategies
                GROUP BY status
                ORDER BY count DESC
            """)
        )
        rows = result.fetchall()

    logger.info("Current strategy statuses:")
    for r in rows:
        logger.info(f"  {r[0]}: {r[1]}")


if __name__ == "__main__":
    asyncio.run(main())
