"""Application settings modeled via Pydantic."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    database_url: str = Field("sqlite:////data/observatory.db", alias="DATABASE_URL")
    ai_ocr_enabled: bool = Field(False, alias="AI_OCR_ENABLED")
    ai_ocr_model: str = Field("gpt-4o-mini", alias="AI_OCR_MODEL")
    ai_ocr_rate_limit_delay: int = Field(12, alias="AI_OCR_RATE_LIMIT_DELAY")
    screenshot_timezone: str = Field("America/New_York", alias="SCREENSHOT_TIMEZONE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def ensure_data_dir() -> None:
    """Create the parent directory for sqlite databases when needed."""
    if not settings.database_url.startswith("sqlite"):
        return
    url = make_url(settings.database_url)
    if not url.database:
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
