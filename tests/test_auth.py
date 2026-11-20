import os

os.environ["APP_TOKEN"] = "t" * 32
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _token_ok, app  # noqa: E402


def test_health_is_public():
    assert TestClient(app).get("/health").status_code == 200


def test_api_requires_token():
    c = TestClient(app)
    assert c.get("/api/summary").status_code == 401
    assert c.get("/api/summary", headers={"X-App-Token": "wrong"}).status_code == 401


def test_default_example_token_is_rejected(monkeypatch):
    from app import main

    class S:
        app_token = main.DEFAULT_TOKEN

    monkeypatch.setattr(main, "get_settings", lambda: S())

    class R:
        headers = {"X-App-Token": main.DEFAULT_TOKEN}
        query_params = {}
        cookies = {}

    assert _token_ok(R()) is False
