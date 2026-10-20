"""Загрузка конфигурации.

Секреты — только из окружения (.env через python-dotenv).
Несекретные настройки LLM и логирования — из config.yaml,
их можно переопределить переменными окружения.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# .env и config.yaml ищутся в рабочем каталоге (запуск из корня проекта):
# после установки пакета __file__ указывает в src/ или site-packages
_BASE_DIR = Path.cwd()

# Load environment variables from .env file in the working directory
load_dotenv(dotenv_path=_BASE_DIR / ".env")


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


class Settings:
    """Global configuration holder.

    Секреты (токены, ключи) берутся из окружения; несекретные настройки —
    из YAML, но каждое из них можно переопределить переменной окружения.
    """

    def __init__(self, cfg_path: str | Path = "config.yaml") -> None:
        cfg = Path(cfg_path)
        self.cfg_path = cfg if cfg.is_absolute() else _BASE_DIR / cfg
        self.reload()

    def reload(self) -> None:
        """Перечитать .env и YAML. Обновляет атрибуты и timestamp."""

        # --- Секреты из окружения -----------------------------------------
        # Старые имена (VK_TOKEN / OPENAI_API_KEY) оставлены для совместимости
        self.VK_TOKEN = os.getenv("VK_GROUP_TOKEN") or os.getenv("VK_TOKEN")
        self.LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.VK_GROUP_ID = os.getenv("VK_GROUP_ID")
        self.ADMIN_VK_ID = _int_or_none(os.getenv("ADMIN_VK_ID"))
        self.DB_PATH = os.getenv("DB_PATH") or "data/bot.db"

        # --- Несекретные настройки из YAML (с переопределением из env) ----
        if self.cfg_path.exists():
            with open(self.cfg_path, encoding="utf-8") as f:
                cfg: dict[str, Any] = yaml.safe_load(f) or {}
        else:
            cfg = {}

        self.ai_provider: str = os.getenv("AI_PROVIDER") or cfg.get("ai_provider", "local")
        self.base_url: str = os.getenv("LLM_BASE_URL") or cfg.get(
            "base_url", "http://127.0.0.1:1234"
        )
        self.model_id: str = os.getenv("LLM_MODEL_ID") or cfg.get(
            "model_id", "773a7da77e569019bb0fd17a554b263738d669a3"
        )
        self.log_level: str = str(
            os.getenv("LOG_LEVEL") or cfg.get("log_level", "INFO")
        ).upper()

        self.timestamp = datetime.now(UTC)

    def missing_required(self) -> list[str]:
        """Список обязательных переменных, которых не хватает."""
        missing = []
        if not self.VK_TOKEN:
            missing.append("VK_GROUP_TOKEN")
        if not self.LLM_API_KEY and self.ai_provider != "local":
            missing.append("LLM_API_KEY")
        return missing

    def __repr__(self) -> str:
        return (
            f"Settings(provider={self.ai_provider!r}, base_url={self.base_url!r}, "
            f"model_id={self.model_id!r})"
        )


# A single global instance that can be imported throughout the app.
settings = Settings()
