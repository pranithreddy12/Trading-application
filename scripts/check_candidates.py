
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def check_candidates():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM strategies s
            JOIN backtest_results b ON b.strategy_id = s.id
            WHERE s.status IN ('elite', 'validated')
              AND b.composite_fitness > 0
              AND NOT EXISTS (
                  SELECT 1 FROM deployment_governance d
                  WHERE d.strategy_id = s.id::text
                    AND d.status IN ('pending_approval', 'approved',
                                     'paper', 'shadow', 'partial_live', 'live')
              )
        """))
        count = r.scalar()
        print(f"Eligible candidates for promotion: {count}")
        
        # Check deployment governance count
        r2 = await conn.execute(text("SELECT COUNT(*) FROM deployment_governance"))
        print(f"Total deployments: {r2.scalar()}")

if __name__ == '__main__':
    asyncio.run(check_candidates())
