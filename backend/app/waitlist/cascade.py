"""The offer cascade — D2's fourth worker job.

⚠ SHELL. The public shape is fixed here so `test_waitlist_races_db.py` (plan §3,
the acceptance contract, authored before any of this exists) imports and collects.
The behaviour lands in B2 (expiry) and B3 (the offer write).
"""

import dataclasses
import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.storefront.validation import Clock


@dataclasses.dataclass(frozen=True)
class CascadeResult:
    """One tenant, one tick. `returned` counts D7's return-to-`waiting`: an offer
    whose SMS never reached `sent` does not get to consume its window."""

    expired: int = 0
    returned: int = 0
    offered: int = 0

    def __add__(self, other: "CascadeResult") -> "CascadeResult":
        return CascadeResult(
            expired=self.expired + other.expired,
            returned=self.returned + other.returned,
            offered=self.offered + other.offered,
        )


class WaitlistCascade:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        window_seconds: int,
        min_lead_seconds: int,
        quiet_start_hour: int,
        quiet_end_hour: int,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._window = datetime.timedelta(seconds=window_seconds)
        self._min_lead = datetime.timedelta(seconds=min_lead_seconds)
        self._quiet_start_hour = quiet_start_hour
        self._quiet_end_hour = quiet_end_hour
        self._clock = clock

    async def run(self, tenant_id: uuid.UUID) -> CascadeResult:
        raise NotImplementedError
