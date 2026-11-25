import asyncio
import logging
import time
from typing import Any

import litellm

from app.core.config import KeyEntry, Settings
from app.core.exceptions import BadRequestError, ProvidersUnavailableError
from app.schemas.chat import ChatMetadata, ChatRequest, ChatResponse
from app.services.cache_service import is_cache_hit
from app.services.failover_service import (
    build_simulated_exception,
    get_simulated_status,
    is_retryable_error,
    parse_simulated_failures,
)
from app.services.session_service import SessionService
from app.services.token_service import extract_token_usage

logger = logging.getLogger(__name__)


class LLMService:
    """Executes chat completions via LiteLLM with key failover, caching, and token tracking."""

    def __init__(
        self,
        settings: Settings,
        session_service: SessionService,
        key_pool: list[KeyEntry],
    ) -> None:
        self.settings = settings
        self.session_service = session_service
        self.key_pool = key_pool

    async def generate_reply(
        self,
        request: ChatRequest,
        simulate_failure_header: str | None = None,
    ) -> ChatResponse:
        """
        Run multi-turn completion through LiteLLM with cache lookup and key failover.

        Persists the turn in SQLite only after a valid reply is obtained.
        """
        if not self.key_pool:
            raise ProvidersUnavailableError()

        start_ns = time.perf_counter_ns()
        messages, _ = self.session_service.build_llm_messages(
            session_id=request.session_id,
            user_message=request.message,
            override_system_prompt=request.system_prompt,
        )

        simulated_failures = parse_simulated_failures(
            header_value=simulate_failure_header,
            simulation_enabled=self.settings.enable_failure_simulation,
        )
        bypass_cache = bool(simulated_failures)

        fallback_attempts = 0
        last_error: Exception | None = None

        for key_entry in self.key_pool:
            simulated_status = get_simulated_status(simulated_failures, key_entry.key_id)
            if simulated_status is not None:
                fallback_attempts += 1
                last_error = build_simulated_exception(
                    status_code=simulated_status,
                    model=key_entry.model,
                    key_id=key_entry.key_id,
                )
                logger.warning(
                    "Simulated provider failure on %s with status %d (model=%s)",
                    key_entry.key_id,
                    simulated_status,
                    key_entry.model,
                )
                continue

            try:
                completion_kwargs: dict[str, Any] = {
                    "model": key_entry.model,
                    "messages": messages,
                    "api_key": key_entry.api_key,
                    "timeout": self.settings.llm_timeout_seconds,
                    "temperature": self.settings.llm_temperature,
                }
                if self.settings.cache_enabled and bypass_cache:
                    completion_kwargs["cache"] = {"no-cache": True, "no-store": True}

                response = await litellm.acompletion(**completion_kwargs)
                reply_text = self._extract_reply_text(response)
                if not reply_text:
                    raise litellm.InternalServerError(
                        message=f"Empty completion content from {key_entry.key_id}",
                        llm_provider=key_entry.model.split("/", 1)[0],
                        model=key_entry.model,
                    )

                cache_hit = False if bypass_cache else is_cache_hit(response)
                if self.settings.cache_enabled and not bypass_cache and not cache_hit:
                    # Yield one event-loop tick so LiteLLM's background async_set_cache
                    # task completes before returning the response to back-to-back callers.
                    await asyncio.sleep(0)
                resolution_source = "LLM_CACHE" if cache_hit else "LIVE_INFERENCE"
                answering_model = key_entry.model

                input_tokens, output_tokens = extract_token_usage(
                    response=response,
                    model=answering_model,
                    messages=messages,
                    reply_text=reply_text,
                )
                latency_ms = max(
                    0,
                    round((time.perf_counter_ns() - start_ns) / 1_000_000),
                )

                metadata = ChatMetadata(
                    resolution_source=resolution_source,
                    model=answering_model,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    key_id=None if cache_hit else key_entry.key_id,
                    fallback_attempts=0 if cache_hit else fallback_attempts,
                )

                self.session_service.save_turn(
                    session_id=request.session_id,
                    user_message=request.message,
                    assistant_reply=reply_text,
                    metadata=metadata.model_dump(),
                    override_system_prompt=request.system_prompt,
                )

                return ChatResponse(
                    session_id=request.session_id,
                    reply=reply_text,
                    metadata=metadata,
                )

            except BadRequestError:
                raise
            except litellm.BadRequestError as exc:
                if is_retryable_error(exc):
                    fallback_attempts += 1
                    last_error = exc
                    logger.warning(
                        "Retryable BadRequest/quota error on %s (%s); failing over",
                        key_entry.key_id,
                        type(exc).__name__,
                    )
                    continue
                raise BadRequestError(detail="invalid chat request") from exc
            except Exception as exc:
                if is_retryable_error(exc):
                    fallback_attempts += 1
                    last_error = exc
                    logger.warning(
                        "Provider failure on %s (%s); failing over to next key",
                        key_entry.key_id,
                        type(exc).__name__,
                    )
                    continue
                fallback_attempts += 1
                last_error = exc
                logger.warning(
                    "Unexpected provider error on %s (%s); failing over to next key",
                    key_entry.key_id,
                    type(exc).__name__,
                )
                continue

        logger.error(
            "All %d configured keys failed (last error type: %s)",
            len(self.key_pool),
            type(last_error).__name__ if last_error else "None",
        )
        raise ProvidersUnavailableError()

    @staticmethod
    def _extract_reply_text(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None:
            return ""
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if not isinstance(content, str):
            return ""
        return content.strip()
