from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_litellm_response, make_test_settings


def test_chat_returns_exact_contract_fields(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path))

    async def fake_acompletion(**kwargs):
        assert kwargs["api_key"] == "sk-test-key-one"
        assert kwargs["model"] == "gemini/gemini-2.0-flash"
        return make_litellm_response(
            content="The capital of France is Paris.",
            model="gemini/gemini-2.0-flash",
            prompt_tokens=42,
            completion_tokens=9,
        )

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={
                "session_id": "s-7f3a",
                "message": "What is the capital of France?",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s-7f3a"
    assert body["reply"] == "The capital of France is Paris."

    meta = body["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "gemini/gemini-2.0-flash"
    assert isinstance(meta["latency_ms"], int)
    assert meta["latency_ms"] >= 0
    assert meta["input_tokens"] == 42
    assert meta["output_tokens"] == 9
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0


def _collect_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        if hasattr(route, "path"):
            paths.add(route.path)
        if hasattr(route, "original_router"):
            paths.update(_collect_paths(route.original_router.routes))
    return paths


def test_only_three_contract_endpoints_are_exposed(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    route_paths = _collect_paths(app.routes)
    assert route_paths == {"/health", "/chat", "/sessions/{session_id}/messages"}
