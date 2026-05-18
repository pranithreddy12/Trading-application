import urllib.request
import urllib.error
import json
import ssl
import asyncio
import time
from loguru import logger
from atlas.config.settings import settings


class ClaudeClient:
    """
    Direct urllib-based Claude API client.
    Bypasses httpx entirely — works on networks that block httpx.
    Wraps sync urllib calls in asyncio executor for async compatibility.
    """

    MODEL = "claude-sonnet-4-6"
    BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self._ssl_ctx = ssl.create_default_context()
        self._lock = asyncio.Lock()

    def _call_sync(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        """
        Synchronous urllib call to Anthropic API.
        Call this via run_in_executor from async code.
        """
        payload = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.BASE_URL,
            data=data,
            method="POST",
        )
        req.add_header("x-api-key", settings.anthropic_api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("content-type", "application/json")

        with urllib.request.urlopen(
            req, context=self._ssl_ctx, timeout=60
        ) as resp:
            body = json.loads(resp.read())
            return body["content"][0]["text"]

    async def complete(
        self,
        user: str,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
        retries: int = 3,
    ) -> str:
        """
        Async wrapper — runs sync urllib call in thread executor.
        Includes retry with exponential backoff.
        """
        messages = [{"role": "user", "content": user}]
        loop = asyncio.get_event_loop()
        last_err = None

        for attempt in range(retries):
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: self._call_sync(
                        messages=messages,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                )
                return result

            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                logger.error(
                    f"Claude HTTP {e.code} on attempt {attempt+1}: {body[:300]}"
                )
                last_err = e
                if e.code in (429, 529):
                    wait = 10 * (2 ** attempt)
                    logger.warning(f"Rate limited — waiting {wait}s")
                    await asyncio.sleep(wait)
                elif e.code in (400, 401, 403):
                    raise  # Don't retry auth/bad request errors
                else:
                    await asyncio.sleep(3 * (attempt + 1))

            except urllib.error.URLError as e:
                logger.error(
                    f"Claude connection error attempt {attempt+1}: {e.reason}"
                )
                last_err = e
                await asyncio.sleep(5 * (attempt + 1))

            except Exception as e:
                logger.error(f"Claude unexpected error: {type(e).__name__}: {e}")
                last_err = e
                await asyncio.sleep(3)

        raise last_err or RuntimeError("All Claude retries failed")


# Global singleton — import this everywhere
claude = ClaudeClient()
