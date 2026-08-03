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
