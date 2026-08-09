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
    """The Literal is what stops a provider booting before its adapter and its
    migration exist. 'lemonsqueezy' was this test's example until F18 shipped
    both — which is exactly the sequence the Literal enforces — so the example
    moves to a provider that still has neither.

    `gateway_secret_box` is supplied and `match=` names the field, because
    without either this test kept passing after F18 widened the Literal: the
    unrelated "GATEWAY_SECRET_BOX is required when PAYMENT_PROVIDER is set"
    guard fired instead, and the assertion proved nothing about the Literal it
    claimed to be testing."""
    with pytest.raises(ValidationError, match="payment_provider"):
        Settings.model_validate(
            {"app_env": "dev", "payment_provider": "grow", "gateway_secret_box": "fake"}
        )


def test_the_superseded_credential_retention_default_is_ninety_days() -> None:
    # D21's blanking clock, read by F20. A security number with no legal
    # counterparty — unlike the payments period, which Gate 1 Q3 set at 7 years.
    assert Settings(app_env="dev").gateway_superseded_credential_retention_days == 90


# --- F20's retention clocks -------------------------------------------------
#
# The only config in this repo where a typo is UNRECOVERABLE DATA LOSS, so the
# floors are tested against the realistic fat-finger — a DROPPED DIGIT — and not
# only against the literal `=0` a first draft would guard. Each floor sits within
# an order of magnitude of the default it guards, which is what makes a
# one-digit-short value trip it.


def test_retention_ships_disarmed() -> None:
    """Gate 1 Q2. An unattended, irreversible, chunked mass-DELETE against a
    database with no tested restore does not ship armed — the job ships complete
    and turning it on is one env var."""
    assert Settings(app_env="dev").retention_enabled is False
    assert Settings(app_env="dev", retention_enabled=True).retention_enabled is True


def test_the_retention_defaults_are_the_specified_periods() -> None:
    settings = Settings(app_env="dev")
    assert settings.retention_otp_seconds == 15 * 60
    assert settings.retention_queue_ticket_seconds == 7 * 24 * 3600
    assert settings.retention_message_log_seconds == 730 * 24 * 3600
    assert settings.retention_bookings_seconds == 365 * 7 * 24 * 3600
    assert settings.retention_orphan_customer_seconds == 30 * 24 * 3600
    assert settings.retention_poll_interval_seconds == 3600


def test_the_otp_retention_floor_is_computed_from_the_two_ttls_not_written_as_a_number() -> None:
    """Asserted by COMPUTING it, so a future TTL change moves the test with the
    code. 15 minutes is EXACTLY `OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS`
    — the margin is zero — so the floor equals the default and there is nothing
    below it to allow."""
    from app.notifications.validation import OTP_TTL_SECONDS, VERIFICATION_TOKEN_TTL_SECONDS

    floor = OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS
    assert Settings(app_env="dev").retention_otp_seconds == floor
    Settings(app_env="dev", retention_otp_seconds=floor)
    with pytest.raises(ValidationError, match="RETENTION_OTP_SECONDS"):
        Settings(app_env="dev", retention_otp_seconds=floor - 1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # A dropped digit, per class. RETENTION_OTP_SECONDS=60 is the case that
        # matters most: it boots clean under a naive `>= 60` floor and then purges
        # every OTP row a minute after send, so no booking in the platform can be
        # completed and there is no error anywhere to explain it.
        ("retention_otp_seconds", 90),
        ("retention_queue_ticket_seconds", 60_480),
        ("retention_message_log_seconds", 6_307_200),
        ("retention_bookings_seconds", 22_075_200),
        ("retention_orphan_customer_seconds", 259_200),
        # ...and the literal zero a first draft would have stopped at.
        ("retention_otp_seconds", 0),
        ("retention_queue_ticket_seconds", 0),
        ("retention_message_log_seconds", 0),
        ("retention_bookings_seconds", 0),
        ("retention_orphan_customer_seconds", 0),
        ("retention_poll_interval_seconds", 0),
    ],
)
def test_a_retention_period_below_its_floor_is_a_boot_failure(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field.upper()):
        Settings.model_validate({"app_env": "dev", field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retention_queue_ticket_seconds", 2 * 24 * 3600),
        ("retention_message_log_seconds", 180 * 24 * 3600),
        ("retention_bookings_seconds", 3 * 365 * 24 * 3600),
        ("retention_orphan_customer_seconds", 7 * 24 * 3600),
        ("retention_poll_interval_seconds", 60),
    ],
)
def test_a_retention_period_exactly_at_its_floor_boots(field: str, value: int) -> None:
    """The boundary in the other direction: a floor that rejected its own value
    would make the documented minimum unusable."""
    assert getattr(Settings.model_validate({"app_env": "dev", field: value}), field) == value


# --- F38's staff retention clock --------------------------------------------


def test_the_staff_retention_default_is_seven_years_in_days() -> None:
    """In DAYS and not seconds, and that is not cosmetic: `last_day` is a
    Jerusalem CALENDAR date, so the policy compares dates and a seconds value
    would have to be divided back into one at every use.
    `waitlist_retention_days` is the in-repo precedent for the unit.

    Flagged for counsel at F21 like every other clock here (spec O2): whether
    seven years is right is a legal question, and this is the one value that
    changes for every tenant at once when it is answered."""
    assert Settings(app_env="dev").staff_retention_days == 365 * 7


def test_a_staff_retention_below_its_three_year_floor_is_a_boot_failure() -> None:
    """`STAFF_RETENTION_DAYS=7` is the fat-finger this exists for: it boots clean
    without a floor and then, at 03:00, blanks the name and email of every
    staffer who left a week ago."""
    with pytest.raises(ValidationError, match="STAFF_RETENTION_DAYS"):
        Settings.model_validate({"app_env": "dev", "staff_retention_days": 7})
    with pytest.raises(ValidationError, match="STAFF_RETENTION_DAYS"):
        Settings.model_validate({"app_env": "dev", "staff_retention_days": 0})


def test_a_staff_retention_exactly_at_its_floor_boots() -> None:
    at_floor = 365 * 3
    assert (
        Settings.model_validate(
            {"app_env": "dev", "staff_retention_days": at_floor}
        ).staff_retention_days
        == at_floor
    )


def test_the_staff_retention_failure_names_days_and_not_seconds() -> None:
    """⚠ THE assertion this task exists for. The shipped floors loop hardcodes
    "… must be at least {floor} seconds" in its message, so riding a DAYS field
    on that dict passes every test that only checks THAT it raises — and ships an
    operator-facing error naming the wrong unit by a factor of 86,400.

    Asserted on the message text, never on the raise alone."""
    with pytest.raises(ValidationError) as refused:
        Settings.model_validate({"app_env": "dev", "staff_retention_days": 1})
    message = str(refused.value)
    assert "days" in message
    assert "seconds" not in message


def test_the_seconds_worded_messages_are_unchanged() -> None:
    """The other half of the pair: adding a days-worded branch must not have
    re-worded the five clocks that really are in seconds."""
    with pytest.raises(ValidationError) as refused:
        Settings.model_validate({"app_env": "dev", "retention_bookings_seconds": 0})
    assert "seconds" in str(refused.value)
