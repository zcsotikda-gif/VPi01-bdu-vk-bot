"""Роутер: событие VK -> детерминированная бизнес-логика.

LLM здесь не участвует в маршрутизации и не меняет состояние —
все переходы делает обычный Python-код по payload кнопок, командам
и текущему состоянию пользователя.
"""

import json
import logging
import re

from vk_bot import keyboards
from vk_bot.context import Ctx, OutMessage, Reply
from vk_bot.handlers import commands, consultation, free_text, menu
from vk_bot.states import CONFIRM, CONTACT, NEW, SEGMENT, is_known, qualification_step

logger = logging.getLogger("vk_bot.router")

# action из payload кнопки -> handler. Подпись у всех одна:
# (ctx, user, payload) -> Reply | list[Reply]
ACTIONS = {
    "show_menu": menu.show_menu,
    "show_services": menu.show_services,
    "choose_segment": menu.choose_segment,
    "choose_need": menu.choose_need,
    "select_service": menu.select_service,
    "service_details": menu.service_details,
    "service_other": menu.service_other,
    "back": menu.back,
    "ask_question": menu.ask_question,
    "start_qualification": consultation.start,
    "agree_consent": consultation.agree_consent,
    "refuse_consent": consultation.refuse_consent,
    "request_manager": consultation.request_manager,
    "confirm_lead": consultation.confirm_lead,
    "cancel_lead": consultation.cancel_lead,
    "restart": commands.cmd_start,
    "delete_data_request": commands.cmd_delete_request,
    "delete_data_confirm": commands.cmd_delete_confirm,
    "delete_data_cancel": commands.cmd_delete_cancel,
}

# Текстовые команды (регистронезависимые, работают из любого состояния)
COMMANDS = {
    "start": commands.cmd_start,
    "старт": commands.cmd_start,
    "начать": commands.cmd_start,
    "рестарт": commands.cmd_start,
    "меню": commands.cmd_menu,
    "menu": commands.cmd_menu,
    "услуги": commands.cmd_services,
    "цены": commands.cmd_prices,
    "консультация": commands.cmd_consultation,
    "менеджер": commands.cmd_manager,
    "стоп": commands.cmd_stop,
    "удалить мои данные": commands.cmd_delete_request,
    "удалить данные": commands.cmd_delete_request,
    "help": commands.cmd_help,
    "помощь": commands.cmd_help,
    "ping": commands.cmd_ping,
    "пинг": commands.cmd_ping,
}

YES_WORDS = {"да", "отправить", "отправить заявку", "подтверждаю", "отправляй", "готов"}
NO_WORDS = {"отмена", "отменить", "нет", "не надо", "откажусь"}


def normalize_command(text: str) -> str:
    normalized = (text or "").strip().lower().replace("ё", "е")
    normalized = re.sub(r"^[!/]+", "", normalized)
    return re.sub(r"\s+", " ", normalized)


class UpdateProcessor:
    """Преобразует входящее VK-событие в список исходящих сообщений."""

    def __init__(
        self,
        users,
        leads,
        events,
        lead_service,
        catalog,
        llm,
        texts,
        get_user_name=None,
        admin_id=None,
    ):
        self.users = users
        self.leads = leads
        self.events = events
        self.catalog = catalog
        self.ctx = Ctx(
            users=users,
            leads=leads,
            lead_service=lead_service,
            catalog=catalog,
            llm=llm,
            texts=texts,
            get_user_name=get_user_name,
            admin_id=admin_id,
        )

    # ------------------------------------------------------------- публичное
    async def handle(self, event: dict) -> list[OutMessage]:
        msg = event.get("message") if isinstance(event.get("message"), dict) else event
        if not isinstance(msg, dict):
            logger.warning("Событие не похоже на сообщение: %r", str(event)[:100])
            return []

        message_id = msg.get("id") or msg.get("conversation_message_id")
        if message_id is not None and not self.events.mark_processed(f"msg:{message_id}"):
            logger.info("Повторное событие пропущено (id=%s)", message_id)
            return []

        from_id = self._parse_peer(msg.get("from_id") or msg.get("peer_id"))
        if from_id is None:
            return []
        if from_id < 0:
            return []  # исходящие сообщения самого сообщества

        text = (msg.get("text") or "").strip()
        payload = self._parse_payload(msg.get("payload"))
        user = self.users.get_or_create(from_id)

        if user.get("current_state") == NEW:
            await self._remember_name(from_id, user)
            return self._wrap(await commands.cmd_start(self.ctx, user), user)

        try:
            replies = await self._route(user, text, payload)
        except Exception:  # обработчик не должен ронять longpoll
            logger.exception("Ошибка обработки сообщения от %s", from_id)
            replies = Reply(self.ctx.texts["error_generic"], keyboards.kb_menu())

        fresh = self.users.get(from_id) or user
        logger.info(
            "Событие обработано: vk_id=%s, state=%s, исходящих=%d",
            from_id,
            fresh.get("current_state"),
            len(self._as_list(replies)),
        )
        return self._wrap(replies, user)

    # ------------------------------------------------------------- внутреннее
    async def _route(self, user: dict, text: str, payload: dict | None):
        if payload is not None:
            return await self._dispatch_action(user, payload)
        if not text:
            return Reply(self.ctx.texts["empty_message"], keyboards.kb_simple())

        command = COMMANDS.get(normalize_command(text))
        if command is not None:
            return await command(self.ctx, user, None)
        if text.startswith(("/", "!")):
            # Slash-команды не отправляем в LLM: это либо опечатка, либо мусор
            logger.warning("Неизвестная команда от %s: %r", user["vk_id"], text[:50])
            return Reply(self.ctx.texts["unknown_command"], keyboards.kb_menu())

        state = user.get("current_state")
        if not is_known(state):
            logger.warning("Неизвестное состояние %r у %s, возврат в меню", state, user["vk_id"])
            return await menu.show_menu(self.ctx, user)
        if qualification_step(state) is not None:
            return await consultation.answer_step(self.ctx, user, text)
        if state == CONTACT:
            return await consultation.save_contact(self.ctx, user, text)
        if state == CONFIRM:
            normalized = normalize_command(text)
            if normalized in YES_WORDS:
                return await consultation.confirm_lead(self.ctx, user, None)
            if normalized in NO_WORDS:
                return await consultation.cancel_lead(self.ctx, user, None)
        if state == SEGMENT:
            need = self.catalog.need_by_title(user.get("segment"), text)
            if need is not None:
                return await menu.choose_need(self.ctx, user, {"need": need["id"]})

        # Сюда же попадают состояния menu/service/lead_created/handoff/free_ask:
        # свободный вопрос всегда можно задать, минуя sales-flow
        return await free_text.answer(self.ctx, user, text)

    async def _dispatch_action(self, user: dict, payload: dict):
        action = payload.get("action")
        handler = ACTIONS.get(action) if isinstance(action, str) else None
        if handler is None:
            logger.warning("Неизвестное действие в payload: %r", str(payload)[:100])
            return Reply(self.ctx.texts["unknown_command"], keyboards.kb_menu())
        return await handler(self.ctx, user, payload)

    async def _remember_name(self, from_id: int, user: dict) -> None:
        if user.get("first_name") or self.ctx.get_user_name is None:
            return
        try:
            name = await self.ctx.get_user_name(from_id)
        except Exception:  # имя не критично: без него приветствие обезличенное
            logger.exception("Не удалось получить имя пользователя %s", from_id)
            return
        if name:
            self.users.set_first_name(from_id, name)
            user["first_name"] = name

    @staticmethod
    def _parse_peer(raw) -> int | None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning("Событие без корректного отправителя: %r", raw)
            return None

    @staticmethod
    def _parse_payload(raw) -> dict | None:
        if raw in (None, "", {}):
            return None
        if isinstance(raw, dict):
            return raw
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Повреждённый payload: %r", str(raw)[:100])
            return {"action": "__malformed__"}
        if not isinstance(data, dict):
            logger.warning("Payload не объект: %r", str(raw)[:100])
            return {"action": "__malformed__"}
        return data

    @staticmethod
    def _as_list(replies) -> list:
        if replies is None:
            return []
        return replies if isinstance(replies, list) else [replies]

    def _wrap(self, replies, user: dict) -> list[OutMessage]:
        vk_id = user["vk_id"]
        return [
            OutMessage(peer_id=reply.peer_id or vk_id, text=reply.text, keyboard=reply.keyboard)
            for reply in self._as_list(replies)
        ]
