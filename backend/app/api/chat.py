from fastapi import APIRouter, Header, Request

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    payload: ChatRequest,
    request: Request,
    x_simulate_failure: str | None = Header(default=None, alias="X-Simulate-Failure"),
) -> ChatResponse:
    """Process a multi-turn chat message with LiteLLM failover and response caching."""
    llm_service = request.app.state.llm_service
    return await llm_service.generate_reply(
        request=payload,
        simulate_failure_header=x_simulate_failure,
    )
