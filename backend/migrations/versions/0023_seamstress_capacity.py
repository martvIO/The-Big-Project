"""seamstress capacity: one nullable column, its CHECK, and the assignee index

Revision ID: 0023
Revises: 0022

The number was resolved from `alembic heads` at build time and is not reserved.
0020's header and 0021's record what reserving one costs — it has now happened
three times in this file series: two files declaring one revision id, different
filenames, a textually clean merge and nothing in review looking wrong. Alembic
keys revisions by the STRING, so it does not error; it warns `Revision N is
present more than once`, dedupes to ONE script and drops the other, which on a
fresh database means one of the two features' DDL simply never runs.

⚠ AND IT HAPPENED AGAIN, WHICH IS WHY THE RULE IS A RULE. This file was built
at 0022 against a `main` whose head was 0021. F37 landed first (PR #41) as
`0022_sos_alerts.py`, so `alembic heads` on the rebased branch printed
`0022 (head)` TWICE with `UserWarning: Revision 0022 is present more than once`
— the exact failure this header describes, observed rather than predicted. The
renumber to 0023 is three edits to one file: the filename, `revision`,
`down_revision`. `test_exactly_one_migration_head` is what proves it, and only
AFTER the rebase.
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULLABLE, NO DEFAULT, and both halves are the decision.
    #
    # NULL is a REAL AND MEANINGFUL STATE: "no capacity recorded for this
    # person". The panel has a designed rendering for it («לא הוגדרה קיבולת»,
    # no bar) because a bar without a denominator is a picture of a number that
    # does not exist. A `DEFAULT 40` would write a number nobody chose onto
    # every existing row and make that state unreachable AND undetectable.
    #
    # Nullable-with-no-default is also the one `ALTER TABLE … ADD COLUMN` form
    # Postgres does as METADATA ONLY — no table rewrite, an ACCESS EXCLUSIVE
    # lock held for microseconds on a single-digit-row table.
    #
    # HOURS, not minutes, even though `effort_minutes` next door is minutes and
    # storing minutes here would make the two comparable with no multiplication.
    # The human types HOURS — «12 שעות» is what a shift manager says — and
    # storing 720 to render 12 puts a conversion between the input and the
    # column for no gain. The single hours→minutes multiplication in the whole
    # feature lives on the client, in `lib/capacity.ts`, and is unit-tested; the
    # SERVER never multiplies the two, which is why the load aggregate returns
    # minutes under their own name and this column reaches the wire as hours
    # under its own.
    op.execute("ALTER TABLE staff_users ADD COLUMN weekly_capacity_hours INTEGER")

    # 0 IS LEGAL AND IS NOT A TYPO: a shift manager setting 0 is saying "she is
    # not available this week", which is a thing the product should be able to
    # say and which the panel renders honestly — a full red bar and «עומס יתר»
    # against any load at all, not the «לא הוגדרה קיבולת» that NULL draws. The
    # resolution function therefore branches on `is not None` and never on
    # truthiness, and that distinction is the one this bound exists to keep
    # expressible.
    #
    # 168 is hours-in-a-week: a TYPO FENCE in `effort_minutes CHECK (… <= 1440)`'s
    # spirit (0020), not a policy about labour law. A capacity is a DENOMINATOR,
    # and an unbounded one renders every bar in the boutique at a fraction of the
    # truth in the colour that says everything is fine.
    #
    # A NAMED TABLE constraint rather than an inline column check, so
    # `pg_get_constraintdef` has a name to pin: whoever re-tunes this ceiling
    # collides with test_the_capacity_definitions_are_pinned and a deliberate
    # review, instead of colliding with nothing.
    op.execute(
        "ALTER TABLE staff_users ADD CONSTRAINT staff_users_weekly_capacity_hours_check "
        "CHECK (weekly_capacity_hours >= 0 AND weekly_capacity_hours <= 168)"
    )

    # 0020 RESERVED THIS DECISION FOR HERE, BY NAME, and this is it being made:
    # "Declined: an index on assigned_staff_user_id. F42's load query
    # (SUM(effort_minutes) … GROUP BY assigned_staff_user_id) is its only
    # reader, and F42 has a migration of its own — the feature that measures the
    # query buys the index."
    #
    # It is not decoration. The load aggregate is DELIBERATELY UNCAPPED — unlike
    # the board read, which stops at BOARD_TICKET_LIMIT — because a Python fold
    # over a truncated board would silently under-count every bar, and the
    # boutique whose board truncates is by definition the overloaded one. So the
    # aggregate scans on every five-second tick, and the partial predicate is
    # the only thing bounding what it scans: it is byte-for-byte the aggregate's
    # own WHERE clause minus the tenant, so on a boutique that has been
    # delivering for two years the index holds only the work still in the room.
    #
    # ⚠ DROPPING THE `delivered_at IS NULL` HALF is the edit this index's pinned
    # definition exists to catch. It would still serve the query and would still
    # look right.
    #
    # Not unique, and nothing here is: one seamstress holds many tickets, which
    # is the entire point of summing them.
    op.execute(
        "CREATE INDEX idx_alteration_tickets_tenant_assignee "
        "ON alteration_tickets (tenant_id, assigned_staff_user_id) "
        "WHERE deleted_at IS NULL AND delivered_at IS NULL"
    )

    # No enable_tenant_rls, no GRANT, no trigger. `staff_users` has forced RLS
    # from 0003 and `alteration_tickets` from 0020; adding a column to a table
    # under a policy does not change the policy, and GRANTs are table-level and
    # column-agnostic (0003_auth.py:83-84's precedent, cited by 0020).
    #
    # ⚠ Stated explicitly because test_every_tenant_id_table_has_forced_rls
    # walks pg_class and would NOT catch a mistake here — this migration creates
    # no table, so that walker has nothing new to find and the absence of a red
    # is not evidence.


def downgrade() -> None:
    # Reverse order of upgrade(). Dropping the column would take its CHECK with
    # it, but naming the constraint keeps the downgrade legible and keeps
    # test_the_seamstress_capacity_migration_round_trips asserting three
    # removals rather than one.
    #
    # ⚠ THIS DOWNGRADE LOSES LIVE DATA — every capacity a boutique has entered.
    # 0021 carries the same warning for the same reason. Stated here rather than
    # discovered on a staging rollback.
    op.execute("DROP INDEX IF EXISTS idx_alteration_tickets_tenant_assignee")
    op.execute(
        "ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_weekly_capacity_hours_check"
    )
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS weekly_capacity_hours")
