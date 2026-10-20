"""Sales-flow: квалификация, согласие, контакт, заявка, менеджер."""

import logging

from vk_bot import keyboards
from vk_bot.context import Ctx, Reply
from vk_bot.handlers import menu
from vk_bot.states import (
    CONFIRM,
    CONSENT,
    CONTACT,
    HANDOFF,
    LEAD_CREATED,
    MENU,
    QUALIFICATION_QUESTIONS,
    qualification_state,
    qualification_step,
)

logger = logging.getLogger("vk_bot.consultation")

_ANSWER_FIELDS = {1: "problem", 2: "expected_result", 3: "deadline"}


def _segment_label(segment: str | None) -> str:
    return {"person": "Для себя", "business": "Для бизнеса"}.get(segment or "", "—")


def build_summary(ctx: Ctx, user: dict, draft: dict) -> str:
    service = ctx.catalog.get(draft.get("service"))
    return ctx.texts["summary"].format(
        segment=_segment_label(draft.get("segment") or user.get("segment")),
        service=service["title"] if service else "—",
        problem=draft.get("problem") or "—",
        expected_result=draft.get("expected_result") or "—",
        deadline=draft.get("deadline") or "—",
        contact=draft.get("contact") or "не указан",
    )


async def start(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    vk_id = user["vk_id"]
    ctx.leads.delete_draft(vk_id)
    ctx.users.set_state(vk_id, qualification_state(1))
    return Reply(ctx.texts["qualification_1"], keyboards.kb_qualification())


async def answer_step(ctx: Ctx, user: dict, text: str) -> Reply:
    """Следующий ответ квалификации. Один вопрос — одно сообщение."""
    vk_id = user["vk_id"]
    step = qualification_step(user.get("current_state"))
    if step is None or step not in _ANSWER_FIELDS:
        logger.warning("Ответ квалификации при неожиданном состоянии %r", user.get("current_state"))
        return await menu.show_menu(ctx, user)
    draft = ctx.leads.get_draft(vk_id) or {}
    field = _ANSWER_FIELDS[step]
    value = (text or "").strip()[:1000]
    ctx.leads.save_draft(
        vk_id=vk_id,
        segment=user.get("segment"),
        service=user.get("selected_service"),
        problem=value if field == "problem" else draft.get("problem"),
        expected_result=value if field == "expected_result" else draft.get("expected_result"),
        deadline=value if field == "deadline" else draft.get("deadline"),
        contact=draft.get("contact"),
    )
    if step < QUALIFICATION_QUESTIONS:
        ctx.users.set_state(vk_id, qualification_state(step + 1))
        return Reply(ctx.texts[f"qualification_{step + 1}"], keyboards.kb_qualification())
    ctx.users.set_state(vk_id, CONSENT)
    return Reply(ctx.texts["consent_request"], keyboards.kb_consent())


async def agree_consent(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    vk_id = user["vk_id"]
    ctx.users.set_consent(vk_id, True)
    ctx.users.set_state(vk_id, CONTACT)
    return Reply(ctx.texts["contact_request"], keyboards.kb_qualification())


async def refuse_consent(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    """Отказ от согласия: контакт не собираем, заявку можно отправить без него."""
    vk_id = user["vk_id"]
    ctx.users.set_consent(vk_id, False)
    ctx.leads.update_draft_contact(vk_id, None)
    draft = ctx.leads.get_draft(vk_id) or {}
    ctx.users.set_state(vk_id, CONFIRM)
    text = ctx.texts["consent_declined"] + "\n\n" + build_summary(ctx, user, draft)
    return Reply(text, keyboards.kb_confirm())


async def save_contact(ctx: Ctx, user: dict, text: str) -> Reply:
    vk_id = user["vk_id"]
    contact = (text or "").strip()[:120]
    notes = []
    if user.get("consent_pd"):
        ctx.leads.update_draft_contact(vk_id, contact)
    else:
        # Без согласия контакт не сохраняем — ни в черновик, ни в уведомление
        notes.append(ctx.texts["contact_not_saved"])
        contact = None
    draft = ctx.leads.get_draft(vk_id) or {}
    if contact is None:
        draft = {**draft, "contact": None}
    ctx.users.set_state(vk_id, CONFIRM)
    prefix = "\n\n".join(notes)
    text = (prefix + "\n\n" if prefix else "") + build_summary(ctx, user, draft)
    return Reply(text, keyboards.kb_confirm())


async def confirm_lead(ctx: Ctx, user: dict, payload: dict | None = None):
    vk_id = user["vk_id"]
    draft = ctx.leads.get_draft(vk_id)
    if draft is None:
        logger.warning("Подтверждение заявки без черновика от %s", vk_id)
        ctx.users.set_state(vk_id, MENU)
        return Reply(ctx.texts["error_generic"], keyboards.kb_menu())
    lead_id = ctx.lead_service.create_lead(vk_id)
    if lead_id is None:
        return Reply(ctx.texts["error_generic"], keyboards.kb_menu())
    ctx.users.set_state(vk_id, LEAD_CREATED)
    replies = [Reply(ctx.texts["lead_created"].format(id=lead_id), keyboards.kb_simple())]
    if ctx.admin_id:
        replies.append(
            Reply(ctx.lead_service.admin_lead_message(vk_id, draft, lead_id), peer_id=ctx.admin_id)
        )
    return replies


async def cancel_lead(ctx: Ctx, user: dict, payload: dict | None = None) -> Reply:
    vk_id = user["vk_id"]
    ctx.leads.delete_draft(vk_id)
    ctx.users.set_state(vk_id, MENU)
    return Reply(ctx.texts["cancel_lead"], keyboards.kb_menu())


async def request_manager(ctx: Ctx, user: dict, payload: dict | None = None):
    """Передача человеку: помечаем обращение и уведомляем менеджера."""
    vk_id = user["vk_id"]
    if user.get("current_state") == HANDOFF:
        # Запрос уже у менеджера: второй записи и второго уведомления не нужно
        return Reply(ctx.texts["handoff_already"], keyboards.kb_simple())
    segment = user.get("segment")
    service = user.get("selected_service")
    lead_id = ctx.lead_service.create_handoff(vk_id, segment, service)
    ctx.users.set_state(vk_id, HANDOFF)
    replies = [Reply(ctx.texts["handoff_user"], keyboards.kb_simple())]
    if ctx.admin_id:
        replies.append(
            Reply(ctx.lead_service.admin_handoff_message(vk_id, segment, service), peer_id=ctx.admin_id)
        )
    logger.info("Handoff для %s создан (lead_id=%s)", vk_id, lead_id)
    return replies
