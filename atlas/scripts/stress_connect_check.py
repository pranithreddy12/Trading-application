import asyncio

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def _one(i: int, db_url: str) -> tuple[int, bool, str]:
    client = TimescaleClient(db_url)
    try:
        await client.connect()
        return i, True, "ok"
    except Exception as e:
        return i, False, str(e)
    finally:
        await client.close()


async def main() -> None:
    settings = get_settings()
    results = await asyncio.gather(*[_one(i, settings.database_url) for i in range(12)])
    errs = [r for r in results if not r[1]]
    for i, ok, msg in results:
        print(f"{'OK' if ok else 'ERR'} {i}: {msg}")
    print(f"SUMMARY total={len(results)} errors={len(errs)}")


if __name__ == "__main__":
    asyncio.run(main())
