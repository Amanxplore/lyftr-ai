import json
from datetime import datetime, timezone
from typing import Any

from app.database.connection import DatabaseManager
from app.database.models import MessageRecord


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatRepository:
    """Data access layer for chat sessions and messages in SQLite."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def get_session_system_prompt(self, session_id: str) -> str | None:
        """Return stored custom system prompt for a session, if any."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row["system_prompt"] if row else None

    def session_exists(self, session_id: str) -> bool:
        """Return True if session has at least one persisted message."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            return row is not None

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        """Return all persisted messages for a session ordered oldest first."""
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, metadata, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

        records: list[MessageRecord] = []
        for row in rows:
            raw_meta = row["metadata"]
            parsed_meta: dict[str, Any] | None = (
                json.loads(raw_meta) if raw_meta else None
            )
            records.append(
                MessageRecord(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    metadata=parsed_meta,
                    created_at=row["created_at"],
                )
            )
        return records

    def save_exchange(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        assistant_metadata: dict[str, Any],
        system_prompt: str | None = None,
    ) -> None:
        """Persist a completed user + assistant turn atomically."""
        now_user = _utc_now_iso()
        now_assistant = _utc_now_iso()
        serialized_meta = json.dumps(assistant_metadata, ensure_ascii=False)

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, system_prompt, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    system_prompt = COALESCE(excluded.system_prompt, sessions.system_prompt),
                    updated_at = excluded.updated_at
                """,
                (session_id, system_prompt, now_user, now_assistant),
            )
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'user', ?, NULL, ?)
                """,
                (session_id, user_content, now_user),
            )
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'assistant', ?, ?, ?)
                """,
                (session_id, assistant_content, serialized_meta, now_assistant),
            )
