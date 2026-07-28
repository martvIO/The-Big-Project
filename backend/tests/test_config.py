from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_base_domain_defaults_to_local_dev_domain() -> None:
    settings = Settings(app_env="dev", database_url=None)
    assert settings.base_domain == "localtest.me"


def test_dev_defaults_to_localhost_database() -> None:
    settings = Settings(app_env="dev", database_url=None)
    assert settings.effective_database_url.startswith("postgresql+asyncpg://")
    assert "localhost" in settings.effective_database_url


def test_non_dev_without_database_url_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", database_url=None)


def test_non_dev_with_database_url_is_used_verbatim() -> None:
    url = "postgresql+asyncpg://app:secret@db.internal:5432/boutique"
    settings = Settings(app_env="production", database_url=url, base_domain="ourbrand.co.il")
    assert settings.effective_database_url == url


def test_non_dev_with_dev_base_domain_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db.internal:5432/boutique",
        )


def test_unknown_app_env_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "prod-oops"})


PROD_DATABASE_URL = "postgresql+asyncpg://app:secret@db.internal:5432/boutique"


def _production(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "production",
        "database_url": PROD_DATABASE_URL,
        "base_domain": "ourbrand.co.il",
    }
    values.update(overrides)
    return Settings(**values)


def test_missing_media_bucket_is_not_a_boot_failure() -> None:
    """No bucket is a supported deployment, not a misconfiguration: the whole
    catalog stays usable and only the media write endpoints answer 503."""
    settings = Settings(app_env="dev", database_url=None)
    assert settings.media_bucket is None


def test_media_bucket_without_a_region_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="dev", database_url=None, media_bucket="b", media_region="")


def test_production_without_a_media_bucket_still_boots() -> None:
    assert _production().media_bucket is None


def test_production_with_a_media_endpoint_fails_fast() -> None:
    """MEDIA_ENDPOINT_URL is a CI/S3-compatible-provider seam. Left set against
    real AWS it silently points every upload at someone else's bucket."""
    with pytest.raises(ValidationError):
        _production(media_bucket="b", media_endpoint_url="https://minio.internal")


def test_production_with_path_style_addressing_fails_fast() -> None:
    with pytest.raises(ValidationError):
        _production(media_bucket="b", media_force_path_style=True)


def test_missing_sms_provider_is_not_a_boot_failure() -> None:
    """No provider is a supported deployment: bookings are structurally gated on
    the sender-ID registration by OTP send answering 503, never by a crash."""
    assert _production().sms_provider is None


def test_production_with_fake_sms_provider_fails_fast() -> None:
    with pytest.raises(ValidationError):
        _production(sms_provider="fake")


def test_production_with_otp_dev_code_fails_fast() -> None:
    with pytest.raises(ValidationError):
        _production(otp_dev_code="424242")


def test_staging_may_use_fake_sender_and_dev_code() -> None:
    settings = Settings(
        app_env="staging",
        database_url=PROD_DATABASE_URL,
        base_domain="staging.ourbrand.co.il",
        sms_provider="fake",
        otp_dev_code="424242",
    )
    assert settings.sms_provider == "fake"
    assert settings.otp_dev_code == "424242"


def test_plaintext_media_endpoint_outside_dev_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="staging",
            database_url=PROD_DATABASE_URL,
            base_domain="staging.ourbrand.co.il",
            media_bucket="b",
            media_endpoint_url="http://minio.internal",
        )
