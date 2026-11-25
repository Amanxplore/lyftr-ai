from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Request payload for POST /chat."""

    session_id: str
    message: str
    system_prompt: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("session_id must be a string")
        if not value.strip():
            raise ValueError("session_id must not be empty")
        if len(value) > 128:
            raise ValueError("session_id must be at most 128 characters")
        return value

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("message must be a string")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message must be between 1 and 4000 characters after trimming")
        if len(trimmed) > 4000:
            raise ValueError("message must be at most 4000 characters after trimming")
        return trimmed

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 4000:
            raise ValueError("system_prompt must be at most 4000 characters")
        return trimmed


class ChatMetadata(BaseModel):
    """Per-request inference/cache metadata returned with POST /chat."""

    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    key_id: str | None
    fallback_attempts: int = Field(ge=0)


class ChatResponse(BaseModel):
    """Response payload for POST /chat."""

    session_id: str
    reply: str
    metadata: ChatMetadata
