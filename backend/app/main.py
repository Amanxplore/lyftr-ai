import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.database.connection import DatabaseManager
from app.database.repository import ChatRepository
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.cache_service import configure_litellm_cache
from app.services.llm_service import LLMService
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    db_manager = DatabaseManager(app_settings.get_sqlite_path())
    db_manager.init_db()

    key_pool = app_settings.get_key_pool()
    cache_enabled = configure_litellm_cache(app_settings)

    repository = ChatRepository(db_manager)
    session_service = SessionService(repository=repository, settings=app_settings)
    llm_service = LLMService(
        settings=app_settings,
        session_service=session_service,
        key_pool=key_pool,
    )

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        logger.info(
            "Starting Lyftr AI backend (keys_configured=%d, cache_enabled=%s, failure_simulation=%s)",
            len(key_pool),
            cache_enabled,
            app_settings.enable_failure_simulation,
        )
        yield
        db_manager.close()

    app = FastAPI(
        title="Lyftr AI Chatbot API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    app.state.settings = app_settings
    app.state.db_manager = db_manager
    app.state.key_pool = key_pool
    app.state.cache_enabled = cache_enabled
    app.state.repository = repository
    app.state.session_service = session_service
    app.state.llm_service = llm_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error"},
        )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)

    return app


app = create_app()
