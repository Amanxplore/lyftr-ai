import asyncio
import litellm
from fastapi.testclient import TestClient
from litellm.types.utils import Choices, Message, ModelResponse, Usage

from app.main import create_app
from tests.conftest import make_test_settings


def test_real_litellm_cache_hit_across_sessions_and_miss_on_different_message(
    tmp_path, monkeypatch
):
    settings = make_test_settings(
        tmp_path,
        llm_model="openai/gpt-4o-mini",
        cache_enabled=True,
        cache_type="local",
    )
    app = create_app(settings)

    provider_calls = 0

    async def fake_provider_acompletion(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        # Simulate real network latency on live inference so cache hit is strictly faster
        await asyncio.sleep(0.05)
        user_msg = kwargs["messages"][-1]["content"]
        reply = (
            "The capital of France is Paris."
            if "France" in user_msg
            else f"Answer to: {user_msg}"
        )
        return ModelResponse(
            id=f"chatcmpl-{provider_calls}",
            model="openai/gpt-4o-mini",
            choices=[
                Choices(
                    index=0,
                    message=Message(role="assistant", content=reply),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=38, completion_tokens=8, total_tokens=46),
        )

    monkeypatch.setattr(
        litellm.openai_chat_completions,
        "acompletion",
        fake_provider_acompletion,
    )

    with TestClient(app) as client:
        # 1. First request in session A -> LIVE_INFERENCE
        r1 = client.post(
            "/chat",
            json={
                "session_id": "s-cache-a",
                "message": "What is the capital of France?",
            },
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["reply"] == "The capital of France is Paris."
        assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert d1["metadata"]["model"] == "openai/gpt-4o-mini"
        assert d1["metadata"]["key_id"] == "key_1"
        assert d1["metadata"]["fallback_attempts"] == 0
        assert d1["metadata"]["input_tokens"] == 38
        assert d1["metadata"]["output_tokens"] == 8
        assert provider_calls == 1

        # 2. Identical first message in a brand-new session B -> LLM_CACHE
        r2 = client.post(
            "/chat",
            json={
                "session_id": "s-cache-b",
                "message": "What is the capital of France?",
            },
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["reply"] == d1["reply"]
        assert d2["metadata"]["resolution_source"] == "LLM_CACHE"
        assert d2["metadata"]["model"] == "openai/gpt-4o-mini"
        assert d2["metadata"]["key_id"] is None
        assert d2["metadata"]["fallback_attempts"] == 0
        assert d2["metadata"]["input_tokens"] == 38
        assert d2["metadata"]["output_tokens"] == 8
        assert d2["metadata"]["latency_ms"] < d1["metadata"]["latency_ms"]
        assert provider_calls == 1

        # 3. Different message must NOT come from cache
        r3 = client.post(
            "/chat",
            json={
                "session_id": "s-cache-c",
                "message": "What is the capital of Japan?",
            },
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert d3["metadata"]["key_id"] == "key_1"
        assert provider_calls == 2

        # 4. Same message with a different system_prompt must NOT come from cache
        r4 = client.post(
            "/chat",
            json={
                "session_id": "s-cache-d",
                "message": "What is the capital of France?",
                "system_prompt": "Respond as a pirate.",
            },
        )
        assert r4.status_code == 200
        d4 = r4.json()
        assert d4["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert provider_calls == 3

        # 5. Identical follow-up message under DIFFERENT conversation history must NOT hit cache
        r_follow_a = client.post(
            "/chat",
            json={
                "session_id": "s-cache-a",
                "message": "Tell me more",
            },
        )
        assert r_follow_a.status_code == 200
        assert r_follow_a.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert provider_calls == 4

        r_follow_c = client.post(
            "/chat",
            json={
                "session_id": "s-cache-c",
                "message": "Tell me more",
            },
        )
        assert r_follow_c.status_code == 200
        assert r_follow_c.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert provider_calls == 5

        # 6. Simulated failure on an already-cached prompt still exercises failover
        r5 = client.post(
            "/chat",
            json={
                "session_id": "s-cache-failover",
                "message": "What is the capital of France?",
            },
            headers={"X-Simulate-Failure": "key_1=429"},
        )
        assert r5.status_code == 200
        d5 = r5.json()
        assert d5["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert d5["metadata"]["key_id"] == "key_2"
        assert d5["metadata"]["fallback_attempts"] == 1
        assert provider_calls == 6


def test_unsupported_cache_type_falls_back_to_local_gracefully(tmp_path):
    settings = make_test_settings(tmp_path, cache_enabled=True, cache_type="disk")
    app = create_app(settings)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["cache_enabled"] is True
