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
    # How long a deposit hold holds the seat before the sweeper releases it
    # (F19 D6). Deliberately NOT one of the recorded money decisions: one env
    # var, reversible in a deploy, no data migration. Its only irreversible
    # consequence is the width of the expiry-vs-webhook race, and 15 minutes is
    # long enough for a bride to find her card and short enough that an
    # abandoned checkout does not hold a Saturday morning slot.
    deposit_hold_seconds: int = 900

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

    # F33's three check-in budgets. THREE limiter instances, never three keys on
    # one: max_attempts lives on the LIMITER, so a shared instance is a shared
    # ceiling and two of these would trip each other.
    #
    # The runaway brake on the create, and the ONLY bound on it — there is no
    # per-phone budget, because a 429 on a phone key is a fact about one person
    # disclosed to anyone who submits her number, and a flooder varies the
    # number for free anyway. A pilot boutique sees tens of walk-ins a DAY, so
    # 200/hour cannot fire on organic traffic and still stops a scripted flood.
    checkin_create_max_per_window: int = 200
    checkin_create_window_seconds: int = 3600
    # The per-client control on the position poll, keyed on the ticket id the
    # caller already holds — so a 429 on it discloses nothing. A 5-second poll
    # is 12/60s, so 30 is 2.5x headroom and one leaked loop stops at its own
    # ceiling rather than at the boutique's.
    checkin_position_max_per_ticket_window: int = 30
    checkin_position_ticket_window_seconds: int = 60
    # The anti-walk brake, charged on position reads that MISSED and nothing
    # else. A flood of guessed ids then denies only reads no legitimate client
    # makes; hits keep answering 200. 120/60s is far above the miss rate of a
    # real client (one, once, when her ticket is swept) and far below a useful
    # rate against a 122-bit id space.
    checkin_position_max_misses_per_window: int = 120
    checkin_position_miss_window_seconds: int = 60
    # F59's board budget, and a FOURTH limiter instance for the same reason the
    # three above are three. Its traffic shape is unlike every other anonymous
    # surface in this product: a wall screen is a single device polling forever
    # at an even cadence, whether or not anybody is in the shop.
    #
    # The arithmetic must count PHONES, not screens, because the key is per
    # TENANT and every woman in the salon who opens the same public URL lands on
    # it — which is an ordinary thing to do with a URL that is public by ruling,
    # and is the load-bearing half of this page's pause-control argument:
    #   2 wall screens at a 5s beat ....................  24 req/min
    #   up to 18 phones in the room on a busy Sunday ... 216 req/min
    #   design target, 20 concurrent viewers ........... 240 req/min
    #   ceiling at 2.5x the target ..................... 600 req/min
    # A screens-only reading gave 120, which is TEN concurrent viewers — two
    # screens and eight phones exactly — and the board only grows all day until
    # F58 ships, so the wall would start backing off at the one moment it
    # matters. 600 is 50 concurrent pollers, above any bridal salon, and still
    # kills a scripted reader: at 50 rps the budget is gone in 12 seconds.
    queue_board_max_per_window: int = 600
    queue_board_window_seconds: int = 60

    # F20's per-data-class retention clocks. These ARE product policy and the
    # house rule normally keeps product policy out of Settings — the reason that
    # rule exists is drift between an env var and a DB CHECK or a frontend
    # constant, producing an IntegrityError on a user action. These have neither
    # twin, and what they do have is a counsel confirmation at F21 that should
    # change one value for every tenant at once. Per-tenant overrides are
    # deliberately absent: a boutique may not choose its own retention for a duty
    # the platform enforces on its behalf.
    #
    # It ships DISARMED (Gate 1 Q2). What `retention_enabled=True` deploys is an
    # unattended, irreversible, chunked mass-DELETE across five tables on clocks
    # read from the environment, against a database with no backup and no tested
    # restore. A default that must be un-set by a deploy note to be safe is a
    # loaded gun with a sticker on it; F21's backup row is the gate that flips it.
    retention_enabled: bool = False
    retention_poll_interval_seconds: int = 3600
    # Exactly OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS. The margin is
    # ZERO — safe only because verify refuses at `expires_at <= now`, so no
    # verification token can be alive at created_at + 900.
    retention_otp_seconds: int = 15 * 60
    retention_queue_ticket_seconds: int = 7 * 24 * 3600
    retention_message_log_seconds: int = 730 * 24 * 3600
    retention_bookings_seconds: int = 365 * 7 * 24 * 3600
    retention_orphan_customer_seconds: int = 30 * 24 * 3600

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

    @model_validator(mode="after")
    def _require_retention_periods_above_their_floors(self) -> Self:
        """Fail at boot rather than degrade — `_forbid_sms_test_paths_in_production`
        is the precedent, and this is the only config in the repo where the thing
        a typo costs is UNRECOVERABLE DATA LOSS.

        Every floor sits within an order of magnitude of the default it guards,
        which is the whole design: floors 15x-730x below their defaults catch the
        literal `=0` they were written for and let the REALISTIC fat-finger — one
        digit short — sail through. `RETENTION_BOOKINGS_SECONDS=220752000`
        mistyped as `22075200` is 255 days, and the next tick hard-DELETEs every
        booking older than that INCLUDING its `terms_version_accepted` — the very
        evidence the erase design goes out of its way to preserve.

        The OTP floor is IMPORTED, never written as a number, so a future TTL
        change moves it. It equals the default because 15 minutes is exactly
        sufficient and there is nothing below it to allow: a naive `>= 60` would
        let `RETENTION_OTP_SECONDS=60` boot clean and then purge every code a
        minute after send, making every booking in the platform uncompletable
        with no error anywhere to explain it.
        """
        from app.notifications.validation import OTP_TTL_SECONDS, VERIFICATION_TOKEN_TTL_SECONDS

        floors = {
            "retention_otp_seconds": OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS,
            "retention_queue_ticket_seconds": 2 * 24 * 3600,
            "retention_message_log_seconds": 180 * 24 * 3600,
            "retention_bookings_seconds": 3 * 365 * 24 * 3600,
            "retention_orphan_customer_seconds": 7 * 24 * 3600,
            "retention_poll_interval_seconds": 60,
        }
        for field, floor in floors.items():
            if getattr(self, field) < floor:
                raise ValueError(f"{field.upper()} must be at least {floor} seconds")
        return self

    @property
    def effective_database_url(self) -> str:
        return self.database_url or DEV_DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()
