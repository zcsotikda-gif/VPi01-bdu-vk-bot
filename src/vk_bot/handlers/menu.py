"""Экраны меню: сегмент, потребность, каталог и карточки услуг."""

import logging

from vk_bot import keyboards
from vk_bot.context import Ctx, Reply
from vk_bot.states import FREE_ASK, MENU, SEGMENT, SERVICE

logger = logging.getLogger("vk_bot.menu")

MAX_SERVICE_BUTTONS = 3


async def show_menu(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], MENU)
    return Reply(ctx.texts["menu"], keyboards.kb_menu())


async def choose_segment(ctx: Ctx, user: dict, payload: dict | None = None):
    segment = (payload or {}).get("segment")
    if segment not in ("person", "business"):
        logger.warning("Некорректный сегмент в payload: %r", segment)
        return await show_menu(ctx, user)
    vk_id = user["vk_id"]
    ctx.users.set_segment(vk_id, segment)
    ctx.users.set_service(vk_id, None)
    ctx.users.set_state(vk_id, SEGMENT)
    needs = ctx.catalog.needs(segment)
    text = f"{ctx.texts['segment_prompt']}\n\n{ctx.texts['need_prompt']}"
    return Reply(text, keyboards.kb_segment(needs))


async def choose_need(ctx: Ctx, user: dict, payload: dict | None = None):
    need_id = (payload or {}).get("need")
    services = ctx.catalog.services_for_need(need_id or "")
    if not services:
        logger.warning("Для потребности %r не найдено услуг", need_id)
        return Reply(ctx.texts["no_service_for_need"], keyboards.kb_llm())
    primary = services[0]
    vk_id = user["vk_id"]
    ctx.users.set_service(vk_id, primary["id"])
    ctx.users.set_state(vk_id, SERVICE)
    text = ctx.catalog.format_card(primary)
    if len(services) > 1:
        text += "\n\nЕщё может подойти: " + services[1]["title"]
    return Reply(text, keyboards.kb_service())


async def show_services(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], MENU)
    services = ctx.catalog.list_services()[:MAX_SERVICE_BUTTONS]
    rows = [
        [keyboards.Button(service["title"], "select_service", {"service": service["id"]})]
        for service in services
    ]
    rows.append([keyboards.menu_button()])
    text = ctx.texts["service_list_header"] + "\n\n" + ctx.catalog.format_list()
    return Reply(text, rows)


async def select_service(ctx: Ctx, user: dict, payload: dict | None = None):
    service = ctx.catalog.get((payload or {}).get("service"))
    if service is None:
        logger.warning("Запрошена неизвестная услуга: %r", (payload or {}).get("service"))
        return await show_services(ctx, user)
    vk_id = user["vk_id"]
    ctx.users.set_service(vk_id, service["id"])
    ctx.users.set_state(vk_id, SERVICE)
    return Reply(ctx.catalog.format_card(service), keyboards.kb_service())


async def service_details(ctx: Ctx, user: dict, payload: dict | None = None):
    service_id = (payload or {}).get("service") or user.get("selected_service")
    service = ctx.catalog.get(service_id)
    if service is None:
        return await show_services(ctx, user)
    ctx.users.set_service(user["vk_id"], service["id"])
    ctx.users.set_state(user["vk_id"], SERVICE)
    return Reply(ctx.catalog.format_card(service, detailed=True), keyboards.kb_service())


async def service_other(ctx: Ctx, user: dict, payload: dict | None = None):
    """Листать следующую услугу каталога."""
    services = ctx.catalog.list_services()
    if not services:
        return await show_services(ctx, user)
    ids = [s["id"] for s in services]
    current = user.get("selected_service")
    # Без pos (кнопка с карточки) — следующая после текущей, а не первая в каталоге
    default = ids.index(current) + 1 if current in ids else 0
    try:
        position = int((payload or {}).get("pos", default))
    except (TypeError, ValueError):
        position = default
    service = services[position % len(services)]
    vk_id = user["vk_id"]
    ctx.users.set_service(vk_id, service["id"])
    ctx.users.set_state(vk_id, SERVICE)
    next_pos = (position + 1) % len(services)
    rows = [
        [keyboards.Button("Оценить мою задачу", "start_qualification", color=keyboards.POSITIVE)],
        [keyboards.Button("Подробнее", "service_details", {"service": service["id"]}),
         keyboards.Button("Другая услуга", "service_other", {"pos": next_pos}, color=keyboards.SECONDARY)],
        [keyboards.back_button(), keyboards.menu_button()],
    ]
    return Reply(ctx.catalog.format_card(service), rows)


async def back(ctx: Ctx, user: dict, payload: dict | None = None):
    """«Назад» с карточки услуги: к потребностям сегмента, без сегмента — к каталогу."""
    segment = user.get("segment")
    if segment in ("person", "business"):
        return await choose_segment(ctx, user, {"segment": segment})
    return await show_services(ctx, user)


async def ask_question(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    ctx.users.set_state(user["vk_id"], FREE_ASK)
    return Reply(ctx.texts["empty_message"], keyboards.kb_llm())
