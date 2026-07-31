from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/boutique"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "dev" default keeps local ergonomics; the runtime backstop for a
    # misconfigured deployment is verify_database_role() at app startup.
    app_env: Literal["dev", "staging", "production"] = "dev"
    database_url: str | None = None
    app_version: str = "0.1.0"
    # {slug}.localtest.me resolves to 127.0.0.1 — no /etc/hosts editing in dev.
    # Staging/production set the real platform domain via BASE_DOMAIN.
    base_domain: str = "localtest.me"

    login_max_attempts: int = 5
    login_window_seconds: int = 900
    session_ttl_seconds: int = 60 * 60 * 12

    # Modest per-tenant throttle on terms-version creation: the table is
    # append-only by DB grant, so spam on this path is permanent bloat.
    terms_creation_max_per_window: int = 10
    terms_creation_window_seconds: int = 3600

    # Per-IP login rate limiting needs the REAL client IP. Behind a proxy
    # (Railway/ALB) request.client.host is the proxy — one global bucket that a
    # tiny burst could use to 429 every tenant. So the per-IP key is OFF unless
    # this is set AND the deployment terminates a single trusted proxy that
    # appends X-Forwarded-For (see README). The per-(tenant,email) key — the real
    # brute-force control — is always on and proxy-independent.
    trust_forwarded_for: bool = False

    # Media storage carries deployment identity only — bucket, region, endpoint.
    # Product policy (byte caps, TTLs) lives once in app/catalog/validation.py:
    # an operator raising a byte limit in env while validation.ts and the DB
    # CHECK stayed put would produce an IntegrityError on confirm.
    # AWS credentials are deliberately absent: boto3 reads them from the process
    # environment, so they never enter this object and never reach a repr.
    media_bucket: str | None = None
    media_region: str = "il-central-1"
    media_endpoint_url: str | None = None
    media_force_path_style: bool = False
    media_presign_max_per_window: int = 60
    media_presign_window_seconds: int = 300

    # SMS carries deployment identity only (which adapter); product policy (OTP
    # length, TTLs, attempt cap) lives once in app/notifications/validation.py.
    # None → UnconfiguredSmsSender: no provider is a supported deployment where
    # OTP send answers 503, exactly like the missing media bucket. "fake" is the
    # dev/staging adapter; "twilio" is the real one and the only value that makes
    # production legal.
    sms_provider: Literal["fake", "twilio"] | None = None
    # These four ARE fields, unlike the AWS pair above, and the boto3 precedent
    # does not transfer: boto3 reads the process environment ITSELF, whereas the
    # Twilio adapter is hand-written and nothing else in the tree reads these
    # names. Kept out of Settings they would be invisible whenever they arrive
    # via `.env` — which is exactly where .env.example tells an operator to put
    # them — and the adapter would report is_configured False while every OTP
    # answered 503. As fields, pydantic-settings reads BOTH the `.env` file and
    # real process env vars, so Railway is unaffected. SecretStr is what keeps
    # them out of a repr, a log line and a traceback frame.
    twilio_account_sid: SecretStr | None = None
    twilio_api_key_sid: SecretStr | None = None
    twilio_api_key_secret: SecretStr | None = None
    twilio_from_number: SecretStr | None = None
    # Staging-only escape hatch: verify() also accepts this exact code. The
    # validator below makes it — and the fake sender — a BOOT FAILURE in
    # production, which is what keeps staging convenience from becoming a hole.
    otp_dev_code: str | None = None
    otp_send_max_per_phone_window: int = 5
    otp_send_phone_window_seconds: int = 3600
    otp_send_max_per_tenant_window: int = 100
    otp_send_tenant_window_seconds: int = 3600
    # Verify is throttled SEPARATELY from send. The per-code attempt cap
    # (5, column-tracked) burns one code; without a budget here an attacker
    # simply requests a fresh code and keeps guessing, and each call is an
    # unauthenticated SELECT + locking UPDATE. 10 per 5 minutes is ~2x the
    # attempts a real customer with a typo could need.
    otp_verify_max_per_phone_window: int = 10
    otp_verify_phone_window_seconds: int = 300
    # Booking creation carries TWO budgets, and only the per-phone one is a
    # defence. Both are spent only by callers who proved possession of the
    # phone (see BookingService.create_booking).
    #
    # Per-PHONE is the real control. A claim that fails — lost race, stale
    # terms — rolls its own token burn back so the customer can retry, which
    # without this cap would mean one SMS buys unlimited attempts. 10/hour
    # covers a bride who loses a couple of races and re-picks, and is 2x the
    # OTP sends that same number can even obtain in the window.
    booking_create_max_per_phone_window: int = 10
    booking_create_phone_window_seconds: int = 3600
    # Per-TENANT is the runaway brake, sized like storefront_read_max_per_window
    # so it cannot fire on organic traffic: a pilot boutique books tens of
    # appointments a DAY, and each unit here costs an attacker another real
    # Israeli SIM that must receive an SMS. The earlier 60 was small enough
    # that six phones could close a boutique for an hour.
    booking_create_max_per_window: int = 300
    booking_create_window_seconds: int = 3600
    # An anti-scrape ceiling on the public manage lookup — the one endpoint that
    # answers a secret, so unlike the storefront reads this really is a defence
    # and not only a runaway brake. Per tenant, not per IP, for the same reason
    # every other budget here is: trust_forwarded_for is unresolved until F21.
    # 60 per 5 minutes is far past a bride re-opening her SMS a few times and far
    # below a useful rate against a 256-bit token space.
    booking_lookup_max_per_tenant_window: int = 60
    booking_lookup_window_seconds: int = 300
    # One budget shared by the three owner taps that spend real SMS credit —
    # resend, phone correction and reschedule (D10). Owner cancel is off it:
    # `cancelled` is terminal, so it is bounded at one SMS per booking by
    # construction. The realistic failure is a stuck button and an impatient
    # owner, not an attacker, so 20/hour is a runaway brake far above a
    # boutique's real volume rather than a defence.
    booking_owner_sms_max_per_tenant_window: int = 20
    booking_owner_sms_window_seconds: int = 3600
    # How often the worker drains due scheduled messages. Deploy-tunable without
    # a code change, and a missed window self-heals on the next tick because the
    # claim is `send_after <= now()` rather than an exact-time match.
    worker_poll_interval_seconds: int = 60

    # Payments carry deployment identity only (which adapter, which key
    # manager); product policy — field caps, the KMS blob ceiling, the AAD
    # purpose label — lives once in app/payments/validation.py.
    #
    # Both None -> UnconfiguredGateway + UnconfiguredSecretBox: no gateway is a
    # supported deployment where every gateway route answers 503 and deposits are
    # simply unavailable, exactly like the missing media bucket. "fake" is the
    # dev/staging pair; "lemonsqueezy" is F18's TEST-MODE development engine and
    # is forbidden in production below; a production provider literal arrives
    # with its adapter, and "kms" arrives with KmsSecretBox.
    payment_provider: Literal["fake", "lemonsqueezy"] | None = None
    gateway_secret_box: Literal["fake"] | None = None
    gateway_validate_max_per_tenant_window: int = 10
    gateway_validate_window_seconds: int = 3600
    # Its own budget, sized like the terms one it is copied from and for the
    # same stated reason: rotation is insert-only on a table whose DELETE is
    # revoked, so a loop on this path is permanent, unreclaimable table growth —
    # plus unbounded KMS request spend.
    gateway_connect_max_per_tenant_window: int = 10
    gateway_connect_window_seconds: int = 3600
    # D21's blanking clock, read by F20: superseded credential ciphertext stops
    # being recoverable from our disk after this. A security number with no legal
    # counterparty — long enough for an incident review, short enough that a
    # leaked-then-rotated merchant secret does not live forever.
    gateway_superseded_credential_retention_days: int = 90

    # Per-TENANT budget on the anonymous storefront reads: a runaway brake, not
    # a defence (see app/storefront/router.py._throttle for the full argument).
    # Env-tunable like every other rate limit here so it can be tightened during
    # an incident without a code deploy.
    #
    # The arithmetic, because the analogy to login_max_attempts is wrong here: a
    # first paint is 2 requests and a dress tap is 1 more, so 6000/60s is roughly
    # 3000 first-paints per minute per tenant. The obvious number, 600, would 429
    # real customers the minute a boutique's Instagram story lands — the exact
    # traffic event this product exists for — while a scraper simply paces
    # itself. Sized so it cannot fire on organic traffic.
    storefront_read_max_per_window: int = 6000
    storefront_read_window_seconds: int = 60

    @property
    def secure_cookies(self) -> bool:
        return self.app_env != "dev"

    @model_validator(mode="after")
    def _require_database_url_outside_dev(self) -> Self:
        # A non-dev deployment missing DATABASE_URL must fail fast — never
        # silently boot against localhost as superuser (Feature 1 security review).
        if self.app_env != "dev" and not self.database_url:
            raise ValueError("DATABASE_URL is required when APP_ENV is not 'dev'")
        return self

    @model_validator(mode="after")
    def _require_real_base_domain_outside_dev(self) -> Self:
        # Forgetting BASE_DOMAIN in prod would 404 every request (no real host
        # ends with .localtest.me) — fail at boot, not as a silent outage.
        if self.app_env != "dev" and self.base_domain == "localtest.me":
            raise ValueError("BASE_DOMAIN must be set when APP_ENV is not 'dev'")
        return self

    @model_validator(mode="after")
    def _require_usable_media_config(self) -> Self:
        # A MISSING bucket is never a boot failure — no bucket is a supported
        # deployment where only the media write endpoints answer 503. A WRONG
        # one is, exactly like _require_real_base_domain_outside_dev: the
        # endpoint override is a CI/S3-compatible-provider seam, and left set
        # against real AWS it points every upload somewhere it must never go.
        if self.media_bucket and not self.media_region:
            raise ValueError("MEDIA_REGION is required when MEDIA_BUCKET is set")
        if self.app_env == "production" and self.media_endpoint_url:
            raise ValueError("MEDIA_ENDPOINT_URL must not be set when APP_ENV is 'production'")
        if (
            self.media_endpoint_url
            and self.app_env != "dev"
            and not self.media_endpoint_url.startswith("https://")
        ):
            raise ValueError("MEDIA_ENDPOINT_URL must be https when APP_ENV is not 'dev'")
        if self.app_env == "production" and self.media_force_path_style:
            raise ValueError("MEDIA_FORCE_PATH_STYLE must be false when APP_ENV is 'production'")
        return self

    @model_validator(mode="after")
    def _forbid_sms_test_paths_in_production(self) -> Self:
        # The fake sender "sends" nothing and the dev code bypasses the OTP
        # comparison — either one in production silently voids the phone
        # verification the whole booking flow rests on. Fail at boot, loudly.
        if self.app_env == "production" and self.sms_provider == "fake":
            raise ValueError("SMS_PROVIDER must not be 'fake' when APP_ENV is 'production'")
        if self.app_env == "production" and self.otp_dev_code:
            raise ValueError("OTP_DEV_CODE must not be set when APP_ENV is 'production'")
        return self

    @model_validator(mode="after")
    def _forbid_fake_payment_paths_in_production(self) -> Self:
        # The fake gateway reports money RECEIVED that was never charged, and
        # F19's flow would confirm bookings off that: in production it is a
        # silent revenue hole with a confirmed appointment on top of it. The fake
        # secret box is base64, so a production merchant credential would sit on
        # disk in plaintext. Fail at boot, loudly — the
        # _forbid_sms_test_paths_in_production shape.
        if self.app_env == "production" and self.payment_provider == "fake":
            raise ValueError("PAYMENT_PROVIDER must not be 'fake' when APP_ENV is 'production'")
        # F18's guard 1, and the same shape on purpose. Lemon Squeezy is
        # merchant-of-record: it would make MODRYN the seller of the bride's
        # transaction, when the deposit is legally the boutique's and the
        # boutique owes the Israeli receipt (architecture.md:13,
        # e10-scale-polish.md:86). The adapter also hard-codes test mode, so in
        # production it would take no money at all while reporting sessions.
        if self.app_env == "production" and self.payment_provider == "lemonsqueezy":
            raise ValueError(
                "PAYMENT_PROVIDER must not be 'lemonsqueezy' when APP_ENV is 'production'"
            )
        if self.app_env == "production" and self.gateway_secret_box == "fake":
            raise ValueError("GATEWAY_SECRET_BOX must not be 'fake' when APP_ENV is 'production'")
        # A MISSING gateway is never a boot failure — that is the supported
        # 503-everywhere deployment. A gateway with NOWHERE TO PUT CREDENTIALS
        # is a misconfiguration, not a deployment: this is the
        # "MEDIA_REGION is required when MEDIA_BUCKET is set" case verbatim.
        if self.payment_provider and not self.gateway_secret_box:
            raise ValueError("GATEWAY_SECRET_BOX is required when PAYMENT_PROVIDER is set")
        return self

    @property
    def effective_database_url(self) -> str:
        return self.database_url or DEV_DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()
