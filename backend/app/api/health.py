from fastapi import APIRouter, Request

from app.core.exceptions import ProvidersUnavailableError
from app.schemas.session import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Return service readiness once DB is reachable and key pool is loaded."""
    db_manager = request.app.state.db_manager
    key_pool = request.app.state.key_pool
    cache_enabled = bool(request.app.state.cache_enabled)

    try:
        db_ok = db_manager.check_health()
    except Exception as exc:
        raise ProvidersUnavailableError(detail="database unavailable") from exc

    if not db_ok:
        raise ProvidersUnavailableError(detail="database unavailable")

    if not key_pool:
        raise ProvidersUnavailableError(detail="no API keys configured")

    return HealthResponse(
        status="ok",
        keys_configured=len(key_pool),
        cache_enabled=cache_enabled,
    )
