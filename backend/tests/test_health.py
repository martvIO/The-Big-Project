import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

BUCKET = "boutique-prod-media"


def _client(monkeypatch: pytest.MonkeyPatch, *, media_bucket: str | None) -> TestClient:
    settings = Settings(app_env="dev", media_bucket=media_bucket, media_region="il-central-1")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    return TestClient(create_app())


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert body["version"]


def test_health_reports_media_unconfigured_without_a_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings.model_config is extra="ignore", so a typo'd MEDIA_BUKCET is
    discarded silently. This field is how the staging smoke learns that before
    attempting a presign."""
    resp = _client(monkeypatch, media_bucket=None).get("/health")
    assert resp.status_code == 200
    assert resp.json()["media"] == "unconfigured"
    assert resp.json()["status"] == "ok"


def test_health_reports_media_configured_but_never_names_the_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resp = _client(monkeypatch, media_bucket=BUCKET).get("/health")
    assert resp.status_code == 200
    assert resp.json()["media"] == "configured"
    # /health is unauthenticated and host-agnostic: it reports the state, never
    # the identity. No bucket, region or endpoint may appear.
    assert BUCKET not in resp.text
    assert "il-central-1" not in resp.text
