"""roster builder: rosters + roster_assignments, coverage targets, the same-day
on-shift override (F40's one migration)

Revision ID: 0036
Revises: 0035

The number was resolved from `alembic heads` at build time and MUST be
re-resolved before the rebase. 0035's header is the case study for what happens
when it is not, and 0031's for the other half: two revisions naming the same
parent BRANCH the history, `alembic heads` then reports two, and every db-marked
test reds with a message that points at nothing in the diff. ⚠ A renumber
WITHOUT a re-parent looks exactly like a passing edit — the local fast lane never
touches Postgres — so the filename, `revision` and `down_revision` move together,
in one commit.

⚠ `downgrade()` DROPS BOTH TABLES AND ALL THREE COLUMNS, AND LOSES LIVE DATA —
every shift the owner staffed, every published week, every coverage target and
every same-day override. 0021/0023/0032/0035's convention: the sentence is here
so the act is a decision rather than a discovery.

0035_shift_availability.py is copied in every particular: raw `op.execute`, the
`_STANDARD` block, `_updated_at_trigger`, a table-level `GRANT` and
`enable_tenant_rls`. Every CHECK and every index is NAMED so
`pg_get_constraintdef` and `pg_indexes.indexdef` have something to pin (0023's
rule) and so a later ALTER can drop by name.

⚠ NO `GRANT` AND NO `enable_tenant_rls` FOR THE THREE `ALTER`s. Grants are
column-agnostic and RLS is a table property; both are already in force on
`shift_templates` (0035) and `staff_users` (0003), and F34 D2 verified this exact
point. Re-issuing `CREATE POLICY` on either would be a duplicate-object error.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

_STANDARD = """
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
"""

# Declared as data, not inline in the DDL string, so `test_boutique_models.py`
# reads the column list out of the migration ITSELF rather than out of a retyped
# copy — the same hand that forgets the model would have to edit a retyped list
# too. 0035's `_SHIFT_TEMPLATE_COLUMNS` is the precedent.
_ROSTER_COLUMNS = (
    # THE JERUSALEM SUNDAY, as a DATE — F39's `staff_availability.week_start`
    # encoding, unchanged and for its reason: a week key names a page of the
    # boutique's calendar, not an instant.
    "week_start DATE NOT NULL",
    # NULL = draft (D6). THE ONLY STATE THIS TABLE HAS. Rejected: a `status`
    # enum — it would be a second copy of a fact `published_at` already states,
    # and the pair could disagree (`sos_alerts.status`' own recorded argument).
    "published_at TIMESTAMPTZ",
    # No FK, house rule.
    "published_by UUID",
)

_ROSTER_ASSIGNMENT_COLUMNS = (
    # No FK on any of the three pointers (house rule); the service proves every
    # parent is live before it writes.
    "roster_id UUID NOT NULL",
    "shift_template_id UUID NOT NULL",
    "staff_user_id UUID NOT NULL",
    # D12: gated on `staff_users.shift_manager_eligible` ALONE and never derived
    # from `role` — F38 shipped that boolean specifically to separate "may be
    # assigned as shift manager" from "her job is shift manager".
    "is_shift_manager BOOLEAN NOT NULL DEFAULT false",
    "assigned_by UUID NOT NULL",
    # The state she had submitted when she was assigned anyway (D11). NULL = no
    # override. Only 'unavailable' is ever written today; the CHECK is the whole
    # AvailabilityState set so a later reader is not pinned to one literal.
    #
    # ⚠ STAMPED AT ASSIGNMENT TIME AND NEVER UPDATED. A staffer may go
    # unavailable AFTER she was rostered (design F-5) — that is a different fact
    # with a different render, and overwriting this column would erase the record
    # of what the owner knowingly did.
    "override_of_state TEXT",
)

# The one column F40 adds to F39's table. Read by the shift_templates half of
# `test_shift_models_declare_every_column_their_migration_creates`, which unions
# it with 0035's CREATE list.
_SHIFT_TEMPLATE_COLUMNS = (
    # D10's sparse map: {"sales_assistant": 2, "seamstress": 1}. NOT NULL with an
    # empty default, because an ABSENT KEY means «no target» and `0` means
    # «deliberately nobody» — a nullable column would give the map a third state
    # that means nothing.
    #
    # Rejected: a `shift_coverage_targets` table. It would carry a row per
    # (template × role) for a number edited on the template's own dialog, and
    # would need its own RLS policy, grants, repository and cascade. The column
    # gets the cascade for free and rides F39's PATCH, which is a FULL REPLACE of
    # all fields — so an omitted key can never silently clear it.
    "coverage_targets JSONB NOT NULL DEFAULT '{}'::jsonb",
)

# The two columns F40 adds to `staff_users`. Read by
# `test_staff_user_declares_every_column_the_hr_migration_adds`, which F40
# EXTENDS to this migration rather than adding a third parity test — scoped to
# 0032 alone it is blind to both of these.
_STAFF_USER_COLUMNS = (
    # D3/D4: THE JERUSALEM DAY THIS OVERRIDE SPEAKS FOR. A DATE and not a
    # timestamp, and that is the whole freshness rule: an override for a day that
    # is not today is never consulted, so it cannot be stale by construction and
    # there is NO clock comparison anywhere to get wrong.
    "on_shift_on DATE",
    # TWO-VALUED. true = on shift, false = off shift. Rejected: a one-way "mark
    # her on" flag — the commonest same-day event in a boutique is somebody NOT
    # coming in, and a flag that can only add people cannot express it.
    "on_shift_override BOOLEAN",
)


def _columns(declarations: tuple[str, ...]) -> str:
    return ",\n            ".join(declarations)


def _updated_at_trigger(table: str) -> str:
    return f"""
        CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """


def upgrade() -> None:
    # ⚠ `rosters` IS A ROW AND NOT A VIRTUAL GROUPING OF ASSIGNMENTS (D5).
    # "Published with nobody on this shift" and "no roster published" are
    # DIFFERENT ANSWERS and the resolver must tell them apart: deriving
    # "published" from EXISTS(assignments) collapses the two in the dangerous
    # direction, and an owner who publishes a genuinely empty Saturday would find
    # the whole boutique reported as on shift.
    #
    # `EXTRACT(DOW FROM week_start) = 0` — Postgres DOW is 0=Sunday, the same
    # encoding `staff_availability_week_start_check` carries. Last line of
    # defence: remove the service guard and a Monday key is still refused.
    op.execute(
        f"""
        CREATE TABLE rosters (
            {_STANDARD},
            {_columns(_ROSTER_COLUMNS)},
            CONSTRAINT rosters_week_start_check CHECK (EXTRACT(DOW FROM week_start) = 0),
            CONSTRAINT rosters_published_pair_check
                CHECK ((published_at IS NULL) = (published_by IS NULL))
        )
        """
    )
    # One live roster per (tenant, week). PARTIAL, so a soft-deleted week does
    # not block a new one.
    op.execute(
        "CREATE UNIQUE INDEX idx_rosters_week_unique "
        "ON rosters (tenant_id, week_start) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("rosters"))

    # ⚠ THE CHECK SET IS THE WHOLE `AvailabilityState`, NOT JUST 'unavailable'.
    # Today the service writes only 'unavailable' (D11), but pinning the column
    # to one literal would make the next reader's honest question — "what did she
    # actually say?" — unanswerable without a migration.
    op.execute(
        f"""
        CREATE TABLE roster_assignments (
            {_STANDARD},
            {_columns(_ROSTER_ASSIGNMENT_COLUMNS)},
            CONSTRAINT roster_assignments_override_check
                CHECK (override_of_state IS NULL
                       OR override_of_state IN ('available', 'unavailable', 'preferred'))
        )
        """
    )
    # One live assignment per (roster, shift, staffer). The structural guarantee
    # the UPSERT's optimistic write rests on — `UPDATE … RETURNING` then `INSERT`
    # on zero rows, with ONE retry on IntegrityError and no advisory lock
    # (F39's shipped shape).
    op.execute(
        "CREATE UNIQUE INDEX idx_roster_assignments_unique "
        "ON roster_assignments (tenant_id, roster_id, shift_template_id, staff_user_id) "
        "WHERE deleted_at IS NULL"
    )
    # D12: AT MOST ONE SHIFT MANAGER PER SHIFT, structurally. A service
    # read-then-write would only be a serialisation; this refuses the second
    # setter outright and the loser gets 409 from the index rather than from a
    # read that raced.
    op.execute(
        "CREATE UNIQUE INDEX idx_roster_assignments_manager_unique "
        "ON roster_assignments (tenant_id, roster_id, shift_template_id) "
        "WHERE deleted_at IS NULL AND is_shift_manager"
    )
    # The builder's read: one roster, every shift.
    op.execute(
        "CREATE INDEX idx_roster_assignments_roster "
        "ON roster_assignments (tenant_id, roster_id, shift_template_id) WHERE deleted_at IS NULL"
    )
    # The resolver's read and MyWeekPanel's, both: one staffer across a roster.
    op.execute(
        "CREATE INDEX idx_roster_assignments_staff "
        "ON roster_assignments (tenant_id, staff_user_id, roster_id) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("roster_assignments"))

    for table in ("rosters", "roster_assignments"):
        # Table-level and column-agnostic (0003_auth.py:83-84's precedent).
        # Ordinary CRUD, so no REVOKE-first dance — that is terms_versions' and
        # platform_audit_log's append-only shape.
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)

    for declaration in _SHIFT_TEMPLATE_COLUMNS:
        op.execute(f"ALTER TABLE shift_templates ADD COLUMN {declaration}")
    for declaration in _STAFF_USER_COLUMNS:
        op.execute(f"ALTER TABLE staff_users ADD COLUMN {declaration}")
    # D4's pair invariant, in the schema rather than in a comment: an override
    # is a (day, answer) or it is nothing at all.
    op.execute(
        "ALTER TABLE staff_users ADD CONSTRAINT staff_users_on_shift_pair_check "
        "CHECK ((on_shift_on IS NULL) = (on_shift_override IS NULL))"
    )


def downgrade() -> None:
    # ⚠ LOSES LIVE DATA — see the header. Both indexes, both triggers and both
    # policies go with their tables; the three ALTERs are undone by name.
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_on_shift_pair_check")
    for declaration in _STAFF_USER_COLUMNS:
        op.execute(f"ALTER TABLE staff_users DROP COLUMN IF EXISTS {declaration.split()[0]}")
    for declaration in _SHIFT_TEMPLATE_COLUMNS:
        op.execute(f"ALTER TABLE shift_templates DROP COLUMN IF EXISTS {declaration.split()[0]}")
    op.execute("DROP TABLE IF EXISTS roster_assignments")
    op.execute("DROP TABLE IF EXISTS rosters")
