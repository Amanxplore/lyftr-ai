import litellm
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_litellm_response, make_test_settings


def test_simulated_failure_key_1_429_falls_back_to_key_2(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path, enable_failure_simulation=True))
    called_keys = []

    async def fake_acompletion(**kwargs):
        called_keys.append(kwargs["api_key"])
        return make_litellm_response(content="Answered by key 2!")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "s-sim-1", "message": "Hello"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Answered by key 2!"
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1
    assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert called_keys == ["sk-test-key-two"]


def test_simulated_failure_key_1_500_falls_back_to_key_2(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path, enable_failure_simulation=True))

    async def fake_acompletion(**kwargs):
        return make_litellm_response(content="Recovered on key 2")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "s-sim-2", "message": "Hello"},
            headers={"X-Simulate-Failure": "key_1=500"},
        )

    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_2"
    assert resp.json()["metadata"]["fallback_attempts"] == 1


def test_simulated_failure_all_keys_returns_503_and_does_not_persist(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path, enable_failure_simulation=True))

    async def fake_acompletion(**kwargs):
        raise AssertionError("Should not invoke LiteLLM when all keys are simulated to fail")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "s-sim-all", "message": "Hello"},
            headers={"X-Simulate-Failure": "*=429"},
        )
        assert resp.status_code == 503
        assert resp.json() == {"detail": "all providers unavailable"}

        hist = client.get("/sessions/s-sim-all/messages")
        assert hist.status_code == 404
        assert hist.json() == {"detail": "session not found"}


def test_simulation_header_ignored_when_disabled(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path, enable_failure_simulation=False))

    async def fake_acompletion(**kwargs):
        return make_litellm_response(content="Key 1 answered")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "s-sim-off", "message": "Hello"},
            headers={"X-Simulate-Failure": "*=429"},
        )

    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_1"
    assert resp.json()["metadata"]["fallback_attempts"] == 0


def test_real_provider_429_and_5xx_failover_and_total_exhaustion(tmp_path, monkeypatch):
    app = create_app(
        make_test_settings(
            tmp_path,
            llm_api_keys="sk-1,sk-2,sk-3",
            llm_models="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openai/gpt-4o-mini",
        )
    )

    async def fake_acompletion(**kwargs):
        key = kwargs["api_key"]
        if key == "sk-1":
            raise litellm.RateLimitError(
                message="429 quota exceeded",
                llm_provider="gemini",
                model=kwargs["model"],
            )
        if key == "sk-2":
            raise litellm.ServiceUnavailableError(
                message="503 upstream overloaded",
                llm_provider="groq",
                model=kwargs["model"],
            )
        return make_litellm_response(
            content="Key 3 saved the day",
            model=kwargs["model"],
            prompt_tokens=31,
            completion_tokens=6,
        )

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "s-real-failover", "message": "Test failover"},
        )

    assert resp.status_code == 200
    meta = resp.json()["metadata"]
    assert meta["key_id"] == "key_3"
    assert meta["model"] == "openai/gpt-4o-mini"
    assert meta["fallback_attempts"] == 2

    # Now fail all keys with real exceptions
    async def all_fail(**kwargs):
        raise litellm.InternalServerError(
            message="500 internal error",
            llm_provider="openai",
            model=kwargs["model"],
        )

    monkeypatch.setattr("litellm.acompletion", all_fail)

    with TestClient(app) as client:
        fail_resp = client.post(
            "/chat",
            json={"session_id": "s-all-fail-real", "message": "Will fail"},
        )
        assert fail_resp.status_code == 503
        assert fail_resp.json() == {"detail": "all providers unavailable"}
        assert client.get("/sessions/s-all-fail-real/messages").status_code == 404


def test_simulated_failure_multiple_keys_and_no_leak_to_next_request(tmp_path, monkeypatch):
    # With 2 keys, key_1=429,key_2=500 exhausts the pool -> 503 and nothing persisted
    app_two = create_app(make_test_settings(tmp_path / "two", enable_failure_simulation=True))

    async def fake_acompletion(**kwargs):
        return make_litellm_response(content="Healthy reply")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app_two) as client:
        r_fail = client.post(
            "/chat",
            json={"session_id": "s-two-fail", "message": "Hi"},
            headers={"X-Simulate-Failure": "key_1=429,key_2=500"},
        )
        assert r_fail.status_code == 503
        assert r_fail.json() == {"detail": "all providers unavailable"}
        assert client.get("/sessions/s-two-fail/messages").status_code == 404

        # Subsequent request without header must succeed cleanly on key_1
        r_ok = client.post(
            "/chat",
            json={"session_id": "s-two-fail", "message": "Hi"},
        )
        assert r_ok.status_code == 200
        assert r_ok.json()["metadata"]["key_id"] == "key_1"
        assert r_ok.json()["metadata"]["fallback_attempts"] == 0

    # With 3 keys, key_1=429,key_2=500 fails over to key_3 with fallback_attempts=2
    app_three = create_app(
        make_test_settings(
            tmp_path / "three",
            llm_api_keys="sk-1,sk-2,sk-3",
            enable_failure_simulation=True,
        )
    )
    with TestClient(app_three) as client3:
        r3 = client3.post(
            "/chat",
            json={"session_id": "s-three-fail", "message": "Hi"},
            headers={"X-Simulate-Failure": "key_1=429,key_2=500"},
        )
        assert r3.status_code == 200
        assert r3.json()["metadata"]["key_id"] == "key_3"
        assert r3.json()["metadata"]["fallback_attempts"] == 2
