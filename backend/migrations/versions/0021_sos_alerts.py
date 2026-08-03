"""sos alerts: one table, one partial index, and deliberately no unique index

Revision ID: 0021
Revises: 0020
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0021"
down_revision = "0020"
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
    # ONE table. `sos_alert_targets` is NOT built and the epic's justification
    # for it no longer applies: the 2026-07-31 ruling replaced the role fanout
    # with ONE target — a specific colleague or the shift-manager role — so the
    # audience IS `target_staff_user_id`, a single nullable column, and there is
    # nothing to snapshot. A child table would be one insert per raise and one
    # join per tick to record a set with at most one member.
    #
    # `target_staff_user_id` carries BOTH meanings of NULL in one sentence: the
    # shift-manager ROLE (the audience {owner, shift_manager}, which F51's
    # last-owner invariant guarantees is never empty), AND a named colleague who
    # turned out to be unreachable and the raise rerouted. That second meaning is
    # exactly why the SOS_RAISED audit row carries the REQUESTED target and this
    # column cannot: the reroute writes NULL over the only record of whom she
    # actually tried to page.
    #
    # `fitting_room_assignment_id` is nullable and NULL is ordinary — a staffer
    # not in a room, or a pointer that no longer resolves. A page never fails
    # over one: the raise resolves it permissively and stores NULL if it does not
    # resolve to HER OWN assignment. «No room» is a defined safe state; «wrong
    # room» would send a responder to a stranger's curtain.
    #
    # `accepted_by` is written by the SAME statement as `status` (the conditional
    # UPDATE), so «accepted with nobody» and «open but owned» are both
    # unrepresentable. It exists because a losing accept must answer a 409 that
    # NAMES THE OWNER, which is unanswerable from `status` and `acknowledged_at`.
    #
    # `acknowledged_at`, not `accepted_at` — LOOP-STATE's name governs.
    #
    # No `resolved_at`, no `resolved_by`, no `cancelled_at`: `status` says which
    # terminal state, the shipped trigger stamps `updated_at`, and the audit row
    # is the record of who and when. Nothing in v1 or in the queue reads alert
    # history. Upgrade path if a pilot wants a response-time report: three
    # columns and a writer, on a table whose only reader today is a poll over the
    # live set.
    #
    # `deleted_at` has NO v1 WRITER, and that is not an omission: nothing
    # soft-deletes an alert — resolve and cancel are status transitions. It is in
    # the index predicate for the same reason it is on every table in this
    # schema, so a reviewer looking for the missing route should stop looking.
    op.execute(
        f"""
        CREATE TABLE sos_alerts (
            {_STANDARD},
            raised_by UUID NOT NULL,
            target_staff_user_id UUID,
            fitting_room_assignment_id UUID,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            accepted_by UUID,
            acknowledged_at TIMESTAMPTZ,
            CONSTRAINT sos_alerts_status_check
                CHECK (status IN ('open', 'accepted', 'resolved', 'cancelled'))
        )
        """
    )
    # The poll's ENTIRE read: this tenant's non-terminal alerts, oldest first.
    # The predicate is matched EXACTLY by the query so the planner uses it.
    #
    # ⚠ NO UNIQUE INDEX ON THIS TABLE, AND THAT IS A DECISION. The tempting one —
    # `(tenant_id, raised_by, target_staff_user_id) WHERE status = 'open'` — is
    # DEFEATED BY NULL-DISTINCTNESS in the common case: a NULL target is the
    # shift-manager route and the destination of every reroute, and Postgres
    # treats NULLs as distinct, so the index would refuse the duplicate in the
    # RARE case (two pages to one named colleague) and permit it in the ordinary
    # one. An index that guards everything except the case it was written for is
    # worse than none, because it is a guarantee a reviewer will believe. And
    # dropping the target from the key would forbid the legitimate double page
    # («a seamstress AND the manager»), which is a real thing a staffer alone
    # with a bride does.
    #
    # The structural guarantee is the conditional `UPDATE ... WHERE status =
    # 'open'`: it constrains a TRANSITION, not a population, and needs no index
    # at all. Duplicates are noise, not corruption — two cards on an overlay,
    # either of which resolves the emergency.
    #
    # NO HISTORY INDEX either, and F36's is deliberately not copied.
    # `idx_fitting_room_assignments_tenant_created` shipped with NAMED readers;
    # this one would have none — nothing in v1, in the queue or in E8-E10 reads a
    # resolved alert. Upgrade path with its stated cost: the day something
    # reports on response times it adds `(tenant_id, created_at) WHERE deleted_at
    # IS NULL` and takes the ACCESS EXCLUSIVE lock on a table that will still be
    # small.
    op.execute(
        "CREATE INDEX idx_sos_alerts_live ON sos_alerts (tenant_id, created_at) "
        "WHERE status IN ('open', 'accepted') AND deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("sos_alerts"))

    # Forgetting enable_tenant_rls fails a DIFFERENT file's test
    # (test_tenant_isolation.py's tenant_id scan). Forgetting the GRANT fails
    # NOTHING until the app role touches the table.
    #
    # The GRANT is REDUNDANT and kept as belt-and-braces, which is the house form
    # (0004, 0005, 0014, 0016, 0017, 0019 all say so): 0002's ALTER DEFAULT
    # PRIVILEGES already grants full CRUD on every table a later migration
    # creates as this role. What it buys is a table created out-of-band by a
    # different deploy role.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON sos_alerts TO app_user")
    for statement in enable_tenant_rls("sos_alerts"):
        op.execute(statement)


def downgrade() -> None:
    # DROP TABLE takes the index, the trigger and the policy with it, so there is
    # nothing else to undo — 0008's downgrade verbatim. F37 touches no existing
    # table, so it has nothing to un-touch and this cannot fail on live data.
    op.execute("DROP TABLE IF EXISTS sos_alerts")
