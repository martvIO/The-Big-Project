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

from app.models.constants import AuditAction
from app.privacy.retention import (
    CHUNK_SIZE,
    MAX_CHUNKS,
    POLICIES,
    RetentionAction,
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


def test_the_registry_covers_the_six_classes_with_the_specified_actions() -> None:
    assert {policy.name: policy.action for policy in POLICIES} == {
        "otp_codes": RetentionAction.PURGE,
        "sessions": RetentionAction.PURGE,
        # DR-11: F33's shipped public notice already promises the walk-in her
        # details go. SCRUB and not PURGE because
        # `fitting_room_assignments.queue_ticket_id` is a nullable no-FK pointer,
        # and a purge leaves danglers with no way to tell "aged out" from "never
        # existed".
        "queue_tickets": RetentionAction.SCRUB,
        "message_log": RetentionAction.PURGE,
        "bookings": RetentionAction.PURGE,
        "customers": RetentionAction.SCRUB,
    }


def test_the_batch_constants_are_the_house_shape() -> None:
    """Verbatim from `app/booking/backfill.py:36-38` — one page per transaction
    and a hard ceiling, so a runaway cannot loop forever."""
    assert (CHUNK_SIZE, MAX_CHUNKS) == (500, 50)
