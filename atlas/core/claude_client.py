from __future__ import annotations

import asyncio
import json
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from loguru import logger

from atlas.config.settings import settings


@dataclass
class LLMRequest:
    messages: list[dict]
    system: str
    max_tokens: int
    temperature: float
    future: asyncio.Future


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    MODEL = "claude-sonnet-4-6"
    BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self._ssl_ctx = ssl.create_default_context()

    def _call_sync(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        payload = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        req = urllib.request.Request(
            self.BASE_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("x-api-key", settings.anthropic_api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("content-type", "application/json")

        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=60) as response:
            body = json.loads(response.read())
            return body["content"][0]["text"]

    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        loop = asyncio.get_running_loop()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                return await loop.run_in_executor(
                    None,
                    lambda: self._call_sync(
                        messages=messages,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                body = exc.read().decode("utf-8", errors="replace")
                logger.error(f"Claude HTTP {exc.code} on attempt {attempt + 1}: {body[:300]}")
                if exc.code in (429, 529):
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                raise
            except urllib.error.URLError as exc:
                last_error = exc
                logger.error(f"Claude connection error on attempt {attempt + 1}: {exc.reason}")
                await asyncio.sleep(3 * (attempt + 1))

        raise last_error or RuntimeError("Claude provider exhausted retries")


class DegradedProvider(LLMProvider):
    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        return (
            "LLM_DEGRADED: Anthropic unavailable. "
            "Use deterministic local fallback and continue orchestration."
        )


class ClaudeClient:
    """Queued provider abstraction with degraded fail-open fallback."""

    def __init__(self):
        self._primary_provider: LLMProvider = AnthropicProvider()
        self._degraded_provider: LLMProvider = DegradedProvider()
        self._request_queue: asyncio.Queue[LLMRequest | None] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._degraded_mode = False
        self._consecutive_failures = 0
        self._failure_threshold = 2

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            request = await self._request_queue.get()
            if request is None:
                return

            try:
                if self._degraded_mode:
                    response = await self._degraded_provider.complete(
                        request.messages,
                        system=request.system,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                    )
                else:
                    response = await self._primary_provider.complete(
                        request.messages,
                        system=request.system,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                    )
                    self._consecutive_failures = 0

                if not request.future.done():
                    request.future.set_result(response)
            except Exception as exc:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    self._degraded_mode = True
                logger.warning(f"Claude client entering degraded mode: {exc}")
                fallback = await self._degraded_provider.complete(
                    request.messages,
                    system=request.system,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )
                if not request.future.done():
                    request.future.set_result(fallback)

    async def complete(
        self,
        user: str,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
        retries: int = 3,
    ) -> str:
        del retries
        if not settings.anthropic_api_key:
            self._degraded_mode = True
            return await self._degraded_provider.complete(
                [{"role": "user", "content": user}],
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        self._ensure_worker()
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        await self._request_queue.put(
            LLMRequest(
                messages=[{"role": "user", "content": user}],
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                future=future,
            )
        )

        try:
            return await future
        except Exception:
            self._degraded_mode = True
            return await self._degraded_provider.complete(
                [{"role": "user", "content": user}],
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )


claude = ClaudeClient()