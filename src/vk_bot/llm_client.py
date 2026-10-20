import asyncio
import logging
from typing import Any

import httpx

from vk_bot.config import settings

logger = logging.getLogger("vk_bot.llm_client")


class LLMClient:
    """Async client that talks to the configured AI provider (OpenAI-compatible)."""

    def __init__(self, settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._last_ts = None
        # Ссылки на задачи закрытия старых клиентов: без них задачу может
        # собрать сборщик мусора до завершения
        self._closing: set[asyncio.Task] = set()

    def _ensure_ready(self) -> None:
        if self.settings.timestamp != self._last_ts:
            if self._client is not None:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(self._client.aclose())
                    self._closing.add(task)
                    task.add_done_callback(self._closing.discard)
                except RuntimeError:
                    # No running loop at this moment; ignore
                    pass
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                timeout=30.0,
            )
            self._last_ts = self.settings.timestamp
            logger.debug("LLM client recreated for %s", self.settings.base_url)

    async def get_response(
        self, prompt: str, retries: int = 3, system: str | None = None
    ) -> str:
        """Send a prompt (plus optional system prompt) and return the reply text."""
        self._ensure_ready()
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.settings.model_id, "messages": messages}

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                logger.debug(
                    "LLM request attempt %d to %s (model=%s)",
                    attempt,
                    self.settings.base_url,
                    self.settings.model_id,
                )
                resp = await self._client.post("/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("LLM attempt %d failed: %s", attempt, exc)
                if attempt < retries:
                    await asyncio.sleep(1)

        raise RuntimeError("LLM request failed after retries") from last_exc


# Global instance
llm_client = LLMClient(settings)
