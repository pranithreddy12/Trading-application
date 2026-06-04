import asyncio
from datetime import datetime, timezone, timedelta

from atlas.config.settings import get_settings
from atlas.data.ingestion.polygon_rest_client import PolygonRestClient


async def main():
    settings = get_settings()
    client = PolygonRestClient(api_key=settings.polygon_api_key, symbols=["AAPL"], bar_handler=lambda *a, **k: None, poll_bars=60.0, calls_per_minute=60)
    session = client._make_session()
    client._session = session
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).strftime('%Y-%m-%d')
    end = now.strftime('%Y-%m-%d')
    path = f"/v2/aggs/ticker/AAPL/range/1/minute/{start}/{end}"
    try:
        resp = await client._get(path, {"adjusted":"true","sort":"asc","limit":5000})
        print('RESPONSE_KEYS:', list(resp.keys()))
        if 'results' in resp:
            print('RESULTS_LEN', len(resp['results']))
            if resp['results']:
                print('FIRST', resp['results'][0])
                print('LAST', resp['results'][-1])
        else:
            print('FULL_RESP', resp)
    except Exception as e:
        print('HTTP_ERROR', e)
    finally:
        await session.close()

if __name__=='__main__':
    asyncio.run(main())
