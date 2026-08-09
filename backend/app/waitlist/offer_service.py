"""The offer claim — D4's atomic conditional claim through the shipped engine.

⚠ SHELL. The public shape is fixed here so `test_waitlist_races_db.py` (plan §3,
the acceptance contract, authored before any of this exists) imports and collects.
The behaviour lands in Phase C.
"""

import datetime
import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.service import BookingClaim
from app.errors import DomainNotFoundError
from app.payments.service import GatewayCredentialService
from app.storefront.validation import Clock


class OfferNotFoundError(DomainNotFoundError):
    """Unknown token, a token for another boutique, or an entry that has been
    purged — ONE indistinguishable 404, the manage page's rule verbatim."""


class OfferNotClaimableError(Exception):
    """The entry is no longer a live offer. `state` is what it moved to —
    `claimed`, `expired` or `cancelled` — carried for the log and for the race
    tests; the HTTP layer collapses all three into the same 409 a direct booker
    losing a race gets, because the caller is owed no oracle."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class WaitlistOfferService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        gateway_credentials: GatewayCredentialService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._gateway_credentials = gateway_credentials
        self._clock = clock

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def claim(
        self,
        tenant_id: uuid.UUID,
        *,
        token: str,
        name: str,
        terms_version: int,
        settings: Mapping[str, object] | None = None,
    ) -> BookingClaim:
        raise NotImplementedError
