import asyncio
import asyncpg
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.environ["PYTHONPATH"] = _PROJECT_ROOT

from atlas.config.settings import settings
import re
DB_URL = re.sub(r'\+\w+', '', settings.database_url)

async def main():
    conn = await asyncpg.connect(DB_URL)
    
    # 1. Strategies & Lifecycle
    r = await conn.fetchrow('SELECT COUNT(*) FROM strategies')
    print('Total Strategies:', r[0])
    
    r = await conn.fetch('SELECT lifecycle_state, COUNT(*) FROM strategies GROUP BY lifecycle_state')
    print('Lifecycle states:', dict(r))
    
    r = await conn.fetch('SELECT status, COUNT(*) FROM strategies GROUP BY status')
    print('Statuses:', dict(r))
    
    # 2. Fitness Metrics
    r = await conn.fetchrow('SELECT AVG(composite_fitness_score), AVG(sortino_ratio), AVG(expectancy) FROM backtest_results WHERE composite_fitness_score > 0')
    if r:
        print(f"Avg Fitness: {r[0]}, Avg Sortino: {r[1]}, Avg Expectancy: {r[2]}")
    
    # 3. Regime Survival
    r = await conn.fetch('SELECT regime, COUNT(*), AVG(regime_fitness_score) FROM regime_fitness_log GROUP BY regime')
    for row in r:
        print(f"Regime {row[0]}: Count={row[1]}, Avg Score={row[2]}")
        
    # 4. Mutation Survival
    r = await conn.fetchrow('SELECT COUNT(*) FROM mutation_survival_log')
    print('Mutation Survival Logs:', r[0])
    
    # 5. Portfolio Evolution
    r = await conn.fetchrow('SELECT COUNT(*) FROM portfolio_evolution_log')
    print('Portfolio Evolution Logs:', r[0])
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
