from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
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

    @property
    def effective_database_url(self) -> str:
        return self.database_url or DEV_DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()
