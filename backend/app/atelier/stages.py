"""The pure core of the atelier board: the stage derivation, the predicate
builder every conditional write is spelled from, and the tenant band resolver.

No I/O, no session, no fakes — every function here is a total function of its
arguments, which is what lets the four-outcome discriminators in the service and
the guarded UPDATEs in the repository be tested without a database.

It lives here rather than in the repository or the service because BOTH need it:
the repository builds its predicates from `later_columns`, the service
discriminates its outcomes with `stage_of`, and putting either in the other would
create a backwards import edge.
"""

from typing import Any

from app.models.alteration_ticket import AlterationTicket
from app.models.constants import EffortBand, TicketStage
from app.models.staff_user import StaffUser

# One column per stage, in declaration order. The mapping is separate from the
# enum because the enum is the WIRE contract and these are column names — F44
# reads the columns directly and must not have to know the wire words.
STAGE_COLUMNS: dict[TicketStage, str] = {
    TicketStage.INTAKE: "intake_at",
    TicketStage.IN_PROGRESS: "in_progress_at",
    TicketStage.QC: "qc_at",
    TicketStage.READY: "ready_at",
    TicketStage.DELIVERED: "delivered_at",
}


def stage_of(row: AlterationTicket) -> TicketStage:
    """The RIGHTMOST stamped column, in declaration order.

    Total by construction: the fallback is INTAKE, so a row with no stamp at all
    — which the writer cannot produce, because the INSERT stamps intake_at — is
    read as intake rather than crashing a poll every five seconds. `StaffCard`'s
    `card_status` is the same shape one file over: a total function of nullable
    columns whose output set is pinned by a set-equality test.

    ⚠ RIGHTMOST, NEVER THE FIRST NULL. A seamstress who takes a hem from intake
    straight to ready in one sitting leaves in_progress_at and qc_at NULL forever
    and the ticket is at `ready`. An implementation that walks forward looking for
    the first NULL answers `in_progress` on that row — and answers it in the
    direction that lets a stale board stamp a stage the garment has already left.
    An earlier NULL beside a later stamp means "that stage was never separately
    recorded", not that it did not happen.
    """
    current = TicketStage.INTAKE
    for stage in TicketStage:
        if getattr(row, STAGE_COLUMNS[stage]) is not None:
            current = stage
    return current


def later_columns(target: TicketStage) -> tuple[str, ...]:
    """Every stamp column AFTER `target` in declaration order.

    This is D3's entire concurrency mechanism, and it does two jobs in one
    predicate the DATABASE evaluates: it refuses a backwards stamp (a stale board
    tapping `qc` on a ticket already at `ready`) and it refuses the loser of a
    genuine race — neither of which a pre-read can do, because another
    transaction can invalidate a pre-read between the SELECT and the UPDATE.

    `delivered` answers the empty tuple: nothing comes after it, so the last
    advance is an ordinary conditional write rather than a special case.

    The target's OWN column is deliberately absent — it is a separate clause,
    `IS NULL` for an advance and `IS NOT NULL` for an undo, and folding it in
    here would make the undo's predicate self-contradictory.
    """
    stages = list(TicketStage)
    return tuple(STAGE_COLUMNS[stage] for stage in stages[stages.index(target) + 1 :])


# The platform's five. A tenant tunes them per band; nobody has to configure
# anything for the board to work, and the E9 brief's reason for tunability at all
# ("'half-day' is not 240 minutes in a boutique whose shifts are six hours") is
# about F42's capacity arithmetic, which F41 does not perform.
DEFAULT_EFFORT_BANDS: dict[EffortBand, int] = {
    EffortBand.THIRTY_MIN: 30,
    EffortBand.ONE_HOUR: 60,
    EffortBand.TWO_HOURS: 120,
    EffortBand.HALF_DAY: 240,
    EffortBand.FULL_DAY: 480,
}

# The DB CHECK's own ceiling, restated here because this resolver is the ONLY
# thing between a hand-edited JSONB blob and that constraint. Without it a stored
# 5000 reaches the INSERT and answers a 500 on intake instead of a ticket.
MAX_BAND_MINUTES = 1440


def _positive_int(value: Any, default: int) -> int:
    """A positive int within the CHECK's bound, or the platform default.

    `bool` is excluded explicitly because it is an `int` subclass in Python and
    `True` would otherwise resolve to a one-minute band. Floats are refused
    rather than rounded: rounding picks a value nobody chose.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if value <= 0 or value > MAX_BAND_MINUTES:
        return default
    return value


def effort_bands(settings: dict[str, Any]) -> dict[EffortBand, int]:
    """The tenant's five bands, resolved from `tenants.settings`.

    ⚠ THIS READ COSTS NO STATEMENT. `TenantContext.settings` is already bound on
    the request by the tenancy middleware, so the router passes the dict straight
    in. Reading it back through `TenantsRepository` would open a FOURTH session,
    pool checkout and BEGIN/COMMIT on the hottest read in the feature, every five
    seconds per device — that repository is constructed with a session_factory and
    opens its own session inside every method, so it cannot join the atelier's
    tenant_session.

    Resolution is PER BAND with a platform default, so a partial mapping is legal
    and one junk value costs that band its tuning and nothing else. Iteration is
    over the ENUM and never over the stored dict, so a renamed key or a typo in a
    hand-edited blob cannot put a sixth band on the wire.

    **Every tenant always has exactly five bands.** That is what lets the intake
    form render with no empty-state branch and what lets `effort_minutes NOT NULL`
    hold. A brand-new boutique has no `atelier` key at all and that is the normal
    case, not an error — no shipped writer can reach the key, because
    `merge_settings` takes only `profile=` and `toggles=`. F42 owns the editor.
    """
    atelier = settings.get("atelier")
    stored = atelier.get("effort_bands") if isinstance(atelier, dict) else None
    if not isinstance(stored, dict):
        stored = {}
    return {
        band: _positive_int(stored.get(band.value), DEFAULT_EFFORT_BANDS[band])
        for band in EffortBand
    }


# 0022's CHECK ceiling, restated once so the column bound and the settings bound
# cannot drift. `boutique/validation.py` imports it from HERE and not from
# `atelier/validation.py`: this module imports only `app.models`, so the edge
# stays acyclic, while `atelier/validation.py` would drag `app.booking.validation`
# and `app.catalog.validation` in behind it (D5).
MAX_WEEKLY_CAPACITY_HOURS = 168


def default_capacity_hours(settings: dict[str, Any]) -> int | None:
    """The tenant's house default, or None. THERE IS NO PLATFORM DEFAULT.

    The asymmetry with `effort_bands`' five is deliberate (D2) and it is two
    arguments: `effort_minutes` is NOT NULL so band resolution must always answer
    a number, while `weekly_capacity_hours` is nullable and "unknown" is
    representable; and a wrong band is bounded inside five coarse presets while a
    wrong capacity is a DENOMINATOR that renders every one of her bars at a
    fraction of the truth, in the colour that says everything is fine.

    ⚠ IT DOES NOT SHARE `_positive_int`. That helper's range is `1..1440` and it
    refuses `0`; this one's is `0..168` and `0` is a value it must keep — "the
    boutique is stood down this week". One helper with two range parameters would
    be a parameterised abstraction over two call sites whose only interesting
    property is precisely the boundary it would have to parameterise.
    """
    atelier = settings.get("atelier")
    stored = atelier.get("default_weekly_capacity_hours") if isinstance(atelier, dict) else None
    if isinstance(stored, bool) or not isinstance(stored, int):
        return None
    return stored if 0 <= stored <= MAX_WEEKLY_CAPACITY_HOURS else None


def resolve_capacity(row: StaffUser, tenant_default: int | None) -> tuple[int | None, bool]:
    """Returns (resolved_hours, capacity_is_default).

    ⚠ `is not None`, NEVER truthiness. `0` is a DELIBERATE value — "she is not
    available this week" (D1) — and `or` would hand her the boutique's default,
    render her bar at a fraction of the truth in the non-overload colour, print
    «ברירת מחדל של הבוטיק» on a number she personally set, and sort her FIRST in
    the assign Select. The shipped `settings.get("atelier") or {}` idiom is
    exactly the habit that produces the bug here, which is why this is code and
    not a sentence.

    `capacity_is_default` is False when the answer is None: there is nothing to
    have defaulted to, and the row renders «לא הוגדרה קיבולת» with no bar.
    """
    if row.weekly_capacity_hours is not None:
        return row.weekly_capacity_hours, False
    return tenant_default, tenant_default is not None
