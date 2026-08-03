"""fitting rooms: the registry, the assignment and its dress bindings

Revision ID: 0018
Revises: 0017
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0018"
down_revision = "0017"
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
    # `is_active` and `deleted_at` are two different facts and the feature needs
    # both. `deleted_at IS NOT NULL` means the boutique reconfigured and this
    # room is gone from the registry; `is_active = false` means the mirror is
    # broken, do not send anyone in there today. The first removes the row from
    # every read, the second leaves it on the panel greyed and with no claim
    # control — so a staffer looking for a free room can SEE that room 2 exists
    # and is out of service rather than wondering whether she forgot it.
    #
    # No unique index on `label`, and that is a decision (D1). `dresses` already
    # states the rule for a tenant-scoped name: two alcoves a boutique genuinely
    # both calls «הבמה» is not an error worth inventing a 409 for, and a room is
    # only ever addressed by id. Upgrade path if a pilot asks: a partial unique
    # on (tenant_id, lower(label)) WHERE deleted_at IS NULL.
    #
    # No index on `is_active` either: nothing filters on it — the read returns
    # every live room and the panel greys the inactive ones — so a partial index
    # would serve no reader and cost every write.
    op.execute(
        f"""
        CREATE TABLE fitting_rooms (
            {_STANDARD},
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT true
        )
        """
    )
    # BOTH sort keys, which is why created_at is in here and not only
    # sort_order. The payload orders by (sort_order, created_at); an index
    # carrying only the leading key would leave the planner sorting inside each
    # equal-sort_order group — and since sort_order defaults to 0 and the
    # registry lets it be omitted, a boutique that never reorders has EVERY room
    # in one group, i.e. the index would supply none of the ordering in the
    # common case. The tiebreak is the whole point: a 5-second repaint that
    # re-sorts the tiles is a repaint a finger cannot travel across.
    op.execute(
        "CREATE INDEX idx_fitting_rooms_tenant_order "
        "ON fitting_rooms (tenant_id, sort_order, created_at) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("fitting_rooms"))

    # `released_at IS NULL AND deleted_at IS NULL` is what ACTIVE means, and it
    # is the whole model: not a status column, not a boolean, not a row that
    # gets deleted. The nullable timestamp is simultaneously the fact (she is
    # out) and the when, which is what makes the historical row worth keeping.
    #
    # No `assigned_at` column — created_at IS the claim time, and the row is
    # created at exactly the instant of the claim. A second column would be a
    # second copy of one fact. The WIRE field is still `assigned_at`, sourced
    # from created_at, because a handover deliberately does not restart the
    # client's clock (D8).
    #
    # `deleted_at` here has NO v1 writer, and that is not an omission: no route
    # soft-deletes an assignment — release stamps `released_at`, and a mis-tapped
    # claim is corrected by releasing it. It is in both index predicates below
    # for the same reason it is on every table in this schema, so a reviewer
    # looking for the missing route should stop looking.
    #
    # `queue_ticket_id` is deliberately ABSENT. The walk-in's dispatch record is
    # F33's `queue_tickets` and the dispatch action is F58's; F58 adds the column
    # in its own migration alongside its writer, rather than this one pre-adding
    # a speculative pointer nothing can fill.
    op.execute(
        f"""
        CREATE TABLE fitting_room_assignments (
            {_STANDARD},
            fitting_room_id UUID NOT NULL,
            staff_user_id UUID NOT NULL,
            booking_id UUID,
            released_at TIMESTAMPTZ
        )
        """
    )
    # Pre-decided #31. ONE active assignment per room: this is the structural
    # guarantee the whole feature exists to give. There is no lock on the claim
    # and there does not need to be — the claim inserts three values the caller
    # already holds, derives nothing from a count, and a unique index is
    # evaluated by the index itself rather than against a transaction snapshot.
    #
    # The `released_at IS NULL` conjunct is what makes a RELEASED room
    # immediately re-claimable in the same tick. Narrow this predicate to
    # `deleted_at IS NULL` alone and a released room can never be claimed again;
    # nothing in the happy path notices, which is why the definition is pinned
    # byte-identical in test_migrations.py.
    op.execute(
        "CREATE UNIQUE INDEX idx_fitting_room_assignments_room_active "
        "ON fitting_room_assignments (tenant_id, fitting_room_id) "
        "WHERE released_at IS NULL AND deleted_at IS NULL"
    )
    # Added by the 2026-07-31 ruling. ONE active room per worker, and this is
    # what makes the staff card's `occupied` a FACT rather than a guess: the
    # derivation reads AT MOST ONE row per staffer by construction, so it never
    # has to pick between two. It also guards the RECEIVING staffer on a
    # handover, which is the second path this index earns its keep on.
    op.execute(
        "CREATE UNIQUE INDEX idx_fitting_room_assignments_staff_active "
        "ON fitting_room_assignments (tenant_id, staff_user_id) "
        "WHERE released_at IS NULL AND deleted_at IS NULL"
    )
    # Not read by this feature, and one line here rather than an ACCESS
    # EXCLUSIVE lock on a growing table later. The two unique indexes above are
    # partial on `released_at IS NULL`, so they are useless over history — and
    # this is the one table in the feature that grows monotonically. Its named
    # readers are F37 ("which assignment was this alert raised in") and F41's
    # ticket attachment. Stated cost: one more index to maintain per claim.
    op.execute(
        "CREATE INDEX idx_fitting_room_assignments_tenant_created "
        "ON fitting_room_assignments (tenant_id, created_at) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("fitting_room_assignments"))

    # A child table and not a JSONB array on the assignment: two staffers adding
    # and removing dresses concurrently would make a JSONB array a
    # read-modify-write, and the loser's write silently drops the winner's dress
    # with no error anywhere and no index able to say so.
    #
    # dress_name / dress_size are SNAPSHOTS, 0008's reasoning unchanged: the
    # owner may rename or archive a dress mid-fitting and a card must render
    # what actually went into the room. dress_id is kept alongside so the image
    # and the live variant list resolve at read time rather than being copied.
    #
    # `removed_by` carries D13's argument in one sentence: the soft-deleted row
    # IS the audit record, and without an actor it answers WHAT left the room and
    # WHEN but cannot answer WHO took it out — which, for a boutique tracking
    # gowns, is the question the trail exists for.
    op.execute(
        f"""
        CREATE TABLE fitting_assignment_dresses (
            {_STANDARD},
            fitting_room_assignment_id UUID NOT NULL,
            dress_id UUID NOT NULL,
            dress_name TEXT NOT NULL,
            dress_size TEXT,
            removed_by UUID
        )
        """
    )
    # The payload's second statement: every live binding for the assignments it
    # is rendering, skipped entirely when nothing is occupied.
    op.execute(
        "CREATE INDEX idx_fitting_assignment_dresses_assignment "
        "ON fitting_assignment_dresses (tenant_id, fitting_room_assignment_id) "
        "WHERE deleted_at IS NULL"
    )
    # THE THIRD partial unique index. One live binding per (assignment, dress),
    # and the predicate is what lets a removed dress be carried back IN. The add
    # is ON CONFLICT ... DO UPDATE rather than DO NOTHING, because DO NOTHING
    # would let an add racing an uncommitted remove answer «נוספה» for a dress
    # that ends up out of the room.
    op.execute(
        "CREATE UNIQUE INDEX idx_fitting_assignment_dresses_unique "
        "ON fitting_assignment_dresses (tenant_id, fitting_room_assignment_id, dress_id) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("fitting_assignment_dresses"))

    # Forgetting enable_tenant_rls fails a DIFFERENT file's test
    # (test_tenant_isolation.py's tenant_id scan).
    #
    # The GRANT is REDUNDANT and is kept as belt-and-braces, which is the house
    # form (0004, 0005, 0014, 0016, 0017 all say so). 0002's ALTER DEFAULT
    # PRIVILEGES already grants full CRUD on every table a later migration
    # creates as this role, so deleting this line changes nothing — verified by
    # mutation against test_fitting_rooms_isolation.py, which stayed green. What
    # it buys is a table created out-of-band by a different deploy role, which is
    # exactly what 0002's own comment says it is for.
    for table in ("fitting_rooms", "fitting_room_assignments", "fitting_assignment_dresses"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    # DROP TABLE takes the indexes, the trigger and the policy with it, so there
    # is nothing else to undo — 0008's downgrade verbatim. F36 touches no
    # existing table, so unlike F57's migration this cannot fail on live data.
    for table in ("fitting_assignment_dresses", "fitting_room_assignments", "fitting_rooms"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
