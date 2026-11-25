import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("app.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs HTTP method, path, status code, and duration without leaking secrets."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_ns = time.perf_counter_ns()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000)

        logger.info(
            "%s %s -> %s (%d ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": elapsed_ms,
                }
            },
        )
        return response
