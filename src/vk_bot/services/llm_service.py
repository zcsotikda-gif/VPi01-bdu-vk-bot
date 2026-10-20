"""LLMService: единственное место, где бот разговаривает с моделью.

Сервис НЕ трогает SQLite и НЕ меняет состояние пользователя.
Получает утверждённый контекст (каталог, FAQ, system prompt) и вопрос
пользователя с вырезанными персональными контактами.
"""

import logging
import re

from vk_bot.services.catalog_service import CatalogService

logger = logging.getLogger("vk_bot.llm")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()\-]{9,16}\d)(?!\d)")

MAX_QUESTION_LENGTH = 2000
MAX_REPLY_LENGTH = 1500


class LLMUnavailable(Exception):
    """Модель недоступна или ответ не получен."""


def redact(text: str) -> str:
    """Убрать типичные персональные контакты перед отправкой в LLM."""
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text


class LLMService:
    def __init__(self, settings, catalog: CatalogService, client=None):
        self.settings = settings
        self.catalog = catalog
        # httpx-клиент подключается лениво; в тестах подсовываем фейковый
        self._client = client
        self._client_ts = None

    @property
    def client(self):
        if self._client is None:
            from vk_bot.llm_client import llm_client  # импорт здесь, чтобы не тянуть httpx в тесты

            self._client = llm_client
        return self._client

    def build_system_prompt(self, segment: str | None = None, service_id: str | None = None) -> str:
        parts = [self.catalog.system_prompt_text]
        parts.append("\n## Каталог услуг (используй только эти сведения)\n" + self.catalog.catalog_text())
        faq = self.catalog.faq_text()
        if faq:
            parts.append("\n## Частые вопросы\n" + faq)
        context_lines = []
        if segment:
            context_lines.append("Сегмент: " + ("личные задачи" if segment == "person" else "бизнес" if segment == "business" else segment))
        service = self.catalog.get(service_id)
        if service:
            context_lines.append("Пользователь смотрит услугу: " + service["title"])
        if context_lines:
            parts.append("\n## Контекст пользователя\n" + "\n".join(context_lines))
        parts.append("\nОтвечай кратко, по-русски, 1-4 коротких абзаца.")
        return "\n".join(parts)

    async def answer(self, question: str, segment: str | None = None, service_id: str | None = None) -> str:
        clean_question = redact((question or "").strip())[:MAX_QUESTION_LENGTH]
        if not clean_question:
            raise LLMUnavailable("пустой вопрос")
        try:
            reply = await self.client.get_response(
                clean_question,
                system=self.build_system_prompt(segment, service_id),
            )
        except Exception as exc:  # любой сбой модели превращаем в одно исключение
            logger.error("LLM недоступна: %s: %s", type(exc).__name__, exc)
            raise LLMUnavailable(str(exc)) from exc
        reply = (reply or "").strip()
        if not reply:
            raise LLMUnavailable("пустой ответ модели")
        logger.info("Ответ LLM подготовлен (%d символов)", len(reply))
        if len(reply) > MAX_REPLY_LENGTH:
            reply = reply[:MAX_REPLY_LENGTH].rstrip() + "…"
        return reply
