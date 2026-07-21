import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dev_defaults_to_localhost_database() -> None:
    settings = Settings(app_env="dev", database_url=None)
    assert settings.effective_database_url.startswith("postgresql+asyncpg://")
    assert "localhost" in settings.effective_database_url


def test_non_dev_without_database_url_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", database_url=None)


def test_non_dev_with_database_url_is_used_verbatim() -> None:
    url = "postgresql+asyncpg://app:secret@db.internal:5432/boutique"
    settings = Settings(app_env="production", database_url=url)
    assert settings.effective_database_url == url


def test_unknown_app_env_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "prod-oops"})
