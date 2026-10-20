"""Каталог услуг и знания: services.json, FAQ, system prompt, тексты.

Handlers получают данные об услугах только через CatalogService —
услуги нигде не захардкожены.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("vk_bot.catalog")

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

REQUIRED_FIELDS = ("title", "audience", "short_description", "result")


class CatalogService:
    def __init__(self, knowledge_dir: str | Path = KNOWLEDGE_DIR):
        self.knowledge_dir = Path(knowledge_dir)

        data = json.loads((self.knowledge_dir / "services.json").read_text(encoding="utf-8"))
        self._needs: dict[str, list[dict]] = data.get("needs", {})
        self._services: dict[str, dict] = {}
        for service_id, service in (data.get("services") or {}).items():
            missing = [field for field in REQUIRED_FIELDS if not service.get(field)]
            if missing:
                logger.error("Услуга %s пропущена: нет полей %s", service_id, ", ".join(missing))
                continue
            service = dict(service)
            service["id"] = service_id
            self._services[service_id] = service

        self._faq: list[tuple[str, str]] = self._load_faq(self.knowledge_dir / "faq.md")
        self.system_prompt_text: str = (
            self.knowledge_dir / "llm_system_prompt.md"
        ).read_text(encoding="utf-8").strip()
        self.texts: dict = json.loads(
            (self.knowledge_dir / "texts.json").read_text(encoding="utf-8")
        )

    # ------------------------------------------------------------------ FAQ
    @staticmethod
    def _load_faq(path: Path) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        question: str | None = None
        answer_lines: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if question is not None:
                    entries.append((question, "\n".join(answer_lines).strip()))
                question = line[3:].strip()
                answer_lines = []
            elif question is not None:
                answer_lines.append(line)
        if question is not None:
            entries.append((question, "\n".join(answer_lines).strip()))
        return entries

    def faq_entries(self) -> list[tuple[str, str]]:
        return list(self._faq)

    # ------------------------------------------------------------- услуги
    def list_services(self) -> list[dict]:
        return list(self._services.values())

    def get(self, service_id: str | None) -> dict | None:
        if not service_id:
            return None
        return self._services.get(service_id)

    def needs(self, segment: str | None) -> list[dict]:
        return list(self._needs.get(segment or "", []))

    def need_by_title(self, segment: str | None, title: str) -> dict | None:
        normalized = (title or "").strip().lower()
        for need in self.needs(segment):
            if need["title"].strip().lower() == normalized:
                return need
        return None

    def services_for_need(self, need_id: str) -> list[dict]:
        for need in self._needs.values():
            for item in need:
                if item["id"] == need_id:
                    return [s for s in (self.get(sid) for sid in item["services"]) if s]
        return []

    # ------------------------------------------------------------ вывод
    def format_card(self, service: dict, detailed: bool = False) -> str:
        """Карточка услуги. Цена и срок выводятся только если заполнены."""
        lines = [service["title"], f"Для кого: {service['audience']}", f"Что решаем: {service['short_description']}", f"Что получаете: {service['result']}"]
        price = (service.get("price_from") or "").strip()
        if price:
            lines.append(f"Стоимость: от {price}")
        duration = (service.get("duration_text") or "").strip()
        if duration:
            lines.append(f"Срок: {duration}")
        if detailed:
            questions = service.get("questions") or []
            if questions:
                lines.append("Что уточню при разборе:")
                lines.extend(f"— {q}" for q in questions)
        return "\n".join(lines)

    def format_list(self) -> str:
        """Текстовый список услуг (для команд «услуги» и «цены»)."""
        lines = []
        for service in self._services.values():
            line = f"• {service['title']} — {service['short_description']}"
            price = (service.get("price_from") or "").strip()
            if price:
                line += f"\n  Стоимость: от {price}"
            lines.append(line)
        return "\n\n".join(lines)

    def has_any_price(self) -> bool:
        return any((s.get("price_from") or "").strip() for s in self._services.values())

    # ---------------------------------------------------- контекст для LLM
    def catalog_text(self) -> str:
        blocks = []
        for service in self._services.values():
            block = [f"### {service['id']} — {service['title']}", f"Для кого: {service['audience']}", f"Что решаем: {service['short_description']}", f"Результат для клиента: {service['result']}"]
            price = (service.get("price_from") or "").strip()
            block.append(f"Стоимость: от {price}" if price else "Стоимость: не указана — не упоминать")
            duration = (service.get("duration_text") or "").strip()
            block.append(f"Срок: {duration}" if duration else "Срок: не указан — не упоминать")
            blocks.append("\n".join(block))
        return "\n\n".join(blocks)

    def faq_text(self) -> str:
        return "\n\n".join(f"В: {q}\nО: {a}" for q, a in self._faq)
