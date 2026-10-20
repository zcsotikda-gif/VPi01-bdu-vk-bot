"""Общие типы, которые используют router и handlers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from vk_bot.keyboards import Button


@dataclass
class Reply:
    """Ответ, который handlers возвращают router'у."""

    text: str
    keyboard: list[list[Button]] | None = None
    peer_id: int | None = None  # None = пользователю, иначе служебное (менеджеру)


@dataclass
class OutMessage:
    """Готовое исходящее сообщение для VK API."""

    peer_id: int
    text: str
    keyboard: list[list[Button]] | None = None


@dataclass
class Ctx:
    """Зависимости, доступные handlers."""

    users: Any
    leads: Any
    lead_service: Any
    catalog: Any
    llm: Any
    texts: dict
    get_user_name: Callable[[int], Awaitable[str | None]] | None = None
    admin_id: int | None = None
