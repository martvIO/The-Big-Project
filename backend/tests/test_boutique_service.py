"""Feature 7 repository + service integration on real Postgres as boutique_app:
CRUD per resource, advisory-locked weekly replace, terms version race with the
fresh-session retry, DB-enforced terms immutability, CHECK rejects, atomic
settings merge under concurrency, and cross-tenant invisibility."""

import asyncio
import datetime
import json
import time
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.boutique.service import (
    BoutiqueSettingsService,
    DuplicateDateError,
    DuplicateNameError,
    NotFoundError,
    TermsThrottledError,
    TermsVersionConflictError,
)
from app.boutique.toggles import TOGGLE_DEFAULTS, TOGGLE_KEYS
from app.boutique.validation import BoutiqueValidationError, WeeklyRuleInput
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import AppointmentAudience, AuditAction, StaffRole
from app.models.terms_version import TermsVersion


def _actor(tenant_id: uuid.UUID) -> StaffContext:
    """F42 (D5 edit #7): `update_settings` names the staffer who saved. It is a
    REQUIRED keyword because `audit_log.actor_id` is nullable — an actor-less row
    would insert silently and green. No row is written for these calls at all:
    they carry no `atelier` block, and F42 audits only the key it owns."""
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


pytestmark = pytest.mark.db

STAFF_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _engine(app_role_url: str) -> AsyncEngine:
    # NullPool: the concurrency tests need genuinely separate connections.
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _service(
    factory: async_sessionmaker[AsyncSession],
    limiter: FixedWindowRateLimiter | None = None,
) -> BoutiqueSettingsService:
    return BoutiqueSettingsService(
        factory,
        terms_rate_limiter=limiter
        or FixedWindowRateLimiter(max_attempts=1000, window_seconds=3600, clock=time.monotonic),
    )


def _rule(day: int, open_h: int, close_h: int, capacity: int = 1) -> WeeklyRuleInput:
    return WeeklyRuleInput(
        day_of_week=day,
        open_time=datetime.time(open_h, 0),
        close_time=datetime.time(close_h, 0),
        capacity=capacity,
    )


async def _create_terms(
    service: BoutiqueSettingsService, tenant_id: uuid.UUID, terms_text: str = "Cancel 48h before."
) -> TermsVersion:
    return await service.create_terms_version(
        tenant_id,
        terms_text=terms_text,
        refundable_until_hours_before=48,
        forfeit_percent=100,
        created_by=STAFF_ID,
    )


# --- settings (tenants.settings JSONB, atomic merge) ---


async def test_settings_roundtrip_and_partial_merge(app_role_url: str) -> None:
    """⚠ THIS TEST'S TOGGLES CONTRACT CHANGED AT F27, DELIBERATELY, AND IT IS THE
    ONE `merge_settings` TEST THAT DID.

    It shipped asserting `again.toggles == {"deposits_enabled": False}` after a
    single-key save — i.e. it PINNED the clobber: `brides_only`, saved a moment
    earlier, was gone. That was correct against `||`'s shallow merge and it is
    what D2 abolishes. It now asserts the invariant the matrix needs — the
    sibling toggle survives a single-key write — and the empty-block assertion
    becomes the registry defaults (D3: the wire is default-complete).

    Every OTHER shipped `merge_settings` assertion in this file stands unedited.
    That was the tripwire: a second one wanting a rewrite would have meant the
    merge expression was wrong, not the test.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"settings-{uuid.uuid4().hex[:8]}", name="Bella")

        initial = await service.get_settings(tenant.id)
        # D3: a brand-new boutique has NO toggles key at all, and the wire still
        # carries every registry key with a concrete bool.
        assert initial.profile == {}
        assert initial.toggles == TOGGLE_DEFAULTS

        updated = await service.update_settings(
            tenant.id,
            actor=_actor(tenant.id),
            profile={"phone": "+972-3-555-0100", "description": "Bridal boutique"},
            toggles={"deposits_enabled": True, "brides_only": False},
        )
        assert updated.profile["phone"] == "+972-3-555-0100"
        assert updated.toggles == {"deposits_enabled": True, "brides_only": False}

        # Toggles-only update: the profile key must be left untouched (only the
        # provided keys enter the patch)...
        await service.update_settings(
            tenant.id, actor=_actor(tenant.id), toggles={"brides_only": True}
        )
        again = await service.get_settings(tenant.id)
        assert again.profile["phone"] == "+972-3-555-0100"
        # ...and so must the SIBLING TOGGLE. `deposits_enabled: True` was never
        # named by the second patch and is still True — that is D2, and before it
        # this line read `== {"brides_only": True}`.
        assert again.toggles == {"deposits_enabled": True, "brides_only": True}
    finally:
        await engine.dispose()


async def test_update_settings_rejects_javascript_maps_url(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"xss-{uuid.uuid4().hex[:8]}", name="XSS")
        with pytest.raises(BoutiqueValidationError):
            await service.update_settings(
                tenant.id, actor=_actor(tenant.id), profile={"maps_url": "javascript:alert(1)"}
            )
        unchanged = await service.get_settings(tenant.id)
        assert unchanged.profile == {}
    finally:
        await engine.dispose()


async def test_settings_unknown_tenant_raises_not_found(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    try:
        with pytest.raises(NotFoundError):
            await service.get_settings(uuid.uuid4())
        with pytest.raises(NotFoundError):
            missing = uuid.uuid4()
            await service.update_settings(
                missing, actor=_actor(missing), toggles={"brides_only": True}
            )
    finally:
        await engine.dispose()


ATELIER_BANDS = {
    "thirty_min": 30,
    "one_hour": 60,
    "two_hours": 120,
    "half_day": 300,
    "full_day": 540,
}


async def test_an_atelier_save_lands_whole_leaves_its_siblings_and_writes_its_audit_row(
    app_role_url: str,
) -> None:
    """F42 (D5, D12) against the REAL service and a real Postgres — which is the
    only place the validator call, the JSONB round trip and the audit row are all
    exercised together. The fast API tests run a FAKE service that calls
    `validate_atelier_settings` itself, so `update_settings` dropping that call
    is invisible to every one of them.

    Three things in one pass: the whole block round-trips through `||`, the
    sibling top-level keys written by an earlier save are untouched, and the
    audit row carries its actor and the whole NEW value with no `from`.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"atelier-{uuid.uuid4().hex[:8]}", name="Atelier")
        actor = _actor(tenant.id)

        await service.update_settings(
            tenant.id,
            actor=actor,
            profile={"phone": "+972-3-555-0100"},
            toggles={"deposits_enabled": True},
        )
        saved = await service.update_settings(
            tenant.id,
            actor=actor,
            atelier={
                "effort_bands": ATELIER_BANDS,
                "default_weekly_capacity_hours": 36,
            },
        )

        assert saved.atelier == {
            "effort_bands": ATELIER_BANDS,
            "default_weekly_capacity_hours": 36,
        }
        # The top level is safe by the atomic `||` and NOT by anything F42 added.
        assert saved.profile == {"phone": "+972-3-555-0100"}
        # ⚠ `brides_only: False` is F27 D3 and NOT a merge change: the STORED
        # block is still the one key this test wrote, and `_settings_result`
        # overlays the registry defaults on the way out. The merge assertion —
        # that an atelier-only save leaves `deposits_enabled` True — is untouched.
        assert saved.toggles == {"deposits_enabled": True, "brides_only": False}

        # And it is really in the column, not merely in the answer.
        again = await service.get_settings(tenant.id)
        assert again.atelier["default_weekly_capacity_hours"] == 36
        assert again.atelier["effort_bands"]["half_day"] == 300

        async with tenant_session(factory, tenant.id) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog).where(
                            AuditLog.action == AuditAction.ATELIER_SETTINGS_UPDATED.value
                        )
                    )
                ).all()
            )
        # ⚠ ONE ROW, not two: the profile/toggles save carried no `atelier` block
        # and F42 audits only the key it owns (the shipped settings path stays
        # unaudited — a pre-existing gap this feature does not widen).
        assert len(rows) == 1
        assert rows[0].actor_id == actor.id
        assert rows[0].entity == str(tenant.id)
        # The whole NEW value and NO `from`: the trail IS the history, and a diff
        # would need the read-modify-write the atomic statement exists to avoid.
        assert rows[0].details == {
            "effort_bands": ATELIER_BANDS,
            "default_weekly_capacity_hours": 36,
        }
        assert "from" not in rows[0].details
    finally:
        await engine.dispose()


async def test_a_partial_band_mapping_is_refused_and_writes_nothing(
    app_role_url: str,
) -> None:
    """`test_update_settings_rejects_javascript_maps_url`'s shape, on F42's
    block: the validator runs BEFORE storage is touched, so a refused save leaves
    the column exactly as it was and writes no audit row.

    ⚠ The MISSING key is the half no request model can see, which is why this
    reaches the service at all — `dict[EffortBand, StrictInt]` would have
    refused an unknown one at the wire.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"partial-{uuid.uuid4().hex[:8]}", name="Partial")
        partial = {key: value for key, value in ATELIER_BANDS.items() if key != "full_day"}
        with pytest.raises(BoutiqueValidationError):
            await service.update_settings(
                tenant.id,
                actor=_actor(tenant.id),
                atelier={
                    "effort_bands": partial,
                    "default_weekly_capacity_hours": 36,
                },
            )
        unchanged = await service.get_settings(tenant.id)
        assert unchanged.atelier == {}

        async with tenant_session(factory, tenant.id) as session:
            written = list(
                (
                    await session.scalars(
                        select(AuditLog).where(
                            AuditLog.action == AuditAction.ATELIER_SETTINGS_UPDATED.value
                        )
                    )
                ).all()
            )
        assert written == []
    finally:
        await engine.dispose()


async def test_the_settings_audit_row_is_written_only_after_a_successful_merge(
    app_role_url: str,
) -> None:
    """⚠ D12's ORDERING, AND IT IS THE ASSERTION THAT MAKES THE COMPROMISE
    BOUNDED. The row cannot ride `merge_settings`' transaction —
    `TenantsRepository` opens its own session inside every method — so it is
    written afterwards, in its own. That is one-directional by construction: a
    crash between the two LOSES a row and can never INVENT one.

    Move the `record` call above the merge and this reds: a save against a
    missing or soft-deleted tenant would leave an audit row claiming the
    boutique's band mapping changed when nothing did.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    missing = uuid.uuid4()
    try:
        with pytest.raises(NotFoundError):
            await service.update_settings(
                missing,
                actor=_actor(missing),
                atelier={
                    "effort_bands": ATELIER_BANDS,
                    "default_weekly_capacity_hours": 36,
                },
            )
        async with tenant_session(factory, missing) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog).where(
                            AuditLog.action == AuditAction.ATELIER_SETTINGS_UPDATED.value
                        )
                    )
                ).all()
            )
        assert rows == [], "an audit row was written for a merge that never happened"
    finally:
        await engine.dispose()


async def test_merge_settings_preserves_concurrently_written_sibling_key(
    app_role_url: str,
) -> None:
    """The atomic || merge must never clobber a sibling top-level key written by
    a concurrent transaction (E4 will add such keys) — by construction, not luck."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"merge-{uuid.uuid4().hex[:8]}", name="Merge")

        async def write_sibling() -> None:
            async with factory() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE tenants SET settings = settings || CAST(:patch AS jsonb) "
                        "WHERE id = :tenant_id"
                    ),
                    {
                        "patch": json.dumps({"marketing": {"consent_default": True}}),
                        "tenant_id": tenant.id,
                    },
                )

        await asyncio.gather(
            tenants.merge_settings(tenant.id, profile={"phone": "03-555-0100"}),
            write_sibling(),
        )

        refreshed = await tenants.by_id(tenant.id)
        assert refreshed is not None
        assert refreshed.settings["marketing"] == {"consent_default": True}
        assert refreshed.settings["profile"] == {"phone": "03-555-0100"}
    finally:
        await engine.dispose()


# --- F27 D2: the `toggles` key merges DEEP, and only that key ---


async def test_two_concurrent_single_key_toggle_writes_both_survive(
    app_role_url: str,
) -> None:
    """⚠ THE TEST F27 EXISTS FOR, one level down from its neighbour above.

    That test proves the TOP level is safe under `||`. This one proves the level
    BELOW `toggles` is, which `||` alone does NOT give: a shallow merge replaces
    the whole `toggles` object, so two writers each saving their own switch would
    have the loser's key deleted. The matrix saves per row — one key per PUT — so
    that is not a hypothetical interleave, it is two clicks a second apart.

    `asyncio.gather` is legitimate here for the same reason it is above: the
    mechanism is one atomic UPDATE each, so whichever runs second blocks on the
    row lock, re-reads and merges, and the ORDER is irrelevant to the outcome.
    Replace the SET expression with a Python read-modify-write and this reds.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"toggles-{uuid.uuid4().hex[:8]}", name="Toggles")

        await asyncio.gather(
            tenants.merge_settings(tenant.id, toggles={"deposits_enabled": True}),
            tenants.merge_settings(tenant.id, toggles={"brides_only": True}),
        )

        refreshed = await tenants.by_id(tenant.id)
        assert refreshed is not None
        assert refreshed.settings["toggles"] == {"deposits_enabled": True, "brides_only": True}
    finally:
        await engine.dispose()


async def test_a_single_key_toggle_patch_lands_on_a_tenant_with_no_toggles_key(
    app_role_url: str,
) -> None:
    """⚠ `coalesce(settings->'toggles','{}'::jsonb)` IS MANDATORY AND THIS IS THE
    TEST THAT SAYS SO. Provisioning seeds no toggles at all, so an absent key is
    EVERY tenant on day one — and the obvious `jsonb_set` reach silently returns
    `settings` UNCHANGED when the intermediate object is missing (`create_missing`
    creates the leaf, not the object). It fails with no error, on every boutique.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"absent-{uuid.uuid4().hex[:8]}", name="Absent")
        assert "toggles" not in (tenant.settings or {})

        merged = await tenants.merge_settings(tenant.id, toggles={"brides_only": True})

        assert merged is not None
        assert merged["toggles"] == {"brides_only": True}
    finally:
        await engine.dispose()


async def test_a_toggles_patch_leaves_profile_atelier_and_privacy_untouched(
    app_role_url: str,
) -> None:
    """The deep merge is scoped to ONE key. `profile`/`atelier`/`privacy` keep
    whole-block-replace semantics — their "one writer always sends the whole
    block" models are load-bearing and F27 does not touch them — so the top-level
    `||` must still carry them through unchanged."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"siblings-{uuid.uuid4().hex[:8]}", name="Siblings")
        atelier = {"effort_bands": ATELIER_BANDS, "default_weekly_capacity_hours": 36}
        privacy = {"controller_name": "Bella", "retention_months": 24}
        await tenants.merge_settings(
            tenant.id,
            profile={"phone": "03-555-0100"},
            toggles={"deposits_enabled": True},
            atelier=atelier,
            privacy=privacy,
        )

        merged = await tenants.merge_settings(tenant.id, toggles={"brides_only": True})

        assert merged is not None
        assert merged["profile"] == {"phone": "03-555-0100"}
        assert merged["atelier"] == atelier
        assert merged["privacy"] == privacy
        # And the sibling TOGGLE — the one the shallow merge used to delete.
        assert merged["toggles"] == {"deposits_enabled": True, "brides_only": True}
    finally:
        await engine.dispose()


async def test_a_profile_patch_alongside_toggles_still_replaces_its_whole_block(
    app_role_url: str,
) -> None:
    """The scoping, asserted from the other side: `profile` did NOT quietly
    become a deep merge too. Its one-writer-sends-the-whole-block model is what
    makes an omitted field a CLEAR there, and a deep merge would silently turn
    every clear into a no-op."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"scope-{uuid.uuid4().hex[:8]}", name="Scope")
        await tenants.merge_settings(
            tenant.id, profile={"phone": "03-555-0100", "address": "דיזנגוף 100"}
        )

        merged = await tenants.merge_settings(
            tenant.id, profile={"phone": "03-555-0199"}, toggles={"brides_only": True}
        )

        assert merged is not None
        assert merged["profile"] == {"phone": "03-555-0199"}
        assert merged["toggles"] == {"brides_only": True}
    finally:
        await engine.dispose()


async def test_a_get_after_a_partial_toggle_write_returns_the_whole_block(
    app_role_url: str,
) -> None:
    """D2 and D3 together, through the real service and a real column — the pair
    the matrix depends on and which no fast test can prove jointly. The fast
    `_settings_result` units cannot see the merge; the merge tests above read raw
    JSONB and never touch the overlay."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"wire-{uuid.uuid4().hex[:8]}", name="Wire")

        saved = await service.update_settings(
            tenant.id, actor=_actor(tenant.id), toggles={"brides_only": True}
        )
        assert saved.toggles == {"deposits_enabled": False, "brides_only": True}

        again = await service.get_settings(tenant.id)
        assert again.toggles == {"deposits_enabled": False, "brides_only": True}

        # Every registry key, always — the FE matrix renders one row per wire key.
        assert set(again.toggles) == set(TOGGLE_KEYS)
    finally:
        await engine.dispose()


# --- F27 D6: TOGGLES_UPDATED ---


async def test_a_toggles_write_records_its_actor_and_its_patch(app_role_url: str) -> None:
    """D6, on `_record_atelier_settings`' pattern verbatim: post-merge, own
    transaction, one-directional loss. Same justification, one key over —
    `deposits_enabled` changes whether the boutique collects money, and «nobody
    can say who or when» is the worse state.

    `details` is THE PATCH — the changed keys only, never the merged block. The
    trail IS the history, so the previous value is the previous row's, and
    computing a diff would need the read-modify-write the atomic statement exists
    to avoid. A merged block here would also make every row look like a full
    rewrite of a matrix the owner touched one switch on.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"audit-{uuid.uuid4().hex[:8]}", name="Audit")
        actor = _actor(tenant.id)

        await service.update_settings(
            tenant.id, actor=actor, toggles={"deposits_enabled": True, "brides_only": True}
        )
        await service.update_settings(tenant.id, actor=actor, toggles={"brides_only": False})

        async with tenant_session(factory, tenant.id) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog)
                        .where(AuditLog.action == AuditAction.TOGGLES_UPDATED.value)
                        .order_by(AuditLog.created_at)
                    )
                ).all()
            )
        assert len(rows) == 2
        assert all(row.actor_id == actor.id for row in rows)
        assert all(row.entity == str(tenant.id) for row in rows)
        assert rows[0].details == {"deposits_enabled": True, "brides_only": True}
        # The PATCH, not the merged block — `deposits_enabled` is still True in
        # the column and deliberately absent from this row.
        assert rows[1].details == {"brides_only": False}
    finally:
        await engine.dispose()


async def test_a_profile_only_write_records_no_toggles_row(app_role_url: str) -> None:
    """F42's boundary, held from the other side. F27 audits the key it now OWNS
    and does not widen the gap it did not create: `profile` stays unaudited, and
    `test_audit_coverage.py`'s partial-audit note says so in writing."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"noaudit-{uuid.uuid4().hex[:8]}", name="NoAudit")
        await service.update_settings(
            tenant.id, actor=_actor(tenant.id), profile={"phone": "03-555-0100"}
        )
        async with tenant_session(factory, tenant.id) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog).where(AuditLog.action == AuditAction.TOGGLES_UPDATED.value)
                    )
                ).all()
            )
        assert rows == []
    finally:
        await engine.dispose()


async def test_the_toggles_audit_row_is_written_only_after_a_successful_merge(
    app_role_url: str,
) -> None:
    """D12's ordering, on F27's key. A save against a missing or soft-deleted
    tenant must leave no row claiming the boutique flipped a switch — the
    compromise is bounded only because a crash between merge and audit LOSES a
    row and can never INVENT one."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    missing = uuid.uuid4()
    try:
        with pytest.raises(NotFoundError):
            await service.update_settings(
                missing, actor=_actor(missing), toggles={"deposits_enabled": True}
            )
        async with tenant_session(factory, missing) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog).where(AuditLog.action == AuditAction.TOGGLES_UPDATED.value)
                    )
                ).all()
            )
        assert rows == [], "an audit row was written for a merge that never happened"
    finally:
        await engine.dispose()


# The uncommitted-writer interleave's two windows — `test_queue_dispatch_db.py`'s
# numbers.
HOLD_SECONDS = 0.6
ISSUE_SECONDS = 0.05


async def test_an_atelier_patch_does_not_clobber_a_concurrent_profile_write(
    app_role_url: str,
) -> None:
    """⚠ THE SAME CLAIM AS THE TEST ABOVE AND DELIBERATELY NOT ITS METHOD, AND
    THE NEIGHBOUR IS THE TRAP.

    `test_merge_settings_preserves_concurrently_written_sibling_key` uses
    `asyncio.gather` LEGITIMATELY: its mechanism is `||` over two single-statement
    UPDATEs, so whichever runs second blocks on the row lock, re-reads and merges,
    and the ORDER is irrelevant to the outcome.

    F42's mutation is a different one — *replace the atomic statement with a
    Python read-modify-write* (`by_id` → mutate the dict → `UPDATE … SET settings
    = :whole`) — and its failure depends ENTIRELY on the losing writer's READ
    happening before the other's COMMIT and its WRITE after. Under `gather` that
    is luck: the read usually lands after the commit, the stale snapshot never
    forms, and the mutation survives green.

    So this one is ORDERED, by a lock rather than by a sleep. The sibling writer
    holds the row's write lock uncommitted; `merge_settings`' plain SELECT (in the
    mutated build) reads straight past it and sees settings WITHOUT `profile`,
    while its UPDATE blocks; the sibling commits; the UPDATE proceeds. The real
    `||` has no separate read at all, so it re-reads the committed row under
    EvalPlanQual and both keys survive. The mutation writes its stale whole and
    `profile` is gone.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"clobber-{uuid.uuid4().hex[:8]}", name="Clobber")
        written = asyncio.Event()

        async def _uncommitted_profile_write() -> None:
            async with factory() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE tenants SET settings = settings || CAST(:patch AS jsonb) "
                        "WHERE id = :tenant_id"
                    ),
                    {
                        "patch": json.dumps({"profile": {"phone": "03-555-0100"}}),
                        "tenant_id": tenant.id,
                    },
                )
                written.set()
                # Still UNCOMMITTED for this long, holding the row lock. Exiting
                # the block is the commit.
                await asyncio.sleep(HOLD_SECONDS)

        sibling = asyncio.create_task(_uncommitted_profile_write())
        await written.wait()
        await asyncio.sleep(ISSUE_SECONDS)

        merged = await tenants.merge_settings(
            tenant.id,
            atelier={"effort_bands": ATELIER_BANDS, "default_weekly_capacity_hours": 36},
        )
        await sibling

        assert merged is not None
        assert merged["profile"] == {"phone": "03-555-0100"}, (
            "the atelier save read a snapshot without the concurrent profile write "
            "and wrote the whole column back over it"
        )
        assert merged["atelier"]["default_weekly_capacity_hours"] == 36

        # …and it is really in the column, not merely in the RETURNING.
        refreshed = await tenants.by_id(tenant.id)
        assert refreshed is not None
        assert refreshed.settings["profile"] == {"phone": "03-555-0100"}
        assert refreshed.settings["atelier"]["effort_bands"] == ATELIER_BANDS
    finally:
        await engine.dispose()


async def test_two_sequential_atelier_saves_leave_the_SECOND_and_BOTH_audit_rows(
    app_role_url: str,
) -> None:
    """⚠ NOT A MUTATION — THE BEHAVIOUR IS THE ASSERTION, and it is D5's designed
    lost update.

    The block is replaced WHOLE on every save, so the second manager's mapping
    wins entirely and the first's tuned `half_day` is simply gone. There is no
    version, no if-match and no 409: a conflict dialog because a colleague
    touched the same settings four seconds ago is the platform second-guessing a
    staffing call that is hers to make.

    What makes that acceptable is the TRAIL, and this is where it is proved:
    BOTH saves leave an audit row carrying its whole new value, so the mapping
    that was overwritten is recoverable from `audit_log` even though nothing in
    `tenants` remembers it. That is also what makes D12's no-`from` choice
    load-bearing rather than lazy — the row before is the row before.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"lastwins-{uuid.uuid4().hex[:8]}", name="Last")
        first_actor, second_actor = _actor(tenant.id), _actor(tenant.id)
        second_bands = {**ATELIER_BANDS, "half_day": 240}

        await service.update_settings(
            tenant.id,
            actor=first_actor,
            atelier={"effort_bands": ATELIER_BANDS, "default_weekly_capacity_hours": 36},
        )
        saved = await service.update_settings(
            tenant.id,
            actor=second_actor,
            atelier={"effort_bands": second_bands, "default_weekly_capacity_hours": 20},
        )

        assert saved.atelier == {
            "effort_bands": second_bands,
            "default_weekly_capacity_hours": 20,
        }
        again = await service.get_settings(tenant.id)
        assert again.atelier["effort_bands"]["half_day"] == 240
        assert again.atelier["default_weekly_capacity_hours"] == 20

        async with tenant_session(factory, tenant.id) as session:
            rows = list(
                (
                    await session.scalars(
                        select(AuditLog)
                        .where(AuditLog.action == AuditAction.ATELIER_SETTINGS_UPDATED.value)
                        .order_by(AuditLog.created_at)
                    )
                ).all()
            )
        assert [row.actor_id for row in rows] == [first_actor.id, second_actor.id]
        # The overwritten mapping survives HERE and nowhere else.
        assert rows[0].details["effort_bands"]["half_day"] == 300
        assert rows[1].details["effort_bands"]["half_day"] == 240
        assert rows[0].details["default_weekly_capacity_hours"] == 36
    finally:
        await engine.dispose()


# --- appointment types CRUD ---


async def test_appointment_type_crud_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        created = await service.create_appointment_type(tenant, name="Fitting", duration_minutes=60)
        assert created.audience == AppointmentAudience.ALL
        assert created.deposit_required is False
        assert created.deposit_amount_agorot is None
        assert created.sort_order == 0

        listed = await service.list_appointment_types(tenant)
        assert [item.id for item in listed] == [created.id]

        updated = await service.update_appointment_type(
            tenant,
            created.id,
            name="First Fitting",
            duration_minutes=90,
            audience=AppointmentAudience.BRIDES_ONLY,
            deposit_required=True,
            deposit_amount_agorot=20_000,
            sort_order=1,
        )
        assert updated.name == "First Fitting"
        assert updated.duration_minutes == 90
        assert updated.updated_at is not None  # set by the DB trigger

        await service.archive_appointment_type(tenant, created.id)
        assert await service.list_appointment_types(tenant) == []

        # Archiving frees the name for reuse (partial unique index).
        again = await service.create_appointment_type(
            tenant, name="First Fitting", duration_minutes=45
        )
        assert again.id != created.id
    finally:
        await engine.dispose()


async def test_duplicate_active_type_name_raises(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        first = await service.create_appointment_type(tenant, name="Fitting", duration_minutes=60)
        with pytest.raises(DuplicateNameError):
            await service.create_appointment_type(tenant, name="Fitting", duration_minutes=30)
        other = await service.create_appointment_type(tenant, name="Pickup", duration_minutes=15)
        with pytest.raises(DuplicateNameError):
            await service.update_appointment_type(
                tenant,
                other.id,
                name="Fitting",
                duration_minutes=15,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        assert first.name == "Fitting"
    finally:
        await engine.dispose()


async def test_update_or_archive_missing_type_raises_not_found(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        with pytest.raises(NotFoundError):
            await service.update_appointment_type(
                tenant,
                uuid.uuid4(),
                name="Ghost",
                duration_minutes=30,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        with pytest.raises(NotFoundError):
            await service.archive_appointment_type(tenant, uuid.uuid4())
    finally:
        await engine.dispose()


# --- weekly rules: atomic replace under the per-tenant advisory lock ---


async def test_weekly_rules_replace_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        first = await service.replace_weekly_rules(tenant, [_rule(0, 9, 12), _rule(0, 12, 17)])
        assert len(first) == 2

        second = await service.replace_weekly_rules(tenant, [_rule(2, 10, 14, capacity=2)])
        assert len(second) == 1

        availability = await service.get_availability(tenant)
        assert [(r.day_of_week, r.capacity) for r in availability.rules] == [(2, 2)]

        # An invalid replacement must leave state untouched.
        with pytest.raises(BoutiqueValidationError):
            await service.replace_weekly_rules(tenant, [_rule(4, 9, 13), _rule(4, 12, 17)])
        untouched = await service.get_availability(tenant)
        assert [(r.day_of_week, r.capacity) for r in untouched.rules] == [(2, 2)]

        # Empty set = closed all week; valid.
        assert await service.replace_weekly_rules(tenant, []) == []
        assert (await service.get_availability(tenant)).rules == []
    finally:
        await engine.dispose()


async def test_concurrent_weekly_replaces_never_union(app_role_url: str) -> None:
    """Two concurrent replaces are serialized by pg_advisory_xact_lock — the
    final state is exactly ONE submitted set, never a union of both."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    set_a = [_rule(0, 9, 12), _rule(1, 9, 12)]
    set_b = [_rule(2, 10, 14), _rule(3, 10, 14), _rule(4, 10, 14)]
    try:
        await asyncio.gather(
            service.replace_weekly_rules(tenant, set_a),
            service.replace_weekly_rules(tenant, set_b),
        )
        final = await service.get_availability(tenant)
        days = sorted(rule.day_of_week for rule in final.rules)
        assert days in ([0, 1], [2, 3, 4]), f"union detected: {days}"
    finally:
        await engine.dispose()


# --- availability exceptions ---


async def test_availability_exceptions_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    closed_day = datetime.date(2026, 9, 23)
    special_day = datetime.date(2026, 9, 24)
    try:
        closed = await service.add_availability_exception(
            tenant, date=closed_day, open_time=None, close_time=None, note="Yom Kippur"
        )
        assert closed.open_time is None and closed.close_time is None

        special = await service.add_availability_exception(
            tenant,
            date=special_day,
            open_time=datetime.time(10, 0),
            close_time=datetime.time(13, 0),
        )
        assert special.open_time == datetime.time(10, 0)

        with pytest.raises(DuplicateDateError):
            await service.add_availability_exception(
                tenant, date=closed_day, open_time=None, close_time=None
            )

        with pytest.raises(BoutiqueValidationError):
            await service.add_availability_exception(
                tenant,
                date=datetime.date(2026, 9, 25),
                open_time=datetime.time(10, 0),
                close_time=None,
            )

        await service.remove_availability_exception(tenant, closed.id)
        remaining = (await service.get_availability(tenant)).exceptions
        assert [item.id for item in remaining] == [special.id]

        with pytest.raises(NotFoundError):
            await service.remove_availability_exception(tenant, closed.id)

        # Removal frees the date for a fresh exception (partial unique index).
        await service.add_availability_exception(
            tenant, date=closed_day, open_time=None, close_time=None
        )
    finally:
        await engine.dispose()


# --- terms versions: sequential, immutable, raced, throttled, paginated ---


async def test_terms_versions_are_sequential_with_history_pagination(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        empty = await service.get_terms_history(tenant)
        assert empty.current is None and empty.versions == [] and empty.total == 0

        for text_body in ("v1 terms", "v2 terms", "v3 terms"):
            await _create_terms(service, tenant, terms_text=text_body)

        history = await service.get_terms_history(tenant)
        assert history.current is not None and history.current.version == 3
        assert [item.version for item in history.versions] == [3, 2, 1]
        assert history.total == 3

        page = await service.get_terms_history(tenant, offset=1, limit=1)
        assert [item.version for item in page.versions] == [2]
        assert page.total == 3
    finally:
        await engine.dispose()


async def test_concurrent_terms_creates_stay_strictly_sequential(app_role_url: str) -> None:
    """The unique-index backstop + fresh-session retry: two racing creates must
    land as versions 1 and 2 — never a gap, never a duplicate, never a 500."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        created = await asyncio.gather(
            _create_terms(service, tenant, terms_text="racer A"),
            _create_terms(service, tenant, terms_text="racer B"),
        )
        assert sorted(item.version for item in created) == [1, 2]
        history = await service.get_terms_history(tenant)
        assert [item.version for item in history.versions] == [2, 1]
    finally:
        await engine.dispose()


class _StaleMaxOnceRepository(TermsVersionsRepository):
    """Serves a stale max exactly once — deterministically forces the unique
    collision so the fresh-session retry path is exercised every run."""

    def __init__(self, stale_reads: int) -> None:
        self._stale_reads = stale_reads

    async def max_version(self, session: AsyncSession, tenant_id: uuid.UUID) -> int:
        if self._stale_reads > 0:
            self._stale_reads -= 1
            return 0
        return await super().max_version(session, tenant_id)


async def test_terms_retry_recomputes_in_a_fresh_session(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        # First attempt sees a stale max (0), collides with v1, and must retry
        # in a FRESH tenant_session (the aborted one cannot be reused).
        service._terms = _StaleMaxOnceRepository(stale_reads=1)
        created = await _create_terms(service, tenant, terms_text="v2")
        assert created.version == 2
    finally:
        await engine.dispose()


async def test_terms_second_collision_raises_conflict(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        service._terms = _StaleMaxOnceRepository(stale_reads=2)
        with pytest.raises(TermsVersionConflictError):
            await _create_terms(service, tenant, terms_text="doomed")
        history = await service.get_terms_history(tenant)
        assert history.total == 1  # the failed create left nothing behind
    finally:
        await engine.dispose()


async def test_terms_creation_is_throttled_per_tenant(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=3600, clock=time.monotonic)
    service = _service(factory, limiter=limiter)
    tenant = uuid.uuid4()
    other_tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        await _create_terms(service, tenant, terms_text="v2")
        with pytest.raises(TermsThrottledError):
            await _create_terms(service, tenant, terms_text="v3")
        assert (await service.get_terms_history(tenant)).total == 2
        # The throttle is per-tenant, not global.
        await _create_terms(service, other_tenant, terms_text="other v1")
    finally:
        await engine.dispose()


async def test_terms_update_and_delete_denied_at_the_db(app_role_url: str) -> None:
    """Immutability is structural: app_user holds SELECT + INSERT only, so even
    raw SQL from the app role cannot rewrite accepted policy evidence."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="immutable")

        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_session(factory, tenant) as session:
                await session.execute(text("UPDATE terms_versions SET terms_text = 'tampered'"))

        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_session(factory, tenant) as session:
                await session.execute(text("DELETE FROM terms_versions"))

        history = await service.get_terms_history(tenant)
        assert history.current is not None and history.current.terms_text == "immutable"
    finally:
        await engine.dispose()


# --- CHECK constraints: the DB rejects out-of-bounds financial fields even when
# --- service validation is bypassed ---


async def test_check_constraints_reject_bad_values_below_the_service(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    terms_repo = TermsVersionsRepository()
    types_repo = AppointmentTypesRepository()
    tenant = uuid.uuid4()
    try:
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await terms_repo.insert(
                    session,
                    tenant_id=tenant,
                    version=1,
                    terms_text="bad forfeit",
                    refundable_until_hours_before=48,
                    forfeit_percent=150,
                    created_by=STAFF_ID,
                )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await terms_repo.insert(
                    session,
                    tenant_id=tenant,
                    version=1,
                    terms_text="negative hours",
                    refundable_until_hours_before=-1,
                    forfeit_percent=100,
                    created_by=STAFF_ID,
                )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await types_repo.insert(
                    session,
                    tenant_id=tenant,
                    name="zero duration",
                    duration_minutes=0,
                    audience=AppointmentAudience.ALL,
                    deposit_required=False,
                    deposit_amount_agorot=None,
                    sort_order=0,
                )
    finally:
        await engine.dispose()


# --- cross-tenant invisibility for every new resource ---


async def test_cross_tenant_invisibility_for_all_new_resources(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        appointment = await service.create_appointment_type(
            tenant_a, name="Fitting", duration_minutes=60
        )
        await service.replace_weekly_rules(tenant_a, [_rule(0, 9, 12)])
        exception = await service.add_availability_exception(
            tenant_a, date=datetime.date(2026, 9, 23), open_time=None, close_time=None
        )
        await _create_terms(service, tenant_a)

        # B reads nothing of A's.
        assert await service.list_appointment_types(tenant_b) == []
        availability_b = await service.get_availability(tenant_b)
        assert availability_b.rules == [] and availability_b.exceptions == []
        history_b = await service.get_terms_history(tenant_b)
        assert history_b.current is None and history_b.total == 0

        # B cannot write A's rows.
        with pytest.raises(NotFoundError):
            await service.update_appointment_type(
                tenant_b,
                appointment.id,
                name="Hijack",
                duration_minutes=5,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        with pytest.raises(NotFoundError):
            await service.archive_appointment_type(tenant_b, appointment.id)
        with pytest.raises(NotFoundError):
            await service.remove_availability_exception(tenant_b, exception.id)
        # B replacing its own rules must not touch A's weekly grid.
        await service.replace_weekly_rules(tenant_b, [_rule(5, 8, 10)])

        # A's data is intact.
        assert [item.id for item in await service.list_appointment_types(tenant_a)] == [
            appointment.id
        ]
        availability_a = await service.get_availability(tenant_a)
        assert [rule.day_of_week for rule in availability_a.rules] == [0]
        assert [item.id for item in availability_a.exceptions] == [exception.id]
        assert (await service.get_terms_history(tenant_a)).total == 1
    finally:
        await engine.dispose()
