import os
from pathlib import Path
from types import SimpleNamespace
import sys

# Ensure module-level app initialization in app.main does not try to touch
# Docker's /data volume or local .env during test collection.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("LLM_API_KEYS", "sk-test-key-one,sk-test-key-two")

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings


def make_test_settings(tmp_path: Path, **overrides) -> Settings:
    """Create isolated Settings backed by a temporary SQLite file."""
    db_file = tmp_path / "test_app.db"
    defaults = {
        "llm_api_keys": "sk-test-key-one,sk-test-key-two",
        "llm_model": "gemini/gemini-2.0-flash",
        "llm_models": "",
        "database_url": f"sqlite:///{db_file}",
        "allowed_origins": "http://localhost:3000",
        "enable_failure_simulation": True,
        "cache_enabled": True,
        "cache_type": "local",
        "cache_disk_dir": str(tmp_path / "litellm_cache"),
        "default_system_prompt": "You are a helpful test assistant.",
        "llm_timeout_seconds": 10.0,
        "llm_temperature": 0.0,
        "log_level": "WARNING",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def make_litellm_response(
    content: str = "The capital of France is Paris.",
    model: str = "gemini/gemini-2.0-flash",
    prompt_tokens: int = 42,
    completion_tokens: int = 9,
    cache_hit: bool = False,
):
    """Build a LiteLLM-shaped completion response object for unit tests."""
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, role="assistant")
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        _hidden_params={"cache_hit": cache_hit},
    )


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return make_test_settings(tmp_path)
