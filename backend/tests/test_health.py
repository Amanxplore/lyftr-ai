from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_test_settings


def test_health_returns_ok_with_configured_keys_and_cache(tmp_path):
    settings = make_test_settings(
        tmp_path,
        llm_api_keys="sk-one,sk-two,sk-three",
        cache_enabled=True,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 3
    assert data["cache_enabled"] is True


def test_health_returns_503_when_no_keys_configured(tmp_path):
    settings = make_test_settings(tmp_path, llm_api_keys="")
    app = create_app(settings)
    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 503
    data = resp.json()
    assert "detail" in data


def test_health_returns_503_when_database_fails(tmp_path, monkeypatch):
    settings = make_test_settings(tmp_path)
    app = create_app(settings)

    def broken_health():
        raise RuntimeError("disk io failure")

    monkeypatch.setattr(app.state.db_manager, "check_health", broken_health)
    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "database unavailable"}
