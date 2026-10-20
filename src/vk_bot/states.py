"""Состояния диалога.

Хранятся в users.current_state. Шаг квалификации кодируется суффиксом
("qualification:2"), чтобы не плодить отдельные колонки и таблицы.
"""

NEW = "new"                      # пользователь написал впервые, ещё не поздоровались
MENU = "menu"                    # главное меню
SEGMENT = "segment"              # выбран сегмент, показываем потребности
SERVICE = "service"              # показана рекомендация услуги
QUALIFICATION = "qualification"  # идёт квалификация, шаг в суффиксе
CONSENT = "consent"              # ждём согласия на обработку контактных данных
CONTACT = "contact"              # ждём контакт для связи
CONFIRM = "confirm"              # показан итог, ждём подтверждения заявки
LEAD_CREATED = "lead_created"    # заявка отправлена
HANDOFF = "handoff"              # передано менеджеру
FREE_ASK = "free_ask"            # пользователь в режиме свободного вопроса

QUALIFICATION_QUESTIONS = 3

# Состояния без шага квалификации; шаги проверяет qualification_step()
KNOWN = {NEW, MENU, SEGMENT, SERVICE, CONSENT, CONTACT, CONFIRM, LEAD_CREATED, HANDOFF, FREE_ASK}


def is_known(state: str | None) -> bool:
    return state in KNOWN or qualification_step(state) is not None


def qualification_state(step: int) -> str:
    return f"{QUALIFICATION}:{step}"


def qualification_step(state: str | None) -> int | None:
    """Вернуть номер шага квалификации или None, если состояние другое."""
    if not state or not state.startswith(QUALIFICATION + ":"):
        return None
    try:
        return int(state.split(":", 1)[1])
    except ValueError:
        return None
