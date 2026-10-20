"""VK API: отправка сообщений, получение имени, уведомления менеджеру.

Единственный слой, который ходит в VK API. Retry использует один и тот же
random_id: VK дедуплицирует по нему, поэтому повторная попытка не создаёт
дубликат сообщения у пользователя.
"""

import asyncio
import logging
import random

from vk_bot import keyboards

logger = logging.getLogger("vk_bot.vk")

RETRIES = 3


class VKService:
    def __init__(self, api=None, admin_id: int | None = None):
        self.api = api  # vkbottle API; None в тестах
        self.admin_id = admin_id or None

    async def send(self, peer_id: int, text: str, keyboard_spec=None) -> bool:
        if self.api is None:
            logger.warning("VK API не настроен, сообщение не отправлено")
            return False
        payload = {
            "peer_id": peer_id,
            "message": text,
            "random_id": random.randint(1, 2**31 - 1),
        }
        if keyboard_spec:
            payload["keyboard"] = keyboards.to_vk(keyboard_spec)
        for attempt in range(1, RETRIES + 1):
            try:
                await self.api.messages.send(**payload)
                logger.debug("Сообщение отправлено peer_id=%s", peer_id)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("VK API: попытка %d не удалась: %s", attempt, exc)
                if attempt < RETRIES:
                    await asyncio.sleep(1)
        logger.error("VK API: не удалось отправить сообщение peer_id=%s после %d попыток", peer_id, RETRIES)
        return False

    async def get_user_first_name(self, user_id: int) -> str | None:
        if self.api is None:
            return None
        try:
            users = await self.api.users.get(user_ids=[user_id])
            return users[0].first_name
        except Exception as exc:  # noqa: BLE001
            logger.error("VK API: не удалось получить имя пользователя %s: %s", user_id, exc)
            return None

    async def notify_admin(self, text: str) -> bool:
        if not self.admin_id:
            logger.warning("ADMIN_VK_ID не задан, уведомление менеджера пропущено")
            return False
        return await self.send(self.admin_id, text)
