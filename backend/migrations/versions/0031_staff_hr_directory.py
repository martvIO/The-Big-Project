"""staff hr directory: eleven columns, two content-type CHECKs, one backfill

Revision ID: 0031
Revises: 0030

The number was resolved from `alembic heads` at build time and is NOT reserved.
Observed head on rebased `main` was `0028` at build time, with F28 and F35
holding `0029` and `0030` in live unmerged worktrees. F35 then MERGED mid-build
and `0030` became real, so `down_revision` was repointed from `0028` to `0030`
at the rebase — the renumber protocol working exactly as written. `0029` is
still F28's and is still unmerged, so this chain reads 0028 -> 0030 -> 0031 with
a gap, which alembic does not care about and a reader might: the numbers are
claim order, not a dense sequence. 0023's header records what
reserving a number costs — alembic keys revisions by the STRING, warns
`Revision N is present more than once`, dedupes to ONE script and silently drops
the other, which on a fresh database means a whole feature's DDL never runs.
`test_exactly_one_migration_head` is what proves it, and only AFTER the rebase.

0023_seamstress_capacity.py is the precedent this follows in every particular:
raw `op.execute`, NAMED table constraints so `pg_get_constraintdef` has a name to
pin, and the model edited in the SAME commit because **no model<->migration
parity test exists anywhere in Backend/tests** — an omitted column is an
AttributeError at first read, not a red test.
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

# Nullable-with-no-default is the one `ALTER TABLE … ADD COLUMN` form Postgres
# does as METADATA ONLY. `shift_manager_eligible` is the single exception and it
# carries a default deliberately: "may she be slotted as shift manager" has no
# meaningful NULL — an unanswered question here is `false`, not a third state —
# and since PG11 a non-volatile default is still metadata-only.
_COLUMNS = (
    # Contact only. NOT a login identifier (spec C1): Interview Q11 was overridden
    # by F31 — staff sign in with email + password — so no auth path reads this,
    # it carries NO unique index (a shared household number and a blank are both
    # legal), and it is scrubbed at the retention boundary. A unique index would
    # ALSO collide at scrub time, which is the exact trap `_erased_phone`'s
    # docstring records for `customers`.
    "phone TEXT",
    "start_date DATE",
    # The retention clock's zero. NULL means "still employed"; the scrub's
    # predicate requires it NOT NULL, which is why the backfill below is
    # load-bearing rather than tidy.
    "last_day DATE",
    "shift_manager_eligible BOOLEAN NOT NULL DEFAULT false",
    # D22's self-falsifying guard, `customers.erased_at`'s shape: the scrub's own
    # UPDATE destroys the predicate that selected the row. Drop this column from
    # the WHERE and the policy re-scrubs its own output forever.
    "scrubbed_at TIMESTAMPTZ",
    # SIX photo columns, not a `staff_photos` table (spec Data model): one photo
    # per person means no sort order, no per-parent cap, no count, no sweep loop
    # and no list — a table would buy a repository and an RLS policy to express
    # "at most one". The pending/live PAIR is what makes *replace* safe: the old
    # photo keeps rendering until the new one confirms.
    "photo_key TEXT",
    "photo_content_type TEXT",
    "photo_confirmed_at TIMESTAMPTZ",
    "photo_pending_key TEXT",
    "photo_pending_content_type TEXT",
    "photo_pending_at TIMESTAMPTZ",
)

# The DB pins the accepted set because it is a SECURITY BOUNDARY, not duplication
# — 0006's own words about the same three types. `app/catalog/validation.py`'s
# ACCEPTED_CONTENT_TYPES is the source; the test imports it and compares rather
# than retyping, so widening one without the other is a red.
_CONTENT_TYPES = "('image/jpeg', 'image/png', 'image/webp')"
_PHOTO_CHECK = "staff_users_photo_content_type_check"
_PHOTO_PENDING_CHECK = "staff_users_photo_pending_content_type_check"


def upgrade() -> None:
    for column in _COLUMNS:
        op.execute(f"ALTER TABLE staff_users ADD COLUMN {column}")

    # `IS NULL OR IN (…)` and not a bare `IN`: every one of these columns is NULL
    # on every existing row and on every staffer who never uploads a photo, and a
    # CHECK that refused NULL would refuse the ordinary state.
    op.execute(
        f"ALTER TABLE staff_users ADD CONSTRAINT {_PHOTO_CHECK} "
        f"CHECK (photo_content_type IS NULL OR photo_content_type IN {_CONTENT_TYPES})"
    )
    op.execute(
        f"ALTER TABLE staff_users ADD CONSTRAINT {_PHOTO_PENDING_CHECK} "
        "CHECK (photo_pending_content_type IS NULL "
        f"OR photo_pending_content_type IN {_CONTENT_TYPES})"
    )

    # ⚠ LOAD-BEARING, not a courtesy. Every staffer deactivated before F38 has
    # `last_day IS NULL`, and the retention policy's predicate requires
    # `last_day IS NOT NULL` — so without this line every already-offboarded
    # staffer is PERMANENTLY unscrubbable, silently, with nothing anywhere to
    # indicate it.
    #
    # `AT TIME ZONE 'Asia/Jerusalem'` before the ::date cast because `last_day` is
    # a JERUSALEM calendar date and `deleted_at` is a UTC instant. A bare
    # `deleted_at::date` would land the day before for anything deactivated
    # between midnight and 02:00/03:00 local — off by one on the clock that
    # decides when personal data is destroyed.
    op.execute(
        "UPDATE staff_users SET last_day = (deleted_at AT TIME ZONE 'Asia/Jerusalem')::date "
        "WHERE deleted_at IS NOT NULL AND last_day IS NULL"
    )

    # No index. `phone` is non-unique by C1; `last_day` is read only by the
    # retention sweep, which already scans one tenant's single-digit staff rows
    # under RLS. No enable_tenant_rls and no GRANT: `staff_users` has forced RLS
    # from 0003, and adding a column to a table under a policy does not change the
    # policy (0003_auth.py:83-84's precedent, cited by 0020 and 0023).
    #
    # ⚠ test_every_tenant_id_table_has_forced_rls would NOT catch a mistake here —
    # this migration creates no table, so that walker has nothing new to find and
    # the absence of a red is not evidence.


def downgrade() -> None:
    # ⚠ THIS DOWNGRADE LOSES LIVE DATA — every phone, start date, eligibility flag
    # and photo pointer the boutique has entered, plus the backfilled last_days
    # that are the ONLY record of when a pre-F38 staffer left. 0021 and 0023 carry
    # the same warning for the same reason. Stated here rather than discovered on
    # a staging rollback.
    op.execute(f"ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS {_PHOTO_PENDING_CHECK}")
    op.execute(f"ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS {_PHOTO_CHECK}")
    for column in reversed(_COLUMNS):
        name = column.split()[0]
        op.execute(f"ALTER TABLE staff_users DROP COLUMN IF EXISTS {name}")
