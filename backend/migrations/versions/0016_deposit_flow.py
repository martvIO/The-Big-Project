"""deposit booking flow: the pending_payment hold, its expiry, and the late-payment SMS

Revision ID: 0016
Revises: 0015

**RENUMBERED AT REBASE, and the guard below is why that was a two-line change.**
Built as 0015/down_revision 0014 so this branch stayed self-coherent and its
db-marked tests could run `alembic upgrade head` at all while F57 and F33 were
still in flight in their own worktrees. F57 merged first and took 0015, so this
became 0016/down_revision 0015.

Two files claiming one revision id is an alembic multiple-heads error that GIT
CANNOT SEE — the filenames differ and the merge is textually clean. On the rebase
that created this collision, `test_exactly_one_migration_head` failed in
`make test` in under a second and named both heads. Without it the first symptom
would have been every db-marked test erroring at CI fixture setup, on a branch
that was green an hour earlier, with a diff touching no migration.
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

# Postgres auto-names an inline column CHECK `<table>_<column>_check`. All three
# constraints widened here were written inline (0007:41, 0008:66-67, 0010:43-44),
# so these are the names it generated — the same fact 0013 relies on for
# tenant_gateway_credentials_provider_check.
_STATUS = "bookings_status_check"
_CANCELLED_BY = "bookings_cancelled_by_check"
_MESSAGE_KIND = "message_log_kind_check"

_STATUSES_BEFORE = ("confirmed", "cancelled", "no_show", "completed")
_STATUSES_AFTER = (*_STATUSES_BEFORE, "pending_payment")

_CANCELLED_BY_BEFORE = ("customer", "owner")
_CANCELLED_BY_AFTER = (*_CANCELLED_BY_BEFORE, "expired")

_MESSAGE_KINDS_BEFORE = ("otp", "confirmation", "reminder", "owner_cancel", "owner_reschedule")
_MESSAGE_KINDS_AFTER = (*_MESSAGE_KINDS_BEFORE, "payment_received_no_slot")


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def _swap_check(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    """0013's drop-then-add, which is the house pattern for widening a bounded set.

    No IF EXISTS on the DROP, deliberately and for 0013's stated reason: if the
    constraint is not there under this exact name, the assumption this migration
    is built on is false and it must fail loudly rather than silently leave the
    column unconstrained.
    """
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK ({column} IN ({_values(values)}))"
    )


def upgrade() -> None:
    # 1. The fifth booking status. `pending_payment` is a HELD seat: both partial
    #    unique indexes and every occupancy read exclude `cancelled` and nothing
    #    else (0008:88-92, 0009:32-36, and both migrations say so ahead of time),
    #    so a held seat is an occupied seat with NO index change and NO
    #    occupancy-query change. That is the whole reason this is a status rather
    #    than a booking_holds table or a deposit_pending boolean.
    _swap_check("bookings", _STATUS, "status", _STATUSES_AFTER)

    # 2. Who cancelled it, when the answer is "nobody — the hold ran out" (MD5).
    #    A third actor rather than reusing 'customer': she did not cancel, and
    #    MD5 turns on telling those apart — an abandoned checkout must not count
    #    against the boutique's headline cancellation rate.
    _swap_check("bookings", _CANCELLED_BY, "cancelled_by", _CANCELLED_BY_AFTER)

    # 3. The hosted-page URL, stored beside the session id (D8). F17 returns
    #    `redirect_url=None` on the converge path deliberately, with a comment
    #    saying it exists "to force F19 to decide what a retry does". This is that
    #    decision: the URL is stored, so a double-tap and the 0009 replay branch
    #    both converge onto the SAME hold and get back a WORKING link instead of
    #    None — which is what the storefront's declined-state retry copy rests on.
    #    Blanked in the same .values() as every transition out of 'pending'
    #    (settle, settle_late, and the sweeper's claim 1), so F20 inherits no new
    #    blanking obligation.
    op.execute("ALTER TABLE payments ADD COLUMN redirect_url TEXT")

    # 4. MD2's SMS: her money arrived after her seat was given away. Unconditional
    #    — the spec's question form made this statement conditional on a user
    #    ruling, and MD2 IS that ruling.
    _swap_check("message_log", _MESSAGE_KIND, "kind", _MESSAGE_KINDS_AFTER)

    # 5. D6 claim 2's orphan sweep rides this. The claim reads pending_payment
    #    bookings older than hold + poll_interval that have NO pending payment
    #    row — the rows left behind when the process dies between create_booking's
    #    COMMIT and open_deposit's, which claim 1 can never see because it sweeps
    #    `payments` and there is no payments row at all.
    #
    #    Partial on a status that holds a handful of live rows at any instant, so
    #    it costs almost nothing to maintain and turns a per-tick sequential scan
    #    of the whole bookings table into an index scan. tenant_id first because
    #    the sweep is per-tenant (RLS forces that shape); created_at second
    #    because the claim's other predicate is an age bound.
    op.execute(
        "CREATE INDEX idx_bookings_pending_payment ON bookings (tenant_id, created_at) "
        "WHERE deleted_at IS NULL AND status = 'pending_payment'"
    )

    # Deliberately absent, each for a verified reason, stated so a reviewer can
    # check the list is COMPLETE rather than merely short (the 0014 discipline):
    #
    #   * No GRANT. 0008 and 0012 issued table-level grants and table grants are
    #     column-agnostic; the ALTER DEFAULT PRIVILEGES gotcha is about newly
    #     CREATED tables, not added columns or added constraints.
    #   * No enable_tenant_rls. RLS is a table property, already forced on
    #     bookings (0008), payments (0012) and message_log (0007).
    #     test_every_tenant_id_table_has_forced_rls stays green unedited.
    #   * No _updated_at_trigger. All three tables already have theirs.
    #   * No change to idx_bookings_slot_seat_unique or
    #     idx_bookings_tenant_customer_starts_unique. Their `status <> 'cancelled'`
    #     predicate is ALREADY correct for a held seat, which is the point of D1.
    #   * No change to idx_payments_hold_expiry. 0012 built it for this feature's
    #     sweeper and labelled it so.
    #   * No backfill. There is no pre-existing pending_payment row to migrate,
    #     because nothing has ever written one.
    #
    # ponytail: ADD CONSTRAINT validates the whole table under ACCESS EXCLUSIVE.
    # At pilot scale (thousands of rows) that is milliseconds; the NOT VALID +
    # VALIDATE CONCURRENTLY dance is the upgrade path if bookings ever gets large.


def downgrade() -> None:
    """Narrowing a CHECK is refused by Postgres while ANY row holds the value
    being removed — `ADD CONSTRAINT` validates the whole table. So a downgrade
    that only swaps constraints back is not a downgrade at all: it works exactly
    until the feature has been used once, which is precisely when a rollback is
    wanted. The data has to move first, and each mapping below is chosen to be
    TRUE in the old schema rather than merely legal.

    Found by running the db suite locally: two leaked `cancelled_by = 'expired'`
    rows turned SEVEN unrelated round-trip tests red with a check-violation
    pointing at no test in particular.
    """
    op.execute("DROP INDEX IF EXISTS idx_bookings_pending_payment")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS redirect_url")

    # `cancelled_by` is NULLABLE, and NULL is the honest answer once 'expired'
    # stops existing: we no longer have a value that says who cancelled it, and
    # mapping it to 'customer' would assert something false about a bride who
    # never touched the booking — the exact misattribution MD5 exists to prevent.
    op.execute("UPDATE bookings SET cancelled_by = NULL WHERE cancelled_by = 'expired'")
    _swap_check("bookings", _CANCELLED_BY, "cancelled_by", _CANCELLED_BY_BEFORE)

    # A held seat cannot be represented at all in the old schema, and leaving
    # these rows 'confirmed' would silently promote unpaid holds into real
    # appointments — the worst available outcome. 'cancelled' frees the seat,
    # which is what an un-completable hold means. COALESCE so a row that somehow
    # already carries a cancel timestamp keeps its own.
    op.execute(
        "UPDATE bookings SET status = 'cancelled', "
        "cancelled_at = COALESCE(cancelled_at, now()) "
        "WHERE status = 'pending_payment'"
    )
    _swap_check("bookings", _STATUS, "status", _STATUSES_BEFORE)

    # message_log.kind is DELIBERATELY LEFT WIDE, and this is the one place this
    # downgrade is not a true inverse.
    #
    # message_log is an append-only record of messages actually sent. Narrowing
    # its CHECK would require deleting every 'payment_received_no_slot' row —
    # destroying evidence that a real SMS reached a real customer, to satisfy
    # schema symmetry. A CHECK left one value wider permits a value nothing
    # writes and costs nothing; deleted delivery evidence cannot be recovered.
    #
    # Re-running upgrade() after this downgrade is safe: _swap_check drops before
    # it adds, so the wider constraint is simply replaced by itself.
