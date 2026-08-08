"""staff notifications: one row per (recipient, event), one partial index

Revision ID: 0030
Revises: 0027

⚠ **The NUMBER and the PARENT are answering two different questions, and the gap
between them is deliberate.** F25 reserved 0028 and F28 reserved 0029 in live
worktrees that have not merged yet, so 0030 is the next FREE string — alembic
keys revisions by the string, and a duplicate does not error, it warns and DROPS
one of the two scripts, meaning one feature's DDL never runs on a fresh database.
`down_revision` meanwhile must name a revision that EXISTS in this tree, which is
0027, or `alembic heads` reports a broken chain and every db test reds on a
missing parent rather than on anything this feature did.

Both are re-resolved against `alembic heads` at the pre-push rebase — filename,
`revision`, `down_revision` — and `test_exactly_one_migration_head` is the proof.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0030"
down_revision = "0028"
branch_labels = None
depends_on = None

_STANDARD = """
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
"""


def _updated_at_trigger(table: str) -> str:
    return f"""
        CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """


def upgrade() -> None:
    # ⚠ **NO CUSTOMER DATUM, EVER — no name, no phone, no ticket id.** The bell
    # says WHO DID WHAT TO YOU; the floor screen, under its own audience rules,
    # says who the customer is. That split is the whole reason this table sits
    # outside F20's retention registry: two staff uuids, an event uuid and two
    # timestamps name no data subject.
    #
    # `staff_user_id` is the RECIPIENT and `actor_staff_user_id` is who did it to
    # her. They are never equal — every producer guards on it — because a
    # notification telling a manager what she just did herself is noise on the
    # one surface whose whole value is that its count means something.
    #
    # `entity_id` is UNTYPED and `kind` names the table it points into
    # (`fitting_room_assignments` for the first two kinds, `sos_alerts` for the
    # third). No FK: this schema has none. It is stored because it is what makes
    # the row a RECORD rather than a log line, and it is deliberately NOT emitted
    # on the wire, because nothing renders it. Upgrade path when a deep link
    # exists: one response field, no migration.
    #
    # `kind` is TEXT with a CHECK, three values, pinned by the DB — the house
    # rule for every bounded set (`bookings.status`, `message_log.kind`,
    # `sos_alerts.status`). A fourth kind is a migration and therefore a review.
    #
    # `deleted_at` has NO v1 WRITER and that is not an omission: read is a
    # status, not a deletion, and there is no per-row dismiss. It is in the
    # index predicate for the same reason it is on every table in this schema.
    op.execute(
        f"""
        CREATE TABLE staff_notifications (
            {_STANDARD},
            staff_user_id UUID NOT NULL,
            actor_staff_user_id UUID NOT NULL,
            kind TEXT NOT NULL,
            entity_id UUID NOT NULL,
            read_at TIMESTAMPTZ,
            CONSTRAINT staff_notifications_kind_check
                CHECK (kind IN ('dispatch_assigned', 'room_handed_over', 'sos_targeted'))
        )
        """
    )
    # ONE INDEX, AND IT MATCHES THE UNREAD COUNT'S PREDICATE EXACTLY. That count
    # rides the SOS poll's payload — the console's only app-wide tick, running on
    # all 18 sections every 5 seconds for every signed-in device — so it is the
    # one statement here whose access path is a product decision rather than a
    # detail. `StaffNotificationsRepository.unread_count` spells the same
    # predicate character for character and `test_migrations.py` pins the
    # deparsed form.
    #
    # NO SECOND INDEX for the list read, deliberately: it is `WHERE tenant_id = ?
    # AND staff_user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT
    # 20` on a table holding tens of rows per tenant per day. Upgrade path with
    # its stated cost: `(tenant_id, staff_user_id, created_at DESC) WHERE
    # deleted_at IS NULL`, taking an ACCESS EXCLUSIVE lock on a table that will
    # still be small.
    op.execute(
        "CREATE INDEX idx_staff_notifications_unread ON staff_notifications "
        "(tenant_id, staff_user_id) WHERE read_at IS NULL AND deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("staff_notifications"))

    # Forgetting enable_tenant_rls fails a DIFFERENT file's test
    # (test_tenant_isolation.py's tenant_id scan). The GRANT is redundant —
    # 0002's ALTER DEFAULT PRIVILEGES already covers every table a later
    # migration creates as this role — and kept as the house belt-and-braces.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON staff_notifications TO app_user")
    for statement in enable_tenant_rls("staff_notifications"):
        op.execute(statement)


def downgrade() -> None:
    # DROP TABLE takes the index, the trigger and the policy with it. F35 touches
    # no existing table, so there is nothing to un-touch and this cannot fail on
    # live data.
    op.execute("DROP TABLE IF EXISTS staff_notifications")
