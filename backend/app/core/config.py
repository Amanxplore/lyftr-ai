from dataclasses import dataclass
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class KeyEntry:
    """Represents a configured API key slot in the failover pool."""

    key_id: str
    api_key: str
    model: str

    def __repr__(self) -> str:
        return f"KeyEntry(key_id={self.key_id!r}, model={self.model!r}, api_key='***')"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_keys: str = ""
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_models: str = ""
    database_url: str = "sqlite:///./data/app.db"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    enable_failure_simulation: bool = False
    cache_enabled: bool = True
    cache_type: str = "local"
    cache_disk_dir: str = "./data/litellm_cache"
    default_system_prompt: str = (
        "You are Lyftr AI, a helpful, accurate, and concise assistant."
    )
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.7
    log_level: str = "INFO"

    def get_key_pool(self) -> List[KeyEntry]:
        """Parse LLM_API_KEYS and optional LLM_MODELS into ordered KeyEntry items."""
        raw_keys = [k.strip() for k in self.llm_api_keys.split(",") if k.strip()]
        raw_models = [m.strip() for m in self.llm_models.split(",") if m.strip()]

        pool: List[KeyEntry] = []
        for idx, api_key in enumerate(raw_keys, start=1):
            if raw_models:
                model = (
                    raw_models[idx - 1]
                    if idx - 1 < len(raw_models)
                    else raw_models[-1]
                )
            else:
                model = self.llm_model.strip() or "gemini/gemini-2.0-flash"
            pool.append(
                KeyEntry(
                    key_id=f"key_{idx}",
                    api_key=api_key,
                    model=model,
                )
            )
        return pool

    def get_allowed_origins(self) -> List[str]:
        """Parse comma-separated CORS origins."""
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        return origins or ["http://localhost:3000"]

    def get_sqlite_path(self) -> str:
        """Convert SQLite DATABASE_URL into a filesystem path or ':memory:'."""
        url = self.database_url.strip()
        if not url.startswith("sqlite:///"):
            raise ValueError(
                f"Only SQLite DATABASE_URL is supported (got {url.split(':')[0]!r})"
            )
        path = url[len("sqlite:///") :]
        if not path:
            raise ValueError("SQLite DATABASE_URL path cannot be empty")
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
