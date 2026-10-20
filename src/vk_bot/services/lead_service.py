"""Lead-сервис: создание заявки и уведомление менеджера."""

import logging

from vk_bot.storage.repository import LeadsRepository

logger = logging.getLogger("vk_bot.leads")


def _segment_label(segment: str | None) -> str:
    return {"person": "Для себя", "business": "Для бизнеса"}.get(segment or "", "—")


class LeadService:
    def __init__(self, leads: LeadsRepository, texts: dict, catalog=None):
        self.leads = leads
        self.texts = texts
        self.catalog = catalog

    # ------------------------------------------------------------- создание
    def create_lead(self, vk_id: int) -> int | None:
        """Подтвердить черновик и вернуть номер заявки."""
        lead_id = self.leads.promote_draft(vk_id)
        if lead_id is None:
            logger.error("Не найден черновик заявки для %s", vk_id)
            return None
        logger.info("Создана заявка №%s (vk_id=%s)", lead_id, vk_id)
        return lead_id

    def create_handoff(self, vk_id: int, segment: str | None, service: str | None) -> int:
        lead_id = self.leads.create_handoff(vk_id, segment, service)
        logger.info("Создан запрос менеджеру №%s (vk_id=%s)", lead_id, vk_id)
        return lead_id

    # ------------------------------------------------------- уведомления
    def admin_lead_message(self, vk_id: int, draft: dict, lead_id: int) -> str:
        service = self.catalog.get(draft.get("service")) if self.catalog else None
        service_title = service["title"] if service else "—"
        return self.texts["admin_lead_notify"].format(
            id=lead_id,
            vk_id=vk_id,
            segment=_segment_label(draft.get("segment")),
            service=service_title,
            problem=(draft.get("problem") or "—"),
            expected_result=(draft.get("expected_result") or "—"),
            deadline=(draft.get("deadline") or "—"),
            contact=(draft.get("contact") or "не указан"),
        )

    def admin_handoff_message(self, vk_id: int, segment: str | None, service: str | None) -> str:
        catalog_service = self.catalog.get(service) if self.catalog else None
        return self.texts["admin_handoff_notify"].format(
            vk_id=vk_id,
            segment=_segment_label(segment),
            service=catalog_service["title"] if catalog_service else "—",
        )
