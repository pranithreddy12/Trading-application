import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from atlas.config.settings import settings

async def main():
    db_url = getattr(settings, 'database_url', None)
    if not db_url:
        print('No database_url in settings; aborting')
        return
    engine = create_async_engine(db_url)
    # Run each query in its own connection to avoid transaction aborts cascading
    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT evolution_pressure_stats FROM portfolio_evolution_log ORDER BY tracked_at DESC LIMIT 1"))
            row = r.fetchone()
            if row and row[0]:
                eps = row[0]
                if isinstance(eps, str):
                    eps = json.loads(eps)
                print('portfolio_evolution_stats:', json.dumps(eps, indent=2))
            else:
                print('No portfolio_evolution_log rows')
    except Exception as e:
        print('portfolio_evolution_log query failed:', e)

    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT mutation_weights, learned_at FROM mutation_policy_state ORDER BY learned_at DESC LIMIT 1"))
            row = r.fetchone()
            if row and row[0]:
                weights = row[0]
                if isinstance(weights, str):
                    weights = json.loads(weights)
                print('mutation_policy_weights:', json.dumps(weights, indent=2))
            else:
                print('No mutation_policy_state rows')
    except Exception as e:
        print('mutation_policy_state query failed:', e)

    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT regime_adaptation_quality, runtime_minutes, recorded_at FROM phase37_intelligence_metrics ORDER BY recorded_at DESC LIMIT 1"))
            row = r.fetchone()
            if row:
                print('latest_metric_row:', {'regime_adaptation_quality': row[0], 'runtime_minutes': row[1], 'recorded_at': str(row[2])})
            else:
                print('No phase37_intelligence_metrics rows')
    except Exception as e:
        print('phase37_intelligence_metrics query failed:', e)

    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT runtime_minutes, regime_adaptation_quality, recorded_at FROM phase37_intelligence_metrics ORDER BY runtime_minutes DESC, recorded_at DESC LIMIT 5"))
            rows = r.fetchall()
            print('top_runtime_rows:', [tuple(row) for row in rows])
            r = await conn.execute(text("SELECT COUNT(*) FROM phase37_intelligence_metrics WHERE runtime_minutes >= 30"))
            print('count_runtime_ge_30:', r.scalar())
    except Exception as e:
        print('runtime disambiguation query failed:', e)

    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
