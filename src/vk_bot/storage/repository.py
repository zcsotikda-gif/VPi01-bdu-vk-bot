"""Репозитории: весь SQL живёт здесь, handlers и router SQL не пишут."""

import logging
import sqlite3

from vk_bot.states import NEW
from vk_bot.storage.db import Database, utcnow

logger = logging.getLogger("vk_bot.storage")


class UsersRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, vk_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM users WHERE vk_id = ?", (vk_id,))

    def get_or_create(self, vk_id: int, first_name: str | None = None) -> dict:
        user = self.get(vk_id)
        if user is None:
            now = utcnow()
            self.db.execute(
                "INSERT INTO users (vk_id, first_name, current_state, consent_pd, created_at, updated_at)"
                " VALUES (?, ?, ?, 0, ?, ?)",
                (vk_id, first_name, NEW, now, now),
            )
            user = self.get(vk_id)
            logger.info("Создан профиль пользователя %s", vk_id)
            return user
        if first_name and not user.get("first_name"):
            self.set_first_name(vk_id, first_name)
            user["first_name"] = first_name
        return user

    def set_first_name(self, vk_id: int, first_name: str) -> None:
        self.db.execute(
            "UPDATE users SET first_name = ?, updated_at = ? WHERE vk_id = ?",
            (first_name, utcnow(), vk_id),
        )

    def set_state(self, vk_id: int, state: str) -> None:
        current = self.get(vk_id)
        if current is None:
            return
        if current.get("current_state") != state:
            logger.info("Состояние %s: %s -> %s", vk_id, current.get("current_state"), state)
        self.db.execute(
            "UPDATE users SET current_state = ?, updated_at = ? WHERE vk_id = ?",
            (state, utcnow(), vk_id),
        )

    def set_segment(self, vk_id: int, segment: str) -> None:
        self.db.execute(
            "UPDATE users SET segment = ?, updated_at = ? WHERE vk_id = ?",
            (segment, utcnow(), vk_id),
        )

    def set_service(self, vk_id: int, service_id: str | None) -> None:
        self.db.execute(
            "UPDATE users SET selected_service = ?, updated_at = ? WHERE vk_id = ?",
            (service_id, utcnow(), vk_id),
        )

    def set_consent(self, vk_id: int, value: bool) -> None:
        self.db.execute(
            "UPDATE users SET consent_pd = ?, updated_at = ? WHERE vk_id = ?",
            (1 if value else 0, utcnow(), vk_id),
        )

    def delete_user_data(self, vk_id: int) -> dict:
        """Удалить данные пользователя. Содержимое не логируется."""
        leads = self.db.execute("DELETE FROM leads WHERE vk_id = ?", (vk_id,)).rowcount
        users = self.db.execute("DELETE FROM users WHERE vk_id = ?", (vk_id,)).rowcount
        logger.info("Операция удаления данных: vk_id=%s, users=%s, leads=%s", vk_id, users, leads)
        return {"users": users, "leads": leads}


class LeadsRepository:
    """Lead'ы. Черновик (status='draft") живёт до подтверждения заявки."""

    DRAFT = "draft"
    NEW_LEAD = "new"
    HANDOFF = "handoff"

    def __init__(self, db: Database):
        self.db = db

    def get_draft(self, vk_id: int) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM leads WHERE vk_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
            (vk_id, self.DRAFT),
        )

    def save_draft(
        self,
        vk_id: int,
        segment: str | None,
        service: str | None,
        problem: str | None,
        expected_result: str | None,
        deadline: str | None,
        contact: str | None = None,
    ) -> None:
        """Черновик на пользователя всегда один: старый удаляем, пишем новый."""
        self.db.execute("DELETE FROM leads WHERE vk_id = ? AND status = ?", (vk_id, self.DRAFT))
        now = utcnow()
        self.db.execute(
            "INSERT INTO leads (vk_id, segment, service, problem, expected_result, deadline,"
            " contact, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vk_id, segment, service, problem, expected_result, deadline, contact, self.DRAFT, now, now),
        )

    def update_draft_contact(self, vk_id: int, contact: str) -> None:
        self.db.execute(
            "UPDATE leads SET contact = ?, updated_at = ? WHERE vk_id = ? AND status = ?",
            (contact, utcnow(), vk_id, self.DRAFT),
        )

    def promote_draft(self, vk_id: int) -> int | None:
        """Подтвердить черновик: перевести в status='new' и вернуть id."""
        draft = self.get_draft(vk_id)
        if draft is None:
            return None
        self.db.execute(
            "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
            (self.NEW_LEAD, utcnow(), draft["id"]),
        )
        return draft["id"]

    def create_handoff(self, vk_id: int, segment: str | None, service: str | None) -> int:
        now = utcnow()
        cursor = self.db.execute(
            "INSERT INTO leads (vk_id, segment, service, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (vk_id, segment, service, self.HANDOFF, now, now),
        )
        return cursor.lastrowid

    def delete_draft(self, vk_id: int) -> None:
        self.db.execute("DELETE FROM leads WHERE vk_id = ? AND status = ?", (vk_id, self.DRAFT))

    def count_by_status(self, vk_id: int, status: str) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS cnt FROM leads WHERE vk_id = ? AND status = ?", (vk_id, status)
        )
        return int(row["cnt"]) if row else 0


class EventsRepository:
    """Дедупликация событий: одно событие обрабатывается один раз."""

    def __init__(self, db: Database):
        self.db = db

    def mark_processed(self, event_id: str) -> bool:
        """True — событие новое и помечено обработанным, False — уже было."""
        try:
            self.db.execute(
                "INSERT INTO processed_events (event_id, processed_at) VALUES (?, ?)",
                (event_id, utcnow()),
            )
            return True
        except sqlite3.IntegrityError:
            return False
