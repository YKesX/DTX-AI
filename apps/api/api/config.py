"""Application settings loaded from environment / .env file."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    anomaly_threshold: float = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dtx_ai.db")
    ai_debug: bool = os.getenv("AI_DEBUG", "false").lower() == "true"

    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
