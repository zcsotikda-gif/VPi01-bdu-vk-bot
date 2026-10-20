"""Один экземпляр бота на машине.

Две копии на одном Group Long Poll отвечают пользователю дважды и пишут
состояние vkbottle в один файл — так 20.10.2026 бот перестал получать события.
Блокировка flock снимается ядром при завершении процесса, даже аварийном.
"""

import fcntl
from pathlib import Path
from typing import IO


def acquire_instance_lock(path: str | Path) -> IO | None:
    """Захватить блокировку. Файл держать открытым до выхода; None — уже занято."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w")  # без with: файл живёт до конца процесса
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle
