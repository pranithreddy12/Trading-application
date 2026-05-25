import asyncio
import asyncpg
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
from atlas.config.settings import settings
import re
DB_URL = re.sub(r'\+\w+', '', settings.database_url)

async def main():
    conn = await asyncpg.connect(DB_URL)
    r = await conn.execute("UPDATE strategies SET status = 'obsolete' WHERE status = 'backtest_failed'")
    print(f"Obsoleted: {r}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
