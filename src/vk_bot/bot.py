"""Сборка приложения: хранилище, сервисы, роутер."""

from dataclasses import dataclass

from vk_bot.router import UpdateProcessor
from vk_bot.services.catalog_service import CatalogService
from vk_bot.services.lead_service import LeadService
from vk_bot.services.llm_service import LLMService
from vk_bot.services.vk_service import VKService
from vk_bot.storage.db import Database
from vk_bot.storage.repository import EventsRepository, LeadsRepository, UsersRepository


@dataclass
class App:
    db: Database
    processor: UpdateProcessor
    vk: VKService
    catalog: CatalogService


def create_app(settings, api=None) -> App:
    """Создать приложение. api — vkbottle API (в тестах остаётся None)."""
    db = Database(settings.DB_PATH)
    users = UsersRepository(db)
    leads = LeadsRepository(db)
    events = EventsRepository(db)

    catalog = CatalogService()
    llm = LLMService(settings, catalog)
    vk = VKService(api, admin_id=settings.ADMIN_VK_ID)
    lead_service = LeadService(leads, catalog.texts, catalog)

    processor = UpdateProcessor(
        users=users,
        leads=leads,
        events=events,
        lead_service=lead_service,
        catalog=catalog,
        llm=llm,
        texts=catalog.texts,
        get_user_name=vk.get_user_first_name,
        admin_id=settings.ADMIN_VK_ID,
    )
    return App(db=db, processor=processor, vk=vk, catalog=catalog)
