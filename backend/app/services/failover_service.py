import logging
from typing import Dict

import litellm

logger = logging.getLogger(__name__)

VALID_SIMULATED_STATUSES = {429, 500, 502, 503}


def parse_simulated_failures(
    header_value: str | None,
    simulation_enabled: bool,
) -> Dict[str, int]:
    """
    Parse X-Simulate-Failure header into a map of key_id (or '*') -> status code.

    Only honored when ENABLE_FAILURE_SIMULATION=true.
    Example: 'key_1=429,key_2=500' or '*=429'
    """
    if not simulation_enabled or not header_value:
        return {}

    parsed: Dict[str, int] = {}
    for raw_pair in header_value.split(","):
        pair = raw_pair.strip()
        if not pair or "=" not in pair:
            continue
        key_part, status_part = pair.split("=", 1)
        key_id = key_part.strip()
        try:
            status_code = int(status_part.strip())
        except ValueError:
            continue
        if key_id and status_code in VALID_SIMULATED_STATUSES:
            parsed[key_id] = status_code
    return parsed


def get_simulated_status(
    simulated_failures: Dict[str, int],
    key_id: str,
) -> int | None:
    """Return simulated failure HTTP status for key_id, or None if not simulated."""
    if key_id in simulated_failures:
        return simulated_failures[key_id]
    if "*" in simulated_failures:
        return simulated_failures["*"]
    return None


def build_simulated_exception(
    status_code: int,
    model: str,
    key_id: str,
) -> Exception:
    """Create a LiteLLM-compatible exception representing a simulated failure."""
    provider = model.split("/", 1)[0] if "/" in model else "unknown"
    msg = f"Simulated {status_code} failure for {key_id}"
    if status_code == 429:
        return litellm.RateLimitError(
            message=msg,
            llm_provider=provider,
            model=model,
        )
    if status_code == 502:
        return litellm.BadGatewayError(
            message=msg,
            llm_provider=provider,
            model=model,
        )
    if status_code == 503:
        return litellm.ServiceUnavailableError(
            message=msg,
            llm_provider=provider,
            model=model,
        )
    return litellm.InternalServerError(
        message=msg,
        llm_provider=provider,
        model=model,
    )


def is_retryable_error(exc: Exception) -> bool:
    """
    Return True when an exception represents a key/provider failure that should
    trigger automatic failover to the next configured key.
    """
    retryable_types = (
        litellm.RateLimitError,
        litellm.ServiceUnavailableError,
        litellm.InternalServerError,
        litellm.BadGatewayError,
        litellm.APIConnectionError,
        litellm.Timeout,
        litellm.AuthenticationError,
        litellm.PermissionDeniedError,
    )
    if isinstance(exc, retryable_types):
        return True

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and (
        status_code == 429 or status_code >= 500 or status_code in (401, 403)
    ):
        return True

    lowered = str(exc).lower()
    if any(
        token in lowered
        for token in (
            "rate limit",
            "ratelimit",
            "quota",
            "429",
            "resource exhausted",
            "service unavailable",
            "503",
            "502",
            "500",
            "overloaded",
            "timeout",
        )
    ):
        return True

    return False
