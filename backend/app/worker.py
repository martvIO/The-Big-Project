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
import datetime
import logging

from app.booking.comms import BookingCommsService, CommsTenant, DrainResult
from app.core.config import Settings, get_settings
from app.db.repositories.tenants import TenantsRepository
from app.db.session import ensure_safe_database_role, get_session_factory
from app.notifications.base import SmsSender
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService
from app.notifications.twilio import TwilioSmsSender
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.payments.sweeper import DepositSweeper, SweepResult
from app.privacy.retention import RetentionRunner
from app.waitlist.cascade import CascadeResult, WaitlistCascade

logger = logging.getLogger("worker")


def build_sender(settings: Settings) -> SmsSender:
    """Mirrors `main._build_sms_sender`, including the observability line: no
    provider is a SUPPORTED state here (due rows are simply left pending until an
    adapter lands), and `Settings.model_config` is extra="ignore", so a typo'd
    SMS_PROVDER would otherwise degrade in silence.

    This process needs the SAME dispatch as the API, not a subset: reminders and
    confirmations drain here, so a `twilio` deployment wired only in main.py
    would send OTPs while every scheduled message sat pending forever."""
    if settings.sms_provider == "fake":
        logger.info("SMS sender: FAKE (in-memory outbox) — no real SMS will be sent")
        return FakeSmsSender()
    if settings.sms_provider == "twilio":
        sender = TwilioSmsSender(settings)
        if sender.is_configured:
            logger.info("SMS sender: TWILIO — real sends from %s", sender.from_number)
        else:
            logger.warning(
                "SMS sender: TWILIO selected but one or more TWILIO_* variables are "
                "missing — due reminders will be left pending"
            )
        return sender
    logger.info("SMS sender NOT configured — due reminders will be left pending")
    return UnconfiguredSmsSender()


async def poll_once(
    comms: BookingCommsService,
    tenants: TenantsRepository,
    sweeper: DepositSweeper,
    cascade: WaitlistCascade,
) -> DrainResult:
    """One tick across every active tenant: drain due messages, release expired
    deposit holds (F19 D7), then run the waitlist offer cascade (F23 D2).

    A failure for one tenant must not stop the others: a single bad row would
    otherwise silence every boutique's reminders until someone noticed. The
    exception is logged, never swallowed silently, and the next tick retries the
    same rows because a rolled-back claim leaves them pending.

    The jobs get SEPARATE try blocks. Sharing one would let a bad payment row
    silence a boutique's reminders, which is the harm D7 names. The residual
    asymmetry is deliberate and stated: the drain runs first, so a drain failure
    defers that tenant's sweep by one tick. Its rows are still `pending` and the
    next tick claims them; the reverse ordering would realise the named harm
    instead.

    **The cascade runs LAST**, and that is the same argument one job further on:
    it is the newest and least-proven of the three, its work is the least urgent
    (an offer lagging one tick is invisible against a two-hour window), and put
    anywhere earlier its failure would add a boutique's reminders or its held
    seats to the bill. `cascade` is a REQUIRED argument for the reason the drain
    and the sweep are: a defaulted one turns a wiring bug into a boutique whose
    waitlist silently never advances.
    """
    totals = DrainResult()
    swept = SweepResult()
    cascaded = CascadeResult()
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
        try:
            swept = swept + await sweeper.sweep(tenant.id)
        except Exception:
            logger.exception("deposit hold sweep failed for tenant %s", tenant.id)
            continue
        try:
            cascaded = cascaded + await cascade.run(tenant.id)
        except Exception:
            logger.exception("waitlist offer cascade failed for tenant %s", tenant.id)
            continue
    if cascaded != CascadeResult():
        logger.info(
            "waitlist offers: expired=%d returned=%d offered=%d",
            cascaded.expired,
            cascaded.returned,
            cascaded.offered,
        )
    if swept != SweepResult():
        logger.info(
            "deposit holds: expired=%d released=%d orphaned=%d",
            swept.expired,
            swept.released,
            swept.orphaned,
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


async def retention_tick(
    runner: RetentionRunner,
    *,
    now: datetime.datetime,
    next_at: datetime.datetime,
    enabled: bool,
    interval_seconds: int,
) -> datetime.datetime:
    """The THIRD job, and the one comparison that separates its hourly cadence
    from the poller's 60-second one. Returns the next deadline — unchanged when
    it did not fire, so `main()`'s loop is one reassignment.

    It is its own function rather than a branch inside `poll_once` because
    `poll_once` is per-TICK and this is per-HOUR, and because `main()` is a bare
    `while True:` that no test can drive: a cadence assertion written against it
    would have to mock `asyncio.sleep` around an infinite loop, which is a hang
    rather than a test.

    Its own try block, exactly as the drain and the sweep have theirs (D7). An
    exception escaping here kills the process loop and takes every boutique's
    reminders AND the deposit-hold sweeper with it — retention is the least
    urgent of the three and must never be the one that stops them.

    The deadline advances even on failure. A permanently failing run that kept
    its deadline in the past would re-enter on every 60-second poll instead of
    hourly, turning one broken tenant into a hot loop against the database.
    """
    if not enabled or now < next_at:
        return next_at
    try:
        result = await runner.run()
    except Exception:
        logger.exception("retention run failed")
    else:
        if result.rows or result.failed_tenants:
            logger.info(
                "retention: tenants=%d failed=%d rows=%s",
                result.tenants,
                result.failed_tenants,
                result.rows,
            )
    return now + datetime.timedelta(seconds=interval_seconds)


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
    # No gateway, no secret box, no credential service: the sweep issues two
    # UPDATEs and calls nobody. That is the whole reason expiry is its own class
    # rather than a PaymentService method — see app/payments/sweeper.py.
    sweeper = DepositSweeper(
        factory,
        hold_seconds=settings.deposit_hold_seconds,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )
    # No SMS sender and no gateway either: the cascade WRITES the offer row and
    # queues the SMS through `scheduled_messages`, so the drain above is what
    # eventually sends it. That is #16's "no second poller, no second process"
    # honoured to the letter.
    cascade = WaitlistCascade(
        factory,
        window_seconds=settings.waitlist_offer_window_seconds,
        min_lead_seconds=settings.waitlist_offer_min_lead_seconds,
        quiet_start_hour=settings.waitlist_quiet_start_hour,
        quiet_end_hour=settings.waitlist_quiet_end_hour,
    )
    retention = RetentionRunner(factory, settings=settings)
    # Due immediately, so an operator who flips RETENTION_ENABLED does not wait
    # an hour to see the first run. With the flag off (the shipped default) this
    # deadline is never read.
    next_retention_at = datetime.datetime.now(datetime.UTC)
    logger.info(
        "worker started — scheduled-message poller, deposit-hold sweeper and waitlist "
        "offer cascade every %ds; retention %s, every %ds",
        settings.worker_poll_interval_seconds,
        "ENABLED" if settings.retention_enabled else "disabled",
        settings.retention_poll_interval_seconds,
    )
    while True:
        await poll_once(comms, tenants, sweeper, cascade)
        next_retention_at = await retention_tick(
            retention,
            now=datetime.datetime.now(datetime.UTC),
            next_at=next_retention_at,
            enabled=settings.retention_enabled,
            interval_seconds=settings.retention_poll_interval_seconds,
        )
        await asyncio.sleep(settings.worker_poll_interval_seconds)


def configure_logging() -> None:
    """httpx logs a request line per send at INFO and the Twilio Account SID is
    in the URL path, so left at INFO this process stamps an account identifier
    into the log on every reminder — the one place a credential-shaped value
    reaches a log line, in a stream that needs it for nothing. The API process
    is already clear (uvicorn leaves root at WARNING with no handler); this one
    calls basicConfig, so it has to say so itself."""
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
