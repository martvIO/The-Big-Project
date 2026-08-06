"""The retention REGISTRY's shape, with no database in sight.

What belongs here is everything about the registry that is true before a single
row exists: which tables a policy is allowed to name, the order the tuple is
declared in, and that every policy can name itself in the audit trail.

What does NOT belong here is clock arithmetic. The plan filed it under this file,
and it cannot live here honestly: a policy's clock is a SQL predicate, so a fast
test could only recompute the same `now - timedelta(...)` in Python and assert
Python against Python — a test that would stay green with the predicate deleted.
Every boundary, in both directions, is asserted against real Postgres in
`test_retention_db.py`, which is also the only place the app role's GRANTs — the
thing the exemption list below is REALLY about — can bite.
"""

import datetime
import uuid
from typing import Any

from app.core.config import Settings
from app.models.constants import AuditAction
from app.privacy.retention import (
    CHUNK_SIZE,
    MAX_CHUNKS,
    POLICIES,
    RetentionAction,
    RetentionPolicy,
    RetentionRunner,
    audit_action,
)

# The five tables `app_user` must never be handed to a policy. FOUR of them have
# had DELETE revoked by migration and would fail at the grant — `terms_versions`
# (0005:126), `platform_audit_log` (0004:39), and `payments` +
# `tenant_gateway_credentials` (0012:147, "a hard DELETE of a payment row
# destroys financial evidence; of a credential row, the rotation trail").
#
# `audit_log` is the fifth and it is exempt for a different reason: it still
# holds a DELETE grant, so nothing in the database would stop a policy naming it
# — and it is the evidence that retention RAN. Giving it a retention class would
# eventually erase the proof of the erasures.
FORBIDDEN_TABLES = frozenset(
    {
        "terms_versions",
        "platform_audit_log",
        "audit_log",
        "payments",
        "tenant_gateway_credentials",
    }
)


def test_the_registry_names_no_table_the_app_role_cannot_delete_from() -> None:
    """Walks `policy.tables`, NOT `policy.name`.

    That distinction is the whole reason `tables` exists as a field. A name is a
    label an author picks; `tables` is a declaration of what the SQL touches, and
    the runner writes it into the audit row — so a policy whose declared table
    diverges from the one its statement hits is a wrong audit row rather than a
    silent mismatch. Asserting on names would make this a spelling check.
    """
    for policy in POLICIES:
        assert not FORBIDDEN_TABLES & set(policy.tables), (
            f"policy {policy.name!r} names an exempt table: "
            f"{sorted(FORBIDDEN_TABLES & set(policy.tables))}"
        )


def test_the_exemption_walk_is_not_walking_an_empty_registry() -> None:
    """The anti-vacuity leg. `not FORBIDDEN & set(...)` above is trivially true
    for an empty tuple, an empty `tables`, and a registry someone renamed the
    field out of — all three of which would leave the assertion above green while
    proving nothing at all."""
    named = {table for policy in POLICIES for table in policy.tables}
    assert "customers" in named
    assert len(named) >= len(POLICIES)


def test_the_registry_order_puts_bookings_before_customers() -> None:
    """Asserted on the TUPLE, never left to a comment. The customer scrub's feed
    is "no live booking points at me", which only becomes true after the booking
    purge has run — so a reordered registry silently stops the scrub finding
    anything for one whole tick per booking."""
    order = [policy.name for policy in POLICIES]
    assert order.index("bookings") < order.index("customers")


def test_every_policy_can_name_itself_in_the_audit_trail() -> None:
    """`audit_action` resolves through the enum, so a policy added without its
    `AuditAction` member is a ValueError HERE rather than at 03:00 inside a
    tenant loop, three tables into an irreversible run."""
    for policy in POLICIES:
        assert audit_action(policy) in set(AuditAction)


def test_the_registry_covers_the_seven_classes_with_the_specified_actions() -> None:
    assert {policy.name: policy.action for policy in POLICIES} == {
        "otp_codes": RetentionAction.PURGE,
        "sessions": RetentionAction.PURGE,
        # DR-11: F33's shipped public notice already promises the walk-in her
        # details go. SCRUB and not PURGE because
        # `fitting_room_assignments.queue_ticket_id` is a nullable no-FK pointer,
        # and a purge leaves danglers with no way to tell "aged out" from "never
        # existed".
        "queue_tickets": RetentionAction.SCRUB,
        # F22 (spec D4): the row IS the personal data — a phone bound to a day
        # and a type — and nothing points at it, so PURGE, `queue_tickets`'
        # class without its dangler argument.
        "waitlist_entries": RetentionAction.PURGE,
        "message_log": RetentionAction.PURGE,
        "bookings": RetentionAction.PURGE,
        "customers": RetentionAction.SCRUB,
    }


def test_the_batch_constants_are_the_house_shape() -> None:
    """Verbatim from `app/booking/backfill.py:36-38` — one page per transaction
    and a hard ceiling, so a runaway cannot loop forever."""
    assert (CHUNK_SIZE, MAX_CHUNKS) == (500, 50)


# --- the runner's loop, driven with fakes -----------------------------------
#
# The chunk loop, the MAX_CHUNKS ceiling, the per-tenant containment and the
# dry-run's no-write promise are all properties of the RUNNER and none of them
# needs a row to exist. What the fakes cannot see — that the SQL is right, that
# RLS contains it, that an audit row lands — is asserted in `test_retention_db.py`
# against real Postgres.


class _FakeTenant:
    def __init__(self, label: str) -> None:
        self.id = uuid.uuid4()
        self.label = label


class _FakeTenants:
    def __init__(self, tenants: list[_FakeTenant]) -> None:
        self._tenants = tenants
        self.list_all_calls = 0

    async def list_all(self) -> list[_FakeTenant]:
        self.list_all_calls += 1
        return self._tenants


class _FakeSession:
    """Enough of AsyncSession for `tenant_session` to bind a context and for
    `AuditLogRepository.record` to add a row."""

    def __init__(self, recorder: list[Any]) -> None:
        self._recorder = recorder

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def begin(self) -> "_FakeSession":
        return self

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None

    def add(self, row: Any) -> None:
        self._recorder.append(row)

    async def flush(self) -> None:
        return None


class _FakeFactory:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.sessions = 0

    def __call__(self) -> _FakeSession:
        self.sessions += 1
        return _FakeSession(self.added)


def _policy(
    name: str, pages: list[int | Exception]
) -> tuple[RetentionPolicy, list[dict[str, Any]]]:
    """A policy that returns each page count in turn, recording how it was called.
    A raising page is spelled by an Exception instance in `pages`."""
    calls: list[dict[str, Any]] = []
    remaining = list(pages)

    async def run(
        session: Any,
        tenant_id: uuid.UUID,
        *,
        now: datetime.datetime,
        settings: Settings,
        limit: int,
        dry_run: bool,
    ) -> int:
        calls.append({"tenant_id": tenant_id, "limit": limit, "dry_run": dry_run, "now": now})
        page = remaining.pop(0) if remaining else 0
        if isinstance(page, Exception):
            raise page
        return page

    return RetentionPolicy(name, RetentionAction.PURGE, (name,), run), calls


def _runner(factory: _FakeFactory, tenants: _FakeTenants, policies: Any) -> RetentionRunner:
    return RetentionRunner(
        factory,  # type: ignore[arg-type]
        settings=Settings(app_env="dev"),
        tenants=tenants,  # type: ignore[arg-type]
        policies=policies,
    )


async def test_the_chunk_loop_stops_on_the_first_short_page() -> None:
    """One page per transaction, and a short page means the feed is drained —
    the backfill.py shape. A loop that kept going would re-run the same empty
    statement 49 more times per policy per tenant per tick."""
    factory, tenants = _FakeFactory(), _FakeTenants([_FakeTenant("bella")])
    policy, calls = _policy("otp_codes", [CHUNK_SIZE, CHUNK_SIZE, 7])

    result = await _runner(factory, tenants, (policy,)).run()

    assert len(calls) == 3
    assert result.rows == {"otp_codes": CHUNK_SIZE * 2 + 7}


async def test_the_chunk_loop_is_bounded_by_max_chunks() -> None:
    """A feed that never shortens must not loop forever. The ceiling is what
    turns "this tenant has a huge backlog" into "this tenant finishes over
    several ticks" rather than into a wedged worker process."""
    factory, tenants = _FakeFactory(), _FakeTenants([_FakeTenant("bella")])
    policy, calls = _policy("otp_codes", [CHUNK_SIZE] * (MAX_CHUNKS + 10))

    result = await _runner(factory, tenants, (policy,)).run()

    assert len(calls) == MAX_CHUNKS
    assert result.rows == {"otp_codes": CHUNK_SIZE * MAX_CHUNKS}


async def test_a_dry_run_calls_each_policy_once_and_writes_no_audit_row() -> None:
    """Not looped, deliberately: a dry run consumes no rows, so a chunk loop over
    a counting statement would report the same page MAX_CHUNKS times. And no
    audit row — a rehearsal that leaves evidence of a run that did not happen is
    a lie about the trail an auditor reads."""
    factory, tenants = _FakeFactory(), _FakeTenants([_FakeTenant("bella")])
    policy, calls = _policy("otp_codes", [CHUNK_SIZE, CHUNK_SIZE])

    result = await _runner(factory, tenants, (policy,)).run(dry_run=True)

    assert [call["dry_run"] for call in calls] == [True]
    assert result.rows == {"otp_codes": CHUNK_SIZE}
    assert factory.added == []


async def test_an_armed_run_writes_one_audit_row_per_tenant_per_policy() -> None:
    factory = _FakeFactory()
    tenants = _FakeTenants([_FakeTenant("bella"), _FakeTenant("vered")])
    first, _ = _policy("otp_codes", [3, 3])
    second, _ = _policy("sessions", [1, 1])

    await _runner(factory, tenants, (first, second)).run()

    assert [(row.action, row.entity) for row in factory.added] == [
        ("retention_otp_codes", "otp_codes"),
        ("retention_sessions", "sessions"),
        ("retention_otp_codes", "otp_codes"),
        ("retention_sessions", "sessions"),
    ]
    assert factory.added[0].details["rows"] == 3


async def test_a_policy_that_touched_nothing_writes_no_audit_row() -> None:
    """Six rows per tenant per hour of "deleted 0" is permanent bloat in the one
    table that deliberately has no retention class of its own."""
    factory, tenants = _FakeFactory(), _FakeTenants([_FakeTenant("bella")])
    busy, _ = _policy("otp_codes", [2])
    idle, _ = _policy("sessions", [0])

    result = await _runner(factory, tenants, (busy, idle)).run()

    assert [row.action for row in factory.added] == ["retention_otp_codes"]
    assert result.rows == {"otp_codes": 2}


async def test_one_tenants_failure_is_logged_and_skipped_never_stopping_the_others() -> None:
    """Higher stakes than the poller's version of this rule: a single bad row
    must not stall retention for every OTHER boutique, because the clock those
    boutiques are on is a legal duty and nothing else will notice it stopped."""
    broken, healthy = _FakeTenant("broken"), _FakeTenant("healthy")
    factory, tenants = _FakeFactory(), _FakeTenants([broken, healthy])
    policy, calls = _policy("otp_codes", [RuntimeError("bad row"), 4])

    result = await _runner(factory, tenants, (policy,)).run()

    assert [call["tenant_id"] for call in calls] == [broken.id, healthy.id]
    assert result.failed_tenants == 1
    assert result.tenants == 2
    assert result.rows == {"otp_codes": 4}
    # The healthy tenant's evidence still lands — the failure did not roll it back.
    assert [row.tenant_id for row in factory.added] == [healthy.id]


async def test_the_runner_enumerates_every_tenant_not_only_the_active_ones() -> None:
    """D21, asserted at the seam rather than only in the repository: the runner
    must ask for `list_all()`. A `list_active()` here would freeze a suspended or
    off-boarded boutique's data with no clock, forever — and nothing else in the
    system would ever notice."""
    factory, tenants = _FakeFactory(), _FakeTenants([_FakeTenant("bella")])
    policy, _ = _policy("otp_codes", [1])

    await _runner(factory, tenants, (policy,)).run()

    assert tenants.list_all_calls == 1
