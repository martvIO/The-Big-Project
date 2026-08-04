"""floor dispatch: the assignment's pointer at the walk-in it serves

Revision ID: 0021
Revises: 0020

⚠ AND IT HAPPENED A THIRD TIME. This file was built as "0020" — honestly, from
`alembic heads` at build time — and F41 merged forty-one minutes later with its
own `0020_alteration_tickets.py`, whose header records the same thing happening
to it at "0019". Two files declaring revision "0020", different filenames, a
textually clean merge and nothing in review looking wrong: alembic keys
revisions by the STRING, so it does not error — it warns `Revision 0020 is
present more than once`, dedupes to ONE script and DROPS the other, which on a
fresh database means one of the two features' DDL simply never runs. Renumbered
here at the merge that brought F41 in, which is the only moment both files are
visible: three edits to this one file (the filename, `revision`,
`down_revision`), and `test_exactly_one_migration_head` is what proves it.
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0019 wrote this handover in its own DDL and this is the other half of it:
    # "queue_ticket_id is deliberately ABSENT. The walk-in's dispatch record is
    # F33's queue_tickets and the dispatch action is F58's; F58 adds the column
    # in its own migration alongside its writer, rather than this one pre-adding
    # a speculative pointer nothing can fill."
    #
    # The other half of `booking_id`, and the two are mutually exclusive in
    # practice without being constrained to be: a fitting serves either a bride
    # who booked (booking_id) or a walk-in off the queue (queue_ticket_id) or
    # nobody at all (a staffer prepping a room — both null, the ordinary case
    # and the one F36 already exercises).
    #
    # DELIBERATELY ABSENT, each with its reason and its verifying test — the
    # 0014_booking_check_in.py idiom, where the comment and not the DDL line is
    # the deliverable:
    #
    #   No NOT NULL: every assignment F36 created has this column null, so a
    #     NOT NULL could not be added at all without a backfill with nothing to
    #     backfill from, and the anonymous claim stays a first-class path.
    #     Pinned by test_the_floor_dispatch_migration_adds_one_nullable_column.
    #   No FK, no CASCADE: house rule; the join predicate is spelled out in
    #     FittingRoomsRepository._occupancy_rows and every read is RLS-scoped.
    #   No CHECK of any kind — not `num_nonnulls(booking_id, queue_ticket_id) <= 1`
    #     either. test_the_fitting_room_tables_carry_no_check_constraints
    #     asserts this table has zero, and the exclusivity such a CHECK would
    #     express is not actually an invariant: a bride who booked ahead and
    #     ALSO scanned the QR is a real person, and refusing to record both
    #     facts about her would be the schema being clever at the expense of the
    #     room she is standing in.
    #   No UNIQUE INDEX — not `(tenant_id, queue_ticket_id) WHERE released_at IS
    #     NULL AND deleted_at IS NULL`, which reads like the missing third
    #     guarantee and is not one. Two dispatches of the same ticket are
    #     already impossible: both dispatch verbs claim the ticket with a
    #     conditional `UPDATE ... WHERE status = 'waiting'` FIRST, so the second
    #     transaction blocks on that row's lock, re-evaluates the predicate
    #     against the updated row and matches nothing. That conditional UPDATE
    #     is the serialisation point, not this table. Adding one would also RED
    #     test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes
    #     — a shipped guard whose whole purpose is to make a third index a
    #     visible, reviewed act. This is that review, and the answer is no.
    #   No non-unique index either: nothing reads this column as a predicate.
    #     The payload joins queue_tickets on ITS primary key and the finish path
    #     goes assignment -> ticket, so an index here would serve no reader and
    #     cost every claim.
    #   No GRANT and no enable_tenant_rls: the table already has both, and RLS
    #     is per-table, not per-column.
    op.execute("ALTER TABLE fitting_room_assignments ADD COLUMN queue_ticket_id UUID")


def downgrade() -> None:
    # ⚠ UNLIKE F36's, THIS DOWNGRADE CAN LOSE LIVE DATA — it drops the only
    # record of which walk-in each fitting served. F57's role-widening migration
    # carries the same warning for the same reason. Stated here rather than
    # discovered on a staging rollback.
    op.execute("ALTER TABLE fitting_room_assignments DROP COLUMN IF EXISTS queue_ticket_id")
