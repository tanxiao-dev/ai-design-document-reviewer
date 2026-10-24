import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str = "gpt-4o-mini"
    max_file_size_bytes: int = 10 * 1024 * 1024
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    @property
    def demo_mode(self) -> bool:
        return not bool(self.openai_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_DIR / ".env")
        api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
        return cls(openai_api_key=api_key, openai_model=model)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
