"""Worker entrypoint. F16 registers the first job — the scheduled-message poller
— and deliberately introduces no new process: `app/worker.py` is already a
deployed Railway service (`uv run python -m app.worker`) with a CI deploy step.

**Why a poller and not a cron at exactly 24h.** architecture.md pins this
("scheduled_messages table + poller worker (`FOR UPDATE SKIP LOCKED`), never
'cron exactly 24h'"). A claim of `send_after <= now()` means a window missed
during a deploy self-heals on the next tick, and a reminder that fires late still
states the true time because the body renders from `starts_at`.

**Why tenants are enumerated instead of queried across.** `scheduled_messages`
carries the standard FORCE RLS policy, so every read needs a tenant context. The
`tenants` table is deliberately RLS-free, which makes the enumeration the only
tenancy-preserving shape (D6) — cross-tenant leakage is the recorded existential
risk, and the codebase's first background reader does not get to be the first RLS
exception.

Sends here are UNMETERED: the API's limiters are per-process and unreachable from
this one, and the volume is bounded by bookings inside the horizon rather than by
anything a caller controls.
"""

import asyncio
import logging

from app.booking.comms import BookingCommsService, CommsTenant, DrainResult
from app.core.config import Settings, get_settings
from app.db.repositories.tenants import TenantsRepository
from app.db.session import ensure_safe_database_role, get_session_factory
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService
from app.notifications.unconfigured import UnconfiguredSmsSender

logger = logging.getLogger("worker")


def build_sender(settings: Settings) -> FakeSmsSender | UnconfiguredSmsSender:
    """Mirrors `main._build_sms_sender`, including the observability line: no
    provider is a SUPPORTED state here (due rows are simply left pending until an
    adapter lands), and `Settings.model_config` is extra="ignore", so a typo'd
    SMS_PROVDER would otherwise degrade in silence."""
    if settings.sms_provider == "fake":
        logger.info("SMS sender: FAKE (in-memory outbox) — no real SMS will be sent")
        return FakeSmsSender()
    logger.info("SMS sender NOT configured — due reminders will be left pending")
    return UnconfiguredSmsSender()


async def poll_once(comms: BookingCommsService, tenants: TenantsRepository) -> DrainResult:
    """One tick across every active tenant.

    A failure for one tenant must not stop the others: a single bad row would
    otherwise silence every boutique's reminders until someone noticed. The
    exception is logged, never swallowed silently, and the next tick retries the
    same rows because a rolled-back claim leaves them pending.
    """
    totals = DrainResult()
    # ponytail: O(tenants) queries per tick. Noise at pilot volume (a handful of
    # boutiques, one query each); E5 #29's scale pass is where this is revisited.
    for tenant in await tenants.list_active():
        try:
            result = await comms.drain_due(
                CommsTenant.from_settings(
                    tenant_id=tenant.id,
                    slug=tenant.slug,
                    name=tenant.name,
                    settings=tenant.settings,
                )
            )
        except Exception:
            logger.exception("scheduled-message drain failed for tenant %s", tenant.id)
            continue
        totals = DrainResult(
            sent=totals.sent + result.sent,
            failed=totals.failed + result.failed,
            cancelled=totals.cancelled + result.cancelled,
            deferred=totals.deferred + result.deferred,
        )
    if totals != DrainResult():
        logger.info(
            "scheduled messages: sent=%d failed=%d cancelled=%d deferred=%d",
            totals.sent,
            totals.failed,
            totals.cancelled,
            totals.deferred,
        )
    return totals


async def main() -> None:
    settings = get_settings()
    # The same fail-fast as the web app and the CLI. The worker keeps the
    # app_user URL — the stray MIGRATIONS_DATABASE_URL on that Railway service is
    # a recorded remediation, not something to start using.
    await ensure_safe_database_role()
    factory = get_session_factory()
    comms = BookingCommsService(
        factory,
        notifications=NotificationService(factory, sender=build_sender(settings)),
        base_domain=settings.base_domain,
    )
    tenants = TenantsRepository(factory)
    logger.info(
        "worker started — scheduled-message poller every %ds", settings.worker_poll_interval_seconds
    )
    while True:
        await poll_once(comms, tenants)
        await asyncio.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
