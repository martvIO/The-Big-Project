from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert body["version"]
