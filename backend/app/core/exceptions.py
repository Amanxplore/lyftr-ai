class AppError(Exception):
    """Base application exception mapped to a clean JSON error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ProvidersUnavailableError(AppError):
    """Raised when every configured LLM API key fails."""

    def __init__(self, detail: str = "all providers unavailable") -> None:
        super().__init__(status_code=503, detail=detail)


class SessionNotFoundError(AppError):
    """Raised when querying an unknown session id."""

    def __init__(self, detail: str = "session not found") -> None:
        super().__init__(status_code=404, detail=detail)


class BadRequestError(AppError):
    """Raised for non-retryable invalid provider/request payloads."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)
