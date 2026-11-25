from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MessageRecord:
    """Internal representation of a row in the messages table."""

    id: int
    session_id: str
    role: str
    content: str
    metadata: dict[str, Any] | None
    created_at: str
