---
paths:
  - "src/vk_bot/services/llm_service.py"
  - "src/vk_bot/llm_client.py"
  - "src/vk_bot/handlers/free_text.py"
  - "src/vk_bot/knowledge/llm_system_prompt.md"
  - "src/vk_bot/knowledge/faq.md"
---

# Граница LLM

- LLM отвечает только на свободные вопросы, объясняет услуги, FAQ и первично
  толкует описанную задачу. Меню, команды, состояние, согласие, контакт, lead и
  handoff — код на Python; ответ модели их не меняет и не выбирает.
- `LLMService` не импортирует `storage` и не вызывает `users.set_*`.
- Вход модели: сегмент, выбранная услуга, каталог из `services.json`, FAQ,
  вопрос. Вопрос проходит `redact()` (email → `[EMAIL]`, телефон → `[PHONE]`).
- Полный prompt и ответ модели не логировать — только длину.
- Сбой модели → одно исключение `LLMUnavailable` → запасной текст
  `llm_unavailable` с кнопками Услуги / Менеджер / Меню.
- Ответ — 1–4 коротких абзаца; режется по `MAX_REPLY_LENGTH`.
- System prompt правится только в `llm_system_prompt.md`; правила 1–16 из
  задания не удалять. Цены и сроки — только из каталога, пустые не упоминать.
- Новое поведение — тест с фейковым клиентом (`SupportTests` в `tests/test_flow.py`).
