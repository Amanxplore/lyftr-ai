from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_litellm_response, make_test_settings


def test_unknown_session_returns_404(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        resp = client.get("/sessions/does-not-exist/messages")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "session not found"}


def test_multi_turn_history_and_persistence_across_restart(tmp_path, monkeypatch):
    captured_calls = []

    async def fake_acompletion(**kwargs):
        captured_calls.append(kwargs["messages"])
        turn = len(captured_calls)
        return make_litellm_response(
            content=f"Reply {turn}",
            prompt_tokens=20 + turn * 10,
            completion_tokens=5 + turn,
        )

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    settings = make_test_settings(tmp_path)
    app1 = create_app(settings)
    with TestClient(app1) as client:
        r1 = client.post(
            "/chat",
            json={
                "session_id": "s-persist",
                "message": "My favorite color is blue.",
                "system_prompt": "Remember user preferences.",
            },
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/chat",
            json={
                "session_id": "s-persist",
                "message": "What is my favorite color?",
            },
        )
        assert r2.status_code == 200

        # Separate session must stay isolated
        r_other = client.post(
            "/chat",
            json={
                "session_id": "s-other",
                "message": "Hello from another session",
            },
        )
        assert r_other.status_code == 200

    # Verify turn 2 sent system_prompt + turn 1 user + turn 1 assistant + turn 2 user
    assert captured_calls[1] == [
        {"role": "system", "content": "Remember user preferences."},
        {"role": "user", "content": "My favorite color is blue."},
        {"role": "assistant", "content": "Reply 1"},
        {"role": "user", "content": "What is my favorite color?"},
    ]
    # Verify s-other did NOT receive s-persist history or custom system prompt
    assert captured_calls[2] == [
        {"role": "system", "content": "You are a helpful test assistant."},
        {"role": "user", "content": "Hello from another session"},
    ]

    # Simulate container restart by creating a new app pointed at the same SQLite DB
    app2 = create_app(settings)
    with TestClient(app2) as client2:
        hist = client2.get("/sessions/s-persist/messages")

    assert hist.status_code == 200
    body = hist.json()
    assert body["session_id"] == "s-persist"
    assert len(body["messages"]) == 4
    # Oldest first, no system prompt
    assert [m["role"] for m in body["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert body["messages"][0] == {
        "role": "user",
        "content": "My favorite color is blue.",
    }
    assert body["messages"][1]["content"] == "Reply 1"
    assert body["messages"][1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert body["messages"][1]["metadata"]["input_tokens"] == 30
    assert body["messages"][1]["metadata"]["output_tokens"] == 6
    assert body["messages"][2]["content"] == "What is my favorite color?"
    assert body["messages"][3]["content"] == "Reply 2"
