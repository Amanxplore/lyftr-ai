import logging
from typing import Any

import litellm

from app.core.config import Settings

logger = logging.getLogger(__name__)


def configure_litellm_cache(settings: Settings) -> bool:
    """
    Initialize LiteLLM's built-in response cache via litellm.enable_cache().

    Returns True if caching is enabled, False otherwise.
    """
    if not settings.cache_enabled:
        if hasattr(litellm, "disable_cache"):
            litellm.disable_cache()
        else:
            litellm.cache = None
        logger.info("LiteLLM response caching disabled")
        return False

    litellm.cache = None
    cache_type = settings.cache_type.strip().lower()
    if cache_type != "local":
        logger.warning(
            "LiteLLM cache_type=%r is unsupported in this runtime; using built-in 'local' cache",
            settings.cache_type,
        )

    litellm.enable_cache(type="local")
    logger.info("LiteLLM in-memory local cache enabled")
    return True


def is_cache_hit(response: Any) -> bool:
    """Return True if LiteLLM served this response from its built-in cache."""
    hidden_params = getattr(response, "_hidden_params", None)
    if isinstance(hidden_params, dict):
        return bool(hidden_params.get("cache_hit", False))
    return False
