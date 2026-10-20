"""Свободные вопросы: единственное место, где отвечает LLM."""

import logging

from vk_bot import keyboards
from vk_bot.context import Ctx, Reply
from vk_bot.services.llm_service import LLMUnavailable

logger = logging.getLogger("vk_bot.free_text")


async def answer(ctx: Ctx, user: dict, text: str) -> Reply:
    try:
        reply_text = await ctx.llm.answer(
            text,
            segment=user.get("segment"),
            service_id=user.get("selected_service"),
        )
    except LLMUnavailable:
        logger.warning("LLM недоступна для %s, показываем запасной вариант", user["vk_id"])
        return Reply(ctx.texts["llm_unavailable"], keyboards.kb_llm_fallback())
    return Reply(reply_text, keyboards.kb_llm())
