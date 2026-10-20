"""Точка входа VK-бота: longpoll, отправка сообщений, служебные команды.

Запуск из корня проекта: python -m vk_bot (.env, config.yaml, data/ и
bot.log берутся из рабочего каталога). Бизнес-логика живёт в остальных
модулях пакета; здесь только адаптер к vkbottle.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vkbottle import Bot, GroupEventType
from vkbottle.bot import Message

from vk_bot.bot import create_app
from vk_bot.config import settings
from vk_bot.instance_lock import acquire_instance_lock

# ---------------------------------------------------------------------------
# Logging configuration: write to stdout and to rotating file bot.log
# ---------------------------------------------------------------------------
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

file_handler = RotatingFileHandler(
    "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(log_formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])

logger = logging.getLogger("vk_bot")


def apply_log_level(level_name: str) -> None:
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logging.getLogger("vk_bot").setLevel(level)
    logging.getLogger("vkbottle").setLevel(level)


# Уровень логирования берётся из config.yaml (log_level).
# DEBUG показывает все сырые события LongPoll — удобно для диагностики.
apply_log_level(settings.log_level)

# ---------------------------------------------------------------------------
# Bot initialization
# ---------------------------------------------------------------------------
missing = settings.missing_required()
if missing:
    logger.error("Не заданы обязательные переменные окружения: %s", ", ".join(missing))
    raise SystemExit(1)

# Блокировка рядом с базой: вторая копия с теми же данными не стартует
lock_path = Path(settings.DB_PATH).with_name("bot.lock")
instance_lock = acquire_instance_lock(lock_path)
if instance_lock is None:
    logger.error("Бот уже запущен (занята блокировка %s). Вторая копия не стартует.", lock_path)
    raise SystemExit(1)

bot = Bot(settings.VK_TOKEN)
app = create_app(settings, api=bot.api)


# ---------------------------------------------------------------------------
# Handlers
#
# ВАЖНО: vkbottle обрабатывает обработчики по порядку регистрации и
# останавливается на первом сработавшем блокирующем обработчике.
# Поэтому /reload_config объявлен ДО общего обработчика @bot.on.message().
# ---------------------------------------------------------------------------

@bot.on.message(text="/reload_config")
async def reload_cfg(msg: Message):
    settings.reload()
    apply_log_level(settings.log_level)
    logger.info("Конфигурация перезагружена")
    await msg.answer("Конфигурация обновлена.")


@bot.on.raw_event(GroupEventType.GROUP_JOIN)
async def welcome(event):
    user_id = event.object.user_id
    logger.info("Новый участник: %s", user_id)
    await app.vk.send(
        user_id,
        "Привет! Рады видеть вас в группе ИИ-Апгрейд. "
        "Напишите сюда — помогу разобраться, где ИИ может помочь.",
    )


@bot.on.message()
async def on_message(message: Message):
    if message.out:
        return  # собственные (исходящие) сообщения не обрабатываем

    event = {
        "id": message.id,
        "from_id": message.from_id,
        "peer_id": message.peer_id,
        "text": message.text,
        "payload": getattr(message, "payload", None),
    }
    try:
        outgoing = await app.processor.handle(event)
    except Exception:  # сбой обработки не должен ронять longpoll
        logger.exception("Ошибка обработки сообщения")
        await app.vk.send(message.from_id, "Произошла ошибка. Попробуйте позже.")
        return

    for out in outgoing:
        await app.vk.send(out.peer_id, out.text, out.keyboard)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(
        "Запуск бота. AI=%s, base_url=%s, модель=%s, log_level=%s, db=%s, admin=%s",
        settings.ai_provider,
        settings.base_url,
        settings.model_id,
        settings.log_level,
        settings.DB_PATH,
        settings.ADMIN_VK_ID or "не задан",
    )
    asyncio.run(bot.run_polling())
