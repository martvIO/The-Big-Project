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

    @property
    def effective_database_url(self) -> str:
        return self.database_url or DEV_DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()
