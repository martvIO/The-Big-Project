"""The worker's poll loop, driven with fakes and no database.

What is worth testing here is not the SQL — the db-marked suite owns the
SKIP-LOCKED claim and F19's two sweep claims — but the loop's containment
properties, which are the ones a silent regression would cost most: every active
tenant is drained AND swept under its own context, and one tenant's failure in
either job must not silence every other boutique.
"""

import dataclasses
import uuid
from typing import Any

from app.booking.comms import CommsTenant, DrainResult
from app.core.config import Settings
from app.payments.sweeper import SweepResult
from app.worker import build_sender, poll_once


@dataclasses.dataclass(frozen=True)
class _Tenant:
    """Only the fields CommsTenant.from_settings reads off a tenants row."""

    id: uuid.UUID
    slug: str
    name: str
    settings: dict[str, Any]


class FakeTenants:
    def __init__(self, tenants: list[_Tenant]) -> None:
        self._tenants = tenants
        self.calls = 0

    async def list_active(self) -> list[_Tenant]:
        self.calls += 1
        return self._tenants


class FakeComms:
    """Programmable per tenant: a DrainResult to return, or an exception to raise."""

    def __init__(self, outcomes: dict[uuid.UUID, DrainResult | Exception]) -> None:
        self._outcomes = outcomes
        self.drained: list[CommsTenant] = []

    async def drain_due(self, tenant: CommsTenant, *, limit: int = 50) -> DrainResult:
        self.drained.append(tenant)
        outcome = self._outcomes.get(tenant.id, DrainResult())
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeSweeper:
    """Programmable per tenant, exactly like FakeComms — the sweep's own SQL is
    the db suite's business; what belongs here is that it runs at all."""

    def __init__(self, outcomes: dict[uuid.UUID, SweepResult | Exception] | None = None) -> None:
        self._outcomes = outcomes or {}
        self.swept: list[uuid.UUID] = []

    async def sweep(self, tenant_id: uuid.UUID) -> SweepResult:
        self.swept.append(tenant_id)
        outcome = self._outcomes.get(tenant_id, SweepResult())
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _tenant(slug: str, *, phone: str | None = "052-1234567") -> _Tenant:
    profile: dict[str, Any] = {} if phone is None else {"phone": phone}
    return _Tenant(id=uuid.uuid4(), slug=slug, name=f"בוטיק {slug}", settings={"profile": profile})


async def test_every_active_tenant_is_drained_once_per_tick() -> None:
    tenants = [_tenant("bella"), _tenant("vered")]
    comms = FakeComms({tenants[0].id: DrainResult(sent=2), tenants[1].id: DrainResult(sent=1)})

    totals = await poll_once(comms, FakeTenants(tenants), FakeSweeper())  # type: ignore[arg-type]

    assert [t.slug for t in comms.drained] == ["bella", "vered"]
    assert totals == DrainResult(sent=3)


async def test_the_tenants_identity_reaches_the_drain_including_the_published_phone() -> None:
    """The link is built from the SLUG and the owner-cancel body points at the
    PHONE, so a loop that passed only the id would produce bodies naming the
    wrong boutique — or a link on the wrong host."""
    tenant = _tenant("bella")
    comms = FakeComms({})

    await poll_once(comms, FakeTenants([tenant]), FakeSweeper())  # type: ignore[arg-type]

    [seen] = comms.drained
    assert (seen.id, seen.slug, seen.name) == (tenant.id, "bella", "בוטיק bella")
    assert seen.phone == "052-1234567"


async def test_a_blank_profile_phone_collapses_to_none() -> None:
    """Same ""-to-null rule as the public projection: an owner who cleared the
    field left "" or " " behind, and a body must not name a phone that is
    whitespace."""
    tenant = _tenant("bella", phone=None)
    comms = FakeComms({})
    await poll_once(comms, FakeTenants([tenant]), FakeSweeper())  # type: ignore[arg-type]
    assert comms.drained[0].phone is None


async def test_one_tenants_failure_does_not_silence_the_others() -> None:
    """The containment property. Without it a single bad row would stop every
    boutique's reminders until somebody noticed — and nothing is watching the
    worker (spec Risk 5)."""
    broken, healthy = _tenant("broken"), _tenant("healthy")
    comms = FakeComms({broken.id: RuntimeError("claim blew up"), healthy.id: DrainResult(sent=1)})

    totals = await poll_once(comms, FakeTenants([broken, healthy]), FakeSweeper())  # type: ignore[arg-type]

    assert [t.slug for t in comms.drained] == ["broken", "healthy"]
    # The failing tenant contributes nothing and its rows stay pending, so the
    # next tick retries them.
    assert totals == DrainResult(sent=1)


async def test_a_quiet_tick_totals_to_nothing() -> None:
    tenants = FakeTenants([_tenant("bella")])
    totals = await poll_once(FakeComms({}), tenants, FakeSweeper())  # type: ignore[arg-type]
    assert totals == DrainResult()


async def test_no_tenants_is_not_an_error() -> None:
    swept = FakeSweeper()
    assert await poll_once(FakeComms({}), FakeTenants([]), swept) == DrainResult()  # type: ignore[arg-type]
    assert swept.swept == []


async def test_every_active_tenant_is_swept_once_per_tick() -> None:
    """D7. The sweeper is the ONLY writer that can move a booking off
    `pending_payment`, so a tenant the loop skips holds that seat forever."""
    tenants = [_tenant("bella"), _tenant("vered")]
    sweeper = FakeSweeper({tenants[0].id: SweepResult(expired=1, released=1)})

    await poll_once(FakeComms({}), FakeTenants(tenants), sweeper)  # type: ignore[arg-type]

    assert sweeper.swept == [tenants[0].id, tenants[1].id]


async def test_a_sweep_failure_does_not_stop_the_other_tenants() -> None:
    """The sweep gets its OWN try/except (D7). Sharing the drain's would let one
    bad payment row silence every boutique's reminders — and a sweep that raised
    out of the loop would strand every LATER boutique's held seats."""
    broken, healthy = _tenant("broken"), _tenant("healthy")
    comms = FakeComms({})
    sweeper = FakeSweeper({broken.id: RuntimeError("expiry blew up")})

    totals = await poll_once(comms, FakeTenants([broken, healthy]), sweeper)  # type: ignore[arg-type]

    assert sweeper.swept == [broken.id, healthy.id]
    # And the reminders are untouched by a payments failure — the whole reason
    # the two jobs do not share a try block.
    assert [t.slug for t in comms.drained] == ["broken", "healthy"]
    assert totals == DrainResult()


async def test_a_drain_failure_defers_that_tenants_sweep_to_the_next_tick() -> None:
    """The accepted asymmetry of ordering the drain first: the spec's named harm
    is a payment row silencing reminders, so the sweep is what moves. A skipped
    sweep costs one tick — the rows are still `pending` and the next tick claims
    them — whereas the reverse ordering would realise the named harm."""
    broken, healthy = _tenant("broken"), _tenant("healthy")
    comms = FakeComms({broken.id: RuntimeError("claim blew up")})
    sweeper = FakeSweeper()

    await poll_once(comms, FakeTenants([broken, healthy]), sweeper)  # type: ignore[arg-type]

    assert sweeper.swept == [healthy.id]


def test_sweep_results_add_up_across_tenants() -> None:
    assert SweepResult(expired=1, released=1) + SweepResult(expired=2, orphaned=3) == SweepResult(
        expired=3, released=1, orphaned=3
    )


def test_the_worker_degrades_to_the_unconfigured_sender_by_default() -> None:
    """No provider is a SUPPORTED deployment for the worker: due rows are left
    pending and flush on the first tick after an adapter lands."""
    assert build_sender(Settings(sms_provider=None)).is_configured is False
    assert build_sender(Settings(sms_provider="fake")).is_configured is True


def test_the_poll_interval_is_settings_tunable() -> None:
    """Deploy-tunable without a code change, and a missed window self-heals
    because the claim is `send_after <= now()` rather than an exact-time match."""
    assert Settings().worker_poll_interval_seconds == 60
    assert Settings(worker_poll_interval_seconds=5).worker_poll_interval_seconds == 5


def test_the_deposit_hold_is_settings_tunable_and_defaults_to_fifteen_minutes() -> None:
    """D6 is explicit that the hold length is NOT one of the recorded money
    decisions: one env var, reversible in a deploy, no data migration. Its only
    irreversible consequence is the width of the expiry-vs-webhook race, which
    is what test_deposit_sweeper_db parameterizes."""
    assert Settings().deposit_hold_seconds == 900
    assert Settings(deposit_hold_seconds=60).deposit_hold_seconds == 60
