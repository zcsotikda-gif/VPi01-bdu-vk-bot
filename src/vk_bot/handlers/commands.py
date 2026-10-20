"""Команды: работают из любого состояния диалога."""

import logging

from vk_bot import keyboards
from vk_bot.context import Ctx, Reply
from vk_bot.handlers import consultation
from vk_bot.states import FREE_ASK, MENU, SEGMENT

logger = logging.getLogger("vk_bot.commands")


def greet_text(ctx: Ctx, user: dict) -> str:
    name = (user.get("first_name") or "").strip()
    if name:
        return ctx.texts["greeting_user"].format(first_name=name)
    return ctx.texts["greeting_generic"]


async def cmd_start(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    """Сброс диалога в начало. История заявок при этом не удаляется."""
    vk_id = user["vk_id"]
    ctx.leads.delete_draft(vk_id)  # черновик незавершённой заявки очищаем
    ctx.users.set_state(vk_id, SEGMENT)
    logger.info("Команда start от %s", vk_id)
    return Reply(greet_text(ctx, user), keyboards.kb_greeting())


async def cmd_menu(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], MENU)
    return Reply(ctx.texts["menu"], keyboards.kb_menu())


async def cmd_services(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], MENU)
    services = ctx.catalog.list_services()[:3]
    rows = [
        [keyboards.Button(service["title"], "select_service", {"service": service["id"]})]
        for service in services
    ]
    rows.append([keyboards.menu_button()])
    text = ctx.texts["service_list_header"] + "\n\n" + ctx.catalog.format_list()
    return Reply(text, rows)


async def cmd_prices(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], MENU)
    text = ctx.catalog.format_list()
    if not ctx.catalog.has_any_price():
        text += "\n\n" + ctx.texts["service_no_price_note"]
    rows = [
        [keyboards.Button("Оценить мою задачу", "start_qualification", color=keyboards.POSITIVE)],
        [keyboards.menu_button()],
    ]
    return Reply(text, rows)


async def cmd_consultation(ctx: Ctx, user: dict, payload: dict | None = None):
    return await consultation.start(ctx, user, payload)


async def cmd_manager(ctx: Ctx, user: dict, payload: dict | None = None):
    return await consultation.request_manager(ctx, user, payload)


async def cmd_stop(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    """Остановить sales-flow: дальше бот отвечает только на вопросы."""
    ctx.users.set_state(user["vk_id"], FREE_ASK)
    return Reply(ctx.texts["stop"], keyboards.kb_llm())


async def cmd_help(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    return Reply(ctx.texts["help"], keyboards.kb_menu())


async def cmd_ping(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    return Reply("pong")


async def cmd_delete_request(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    return Reply(ctx.texts["delete_confirm"], keyboards.kb_delete_confirm())


async def cmd_delete_confirm(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    counts = ctx.users.delete_user_data(user["vk_id"])
    logger.info("Подтверждено удаление данных от %s: %s", user["vk_id"], counts)
    return Reply(ctx.texts["delete_done"], keyboards.kb_after_delete())


async def cmd_delete_cancel(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    return await cmd_menu(ctx, user, payload)
