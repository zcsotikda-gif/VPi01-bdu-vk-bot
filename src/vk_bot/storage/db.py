"""SQLite: подключение, схема и простые помощники запросов.

Используется одно соединение с защёлкой: бот обрабатывает единицы сообщений
в минуту, пул соединений был бы лишней сложностью.
"""

import logging
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("vk_bot.storage")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    vk_id INTEGER PRIMARY KEY,
    first_name TEXT,
    segment TEXT,
    current_state TEXT,
    selected_service TEXT,
    consent_pd INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vk_id INTEGER,
    segment TEXT,
    service TEXT,
    problem TEXT,
    expected_result TEXT,
    deadline TEXT,
    contact TEXT,
    status TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    processed_at DATETIME
);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        with self._lock:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor

    def query_one(self, sql: str, params: tuple = ()):
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
