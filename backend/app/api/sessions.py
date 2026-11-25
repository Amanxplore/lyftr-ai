from fastapi import APIRouter, Request

from app.schemas.session import SessionMessagesResponse

router = APIRouter()


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(
    session_id: str,
    request: Request,
) -> SessionMessagesResponse:
    """Return oldest-first stored history for one session from SQLite."""
    session_service = request.app.state.session_service
    return session_service.get_session_messages(session_id=session_id)
