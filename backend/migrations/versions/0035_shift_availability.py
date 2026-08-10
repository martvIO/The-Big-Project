"""staff availability: shift_templates + staff_availability (F39's two tables)

Revision ID: 0035
Revises: 0034

The number was resolved from `alembic heads` at build time and must be
re-resolved before the rebase — 0032's header is the case study for what happens
when it is not. Two scripts declaring the same `revision` string do not collide
loudly: alembic warns once, dedupes to ONE script and silently drops the other,
and `test_exactly_one_migration_head` still sees exactly one head while a whole
feature's DDL is missing.

⚠ `downgrade()` DROPS BOTH TABLES AND LOSES LIVE DATA — every shift the owner
defined and every answer her staff gave. 0021/0023/0032's convention: the
sentence is here so the act is a decision rather than a discovery.

0031_dress_reservations.py is copied in every particular: raw `op.execute`, the
`_STANDARD` block, `_updated_at_trigger`, a table-level `GRANT` and
`enable_tenant_rls`. Every CHECK and both indexes are NAMED so
`pg_get_constraintdef` and `pg_indexes.indexdef` have something to pin (0023's
rule) and so a later ALTER can drop by name.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0035"
down_revision = "0034"
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
# can read the column list out of the migration ITSELF rather than out of a
# retyped copy — the same hand that forgets the model would have to edit a
# retyped list too. F38's `_COLUMNS` is the precedent and the only
# model<->migration parity mechanism that exists in Backend/tests.
_SHIFT_TEMPLATE_COLUMNS = (
    # 0=Sunday … 6=Saturday, `availability_rules.day_of_week`'s encoding, which
    # `jerusalem_day_index` produces and `packages/ui/src/lib/hours.ts` renders.
    "day_of_week INTEGER NOT NULL",
    # Operator text: «משמרת בוקר». D3's seed writes an auto-label the owner then
    # replaces the moment she splits a day, so nothing here is unique.
    "label TEXT NOT NULL",
    "starts_at_time TIME NOT NULL",
    "ends_at_time TIME NOT NULL",
    "sort_order INTEGER NOT NULL DEFAULT 0",
)

_STAFF_AVAILABILITY_COLUMNS = (
    # No FK on either pointer (house rule); the service proves both parents are
    # live before it writes.
    "staff_user_id UUID NOT NULL",
    "shift_template_id UUID NOT NULL",
    # THE JERUSALEM SUNDAY, as a DATE (spec D1). Not a TIMESTAMPTZ: a week key
    # names a page of the boutique's calendar, not an instant, and Jerusalem is
    # UTC+2 in winter and UTC+3 in summer — so the same civil Sunday would key
    # to two different instants across the year and an equality join would
    # silently miss.
    "week_start DATE NOT NULL",
    "state TEXT NOT NULL",
    # NULL when she recorded it herself (D5). An elevated actor recording on her
    # behalf stamps her own id, which is what makes «נרשם על ידי…» a column
    # rather than a derived guess.
    "recorded_by UUID",
)


def _columns(declarations: tuple[str, ...]) -> str:
    return ",\n            ".join(declarations)


def _updated_at_trigger(table: str) -> str:
    return f"""
        CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """


def upgrade() -> None:
    # ⚠ NO UNIQUE CONSTRAINT ON (day_of_week, starts_at_time) AND NO OVERLAP
    # EXCLUSION. Overlapping templates on one weekday are LEGAL and deliberate
    # (spec D2): a morning 09:00–14:00 and an afternoon 13:00–20:00 sharing the
    # changeover hour is an ordinary split shift, and refusing it makes the owner
    # fudge her real times. The platform bounds the COUNT instead
    # (MAX_TEMPLATES_PER_DAY, MAX_TEMPLATES in app/shifts/validation.py).
    #
    # `ends_at_time > starts_at_time` is a NAMED CHECK, so there is NO OVERNIGHT
    # SHIFT. A bridal boutique does not run one.
    # ponytail: an overnight template needs a crosses_midnight flag or a duration
    # column; nothing here blocks adding it.
    op.execute(
        f"""
        CREATE TABLE shift_templates (
            {_STANDARD},
            {_columns(_SHIFT_TEMPLATE_COLUMNS)},
            CONSTRAINT shift_templates_day_check CHECK (day_of_week BETWEEN 0 AND 6),
            CONSTRAINT shift_templates_order_check CHECK (ends_at_time > starts_at_time)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_shift_templates_day "
        "ON shift_templates (tenant_id, day_of_week, starts_at_time) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("shift_templates"))

    # ⚠ `EXTRACT(DOW FROM week_start) = 0` — Postgres DOW is 0=Sunday, the same
    # encoding `day_of_week` above uses. This is the LAST line of defence for
    # D1: remove the service guard and a Monday key is still refused, which is
    # exactly what test_shifts_db.py drives.
    op.execute(
        f"""
        CREATE TABLE staff_availability (
            {_STANDARD},
            {_columns(_STAFF_AVAILABILITY_COLUMNS)},
            CONSTRAINT staff_availability_state_check
                CHECK (state IN ('available', 'unavailable', 'preferred')),
            CONSTRAINT staff_availability_week_start_check
                CHECK (EXTRACT(DOW FROM week_start) = 0)
        )
        """
    )
    # PARTIAL and UNIQUE: one live answer per (staffer, shift, week). This is the
    # structural guarantee D11's concurrency argument rests on — the write is a
    # per-pair `UPDATE … RETURNING` then an `INSERT` on zero rows, with ONE retry
    # on IntegrityError, and no advisory lock. A tenant-wide lock would be far
    # too coarse for a per-tap write, and it would only serialise where this
    # index actually constrains.
    op.execute(
        "CREATE UNIQUE INDEX idx_staff_availability_unique "
        "ON staff_availability (tenant_id, staff_user_id, shift_template_id, week_start) "
        "WHERE deleted_at IS NULL"
    )
    # The roster-readiness read: one week, every staffer.
    op.execute(
        "CREATE INDEX idx_staff_availability_week "
        "ON staff_availability (tenant_id, week_start, staff_user_id) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("staff_availability"))

    for table in ("shift_templates", "staff_availability"):
        # Table-level and column-agnostic (0003_auth.py:83-84's precedent).
        # Ordinary CRUD, so no REVOKE-first dance — that is terms_versions' and
        # platform_audit_log's append-only shape.
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    # ⚠ LOSES LIVE DATA — see the header. Both indexes, both triggers and both
    # policies go with their tables. F39 adds no column to any existing table, so
    # there is nothing else to un-touch.
    op.execute("DROP TABLE IF EXISTS staff_availability")
    op.execute("DROP TABLE IF EXISTS shift_templates")
