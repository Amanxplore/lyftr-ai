from typing import Any

from app.core.config import Settings
from app.core.exceptions import SessionNotFoundError
from app.database.repository import ChatRepository
from app.schemas.session import (
    AssistantMessageItem,
    SessionMessageItem,
    SessionMessagesResponse,
    StoredMessageMetadata,
    UserMessageItem,
)


class SessionService:
    """Manages multi-turn conversation state and SQLite persistence."""

    def __init__(self, repository: ChatRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def build_llm_messages(
        self,
        session_id: str,
        user_message: str,
        override_system_prompt: str | None = None,
    ) -> tuple[list[dict[str, str]], str]:
        """
        Build the full message list [system, ...history, new_user] for LiteLLM.

        Returns (messages, effective_system_prompt).
        """
        stored_prompt = self.repository.get_session_system_prompt(session_id)
        effective_system_prompt = (
            override_system_prompt
            or stored_prompt
            or self.settings.default_system_prompt
        )

        history = self.repository.get_messages(session_id)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": effective_system_prompt}
        ]
        for record in history:
            messages.append({"role": record.role, "content": record.content})
        messages.append({"role": "user", "content": user_message})

        return messages, effective_system_prompt

    def save_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_reply: str,
        metadata: dict[str, Any],
        override_system_prompt: str | None = None,
    ) -> None:
        """Persist a completed user + assistant turn to SQLite."""
        self.repository.save_exchange(
            session_id=session_id,
            user_content=user_message,
            assistant_content=assistant_reply,
            assistant_metadata=metadata,
            system_prompt=override_system_prompt,
        )

    def get_session_messages(self, session_id: str) -> SessionMessagesResponse:
        """Return oldest-first stored history without system prompt, or raise 404."""
        records = self.repository.get_messages(session_id)
        if not records:
            raise SessionNotFoundError()

        items: list[SessionMessageItem] = []
        for record in records:
            if record.role == "user":
                items.append(UserMessageItem(role="user", content=record.content))
            else:
                meta = record.metadata or {}
                items.append(
                    AssistantMessageItem(
                        role="assistant",
                        content=record.content,
                        metadata=StoredMessageMetadata(
                            resolution_source=meta.get(
                                "resolution_source", "LIVE_INFERENCE"
                            ),
                            input_tokens=int(meta.get("input_tokens", 0)),
                            output_tokens=int(meta.get("output_tokens", 0)),
                            model=meta.get("model"),
                            latency_ms=meta.get("latency_ms"),
                            key_id=meta.get("key_id"),
                            fallback_attempts=meta.get("fallback_attempts"),
                        ),
                    )
                )

        return SessionMessagesResponse(session_id=session_id, messages=items)
