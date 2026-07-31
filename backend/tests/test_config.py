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


# --- F17: the payment gateway boot guards ---


def test_missing_payment_provider_is_not_a_boot_failure() -> None:
    """No gateway is a supported deployment, not a misconfiguration — the
    missing-media-bucket posture: every gateway route answers 503 and deposits
    are simply unavailable."""
    assert _production().payment_provider is None
    assert _production().gateway_secret_box is None


def test_production_with_the_fake_gateway_fails_fast() -> None:
    """The fake gateway reports money RECEIVED that was never charged; in
    production that is a silent revenue hole with a confirmed booking on top.

    `match=` is what ISOLATES this guard. Both fake values have to be passed
    together — `gateway_secret_box` is `Literal["fake"] | None`, so leaving it
    unset trips the "required when PAYMENT_PROVIDER is set" guard instead — and a
    bare `pytest.raises` therefore stays green with this guard deleted, satisfied
    by whichever guard is left. Verified by deleting it: without `match=` the
    whole suite passes."""
    with pytest.raises(ValidationError, match="PAYMENT_PROVIDER"):
        _production(payment_provider="fake", gateway_secret_box="fake")


def test_production_with_the_fake_secret_box_fails_fast() -> None:
    # The fake box is base64. A production merchant credential would sit on disk
    # in plaintext behind an unmissable prefix.
    with pytest.raises(ValidationError):
        _production(gateway_secret_box="fake")


def test_a_gateway_with_no_secret_box_fails_fast() -> None:
    """The "MEDIA_REGION is required when MEDIA_BUCKET is set" case verbatim: a
    MISSING gateway is never a boot failure, a gateway with nowhere to put
    credentials is."""
    with pytest.raises(ValidationError):
        Settings(app_env="dev", database_url=None, payment_provider="fake")


def test_staging_may_use_the_fake_gateway_and_the_fake_box() -> None:
    # Both guards key on production ONLY, deliberately: staging is where the
    # deposit flow is exercised before a real PSP exists. It is also why the
    # console renders a test-environment notice whenever provider == "fake" —
    # staging WILL store a real merchant credential set as base64 of plaintext
    # if an owner types one in.
    settings = Settings(
        app_env="staging",
        database_url=PROD_DATABASE_URL,
        base_domain="staging.ourbrand.co.il",
        payment_provider="fake",
        gateway_secret_box="fake",
    )
    assert settings.payment_provider == "fake"
    assert settings.gateway_secret_box == "fake"


def test_unknown_payment_provider_is_rejected() -> None:
    # The Literal is what stops PAYMENT_PROVIDER=lemonsqueezy booting before its
    # adapter and 0012's widened CHECK exist.
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "dev", "payment_provider": "lemonsqueezy"})


def test_the_superseded_credential_retention_default_is_ninety_days() -> None:
    # D21's blanking clock, read by F20. A security number with no legal
    # counterparty — unlike the payments period, which Gate 1 Q3 set at 7 years.
    assert Settings(app_env="dev").gateway_superseded_credential_retention_days == 90
