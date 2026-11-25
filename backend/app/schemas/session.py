from typing import Literal, Union
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response payload for GET /health."""

    status: str
    keys_configured: int
    cache_enabled: bool


class StoredMessageMetadata(BaseModel):
    """Metadata persisted alongside an assistant message."""

    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    input_tokens: int
    output_tokens: int
    model: str | None = None
    latency_ms: int | None = None
    key_id: str | None = None
    fallback_attempts: int | None = None


class UserMessageItem(BaseModel):
    """User turn item returned by GET /sessions/{session_id}/messages."""

    role: Literal["user"]
    content: str


class AssistantMessageItem(BaseModel):
    """Assistant turn item returned by GET /sessions/{session_id}/messages."""

    role: Literal["assistant"]
    content: str
    metadata: StoredMessageMetadata


SessionMessageItem = Union[UserMessageItem, AssistantMessageItem]


class SessionMessagesResponse(BaseModel):
    """Response payload for GET /sessions/{session_id}/messages."""

    session_id: str
    messages: list[SessionMessageItem]
