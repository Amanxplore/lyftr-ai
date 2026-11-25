from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_litellm_response, make_test_settings


def test_validation_rejects_empty_and_oversized_fields(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        # Missing message
        r1 = client.post("/chat", json={"session_id": "s-1"})
        assert r1.status_code == 422
        assert "detail" in r1.json()

        # Whitespace-only message
        r2 = client.post("/chat", json={"session_id": "s-1", "message": "   \n\t  "})
        assert r2.status_code == 422
        assert "detail" in r2.json()

        # Message over 4000 chars after trimming
        r3 = client.post("/chat", json={"session_id": "s-1", "message": "x" * 4001})
        assert r3.status_code == 422
        assert "detail" in r3.json()

        # Empty session_id
        r4 = client.post("/chat", json={"session_id": "  ", "message": "hello"})
        assert r4.status_code == 422
        assert "detail" in r4.json()

        # session_id over 128 chars
        r5 = client.post("/chat", json={"session_id": "s" * 129, "message": "hello"})
        assert r5.status_code == 422
        assert "detail" in r5.json()

        # Malformed JSON
        r6 = client.post(
            "/chat",
            content="{not-valid-json",
            headers={"Content-Type": "application/json"},
        )
        assert r6.status_code == 422
        assert "detail" in r6.json()

        # Failed requests must NOT create session history
        hist = client.get("/sessions/s-1/messages")
        assert hist.status_code == 404
        assert hist.json() == {"detail": "session not found"}


def test_validation_accepts_message_valid_after_trimming(tmp_path, monkeypatch):
    app = create_app(make_test_settings(tmp_path))

    async def fake_acompletion(**kwargs):
        return make_litellm_response(content="Trimmed ok!")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)

    with TestClient(app) as client:
        # 4000 chars with leading/trailing spaces is valid after trimming
        padded = "  " + ("a" * 4000) + "  "
        resp = client.post("/chat", json={"session_id": "s-trim", "message": padded})

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Trimmed ok!"
