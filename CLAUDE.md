# CLAUDE.md

VK sales/consulting bot агентства ИИ-Апгрейд (vkbottle + Long Poll + SQLite).

## Правила

- Бизнес-логика детерминированная: меню, состояния, квалификация, lead'ы —
  обычный Python. **LLM не изменяет state** и не участвует в маршрутизации.
- Услуги и тексты — только в `src/vk_bot/knowledge/` (`services.json`, `faq.md`,
  `llm_system_prompt.md`, `texts.json`), не хардкодить в handlers.
- Токены и ключи — только через окружение (`.env`, см. `.env.example`).
  Никогда не коммитить `.env` и не писать секреты в код/логи/тесты.
- Основной storage — SQLite (`src/vk_bot/storage/`), источник истины. Все SQL —
  только в `repository.py`.
- Персональные контакты (телефон/email) не отправлять в LLM: проходят через
  `llm_service.redact`.
- Любое изменение сопровождается тестами в `tests/`; перед завершением
  зелёные `.venv/bin/pytest -q` и `.venv/bin/ruff check src tests`.
- Окружение — `.venv` на Homebrew Python 3.12, зависимости только в
  `pyproject.toml`. Запуск и тесты — из корня проекта: `.env`, `config.yaml`,
  `data/` ищутся в рабочем каталоге.
- Не добавлять архитектурную сложность без причины: без ORM, без DI-фреймворков,
  без отдельных слоёв ради слоёв.
- Копия бота на сообщество одна: две на одном Long Poll мешают друг другу
  (`instance_lock.py`). Живой запуск и чтение лога — скилл `bot-live`.
- Доработка закончена — скилл `bot-review` (три ревью и критерии готовности).
  Детали по LLM и экранам — `.claude/rules/`, тесты и ruff проверяет хук Stop.

## Структура

Пакет `src/vk_bot/`, запуск `.venv/bin/python -m vk_bot`.
`__main__.py` — точка входа (vkbottle-адаптер), `bot.py` — сборка зависимостей,
`config.py` — настройки. `router.py` — маршрутизация
(payload action / команда / состояние). `handlers/` — сценарии,
`services/` — VK/LLM/каталог/lead, `storage/` — SQLite,
`keyboards.py` — клавиатуры. `docker/` — образ и compose для pytest. Новый обработчик = функция
`(ctx, user, payload) -> Reply | list[Reply]` + запись в `ACTIONS`/`COMMANDS`.
