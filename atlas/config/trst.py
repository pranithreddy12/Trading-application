
import asyncio, httpx
from atlas.config.settings import settings

async def test():
    transport = httpx.AsyncHTTPTransport(http2=False)
    async with httpx.AsyncClient(transport=transport, timeout=30) as client:
        r = await client.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': settings.anthropic_api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-sonnet-4-6',
                'max_tokens': 20,
                'messages': [{'role': 'user', 'content': 'Reply OK'}]
            }
        )
        print(f"Status: {r.status_code}")
        data = r.json()
        print(f"Response: {data['content'][0]['text']}")

asyncio.run(test())
