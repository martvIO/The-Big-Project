"""F19 fast units: the gateway-connected read (D10) and the `deposit_due`
predicate (D19). No database.

**These live here and not in test_payments_service.py** because that module is
`pytestmark = pytest.mark.db` end to end — it exists for the gathered-concurrency
cases that need real connections. Nothing below needs one: `is_connected` is a
single repository call behind two in-process property checks, and the predicate
is pure. A fast test that only runs in the db suite is a fast test nobody runs.

**The four `is_connected` cases are the point of the method.** The spec's earlier
draft had the storefront read `active_for_provider` directly — tenant + provider
+ `deleted_at IS NULL`, and nothing else. Cases 1-3 are exactly the three
boutiques that read would have shown a deposit to and then refused at
booking-create with a 409 or a 503.
"""

import datetime
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.service import deposit_due
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.gateway_credentials import GatewayCredentialsRepository
from app.models.appointment_type import AppointmentType
from app.models.constants import GatewayCredentialStatus
from app.models.tenant_gateway_credential import TenantGatewayCredential
from app.payments.base import PaymentGateway
from app.payments.fake import FakeGateway
from app.payments.secretbox import FakeSecretBox, SecretBox, UnconfiguredSecretBox
from app.payments.service import GatewayCredentialService
from app.payments.unconfigured import UnconfiguredGateway
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.storefront.service import StorefrontService

TENANT_ID = uuid.uuid4()
NOW = datetime.datetime(2026, 8, 3, 9, 0, tzinfo=datetime.UTC)
DEPOSITS_ON: dict[str, object] = {"toggles": {"deposits_enabled": True, "brides_only": False}}
DEPOSITS_OFF: dict[str, object] = {"toggles": {"deposits_enabled": False}}


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    """`tenant_session`'s set_config surface and nothing else — every repository
    call these tests reach is patched out, so a statement escaping to a real
    session raises here instead of passing silently."""

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


@asynccontextmanager
async def _fake_session_factory() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _factory() -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], _fake_session_factory)


def _limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=100, window_seconds=3600, clock=time.monotonic)


def _credentials(
    *, gateway: PaymentGateway | None = None, secret_box: SecretBox | None = None
) -> GatewayCredentialService:
    return GatewayCredentialService(
        _factory(),
        gateway=gateway if gateway is not None else FakeGateway(),
        secret_box=secret_box if secret_box is not None else FakeSecretBox(),
        connect_limiter=_limiter(),
        validate_limiter=_limiter(),
    )


def _row(status: str) -> TenantGatewayCredential:
    return TenantGatewayCredential(
        tenant_id=TENANT_ID,
        provider="fake",
        ciphertext="fake-secretbox-v1:x",
        key_ref="fake",
        status=status,
        last_validated_at=NOW,
        created_by=uuid.uuid4(),
    )


def _stored(
    monkeypatch: pytest.MonkeyPatch, row: TenantGatewayCredential | None
) -> list[tuple[uuid.UUID, str]]:
    """Patches the USE-path read and records what it was asked for, so a caller
    that skipped the two property checks is visible rather than merely wrong."""
    calls: list[tuple[uuid.UUID, str]] = []

    async def _active(
        self: object, session: object, tenant_id: uuid.UUID, *, provider: str
    ) -> TenantGatewayCredential | None:
        calls.append((tenant_id, provider))
        return row

    monkeypatch.setattr(GatewayCredentialsRepository, "active_for_provider", _active)
    return calls


def _appointment_type(
    *, deposit_required: bool = True, deposit_amount_agorot: int | None = 15_000
) -> AppointmentType:
    return AppointmentType(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        name="מדידת כלה",
        duration_minutes=60,
        audience="brides_only",
        deposit_required=deposit_required,
        deposit_amount_agorot=deposit_amount_agorot,
        sort_order=0,
        created_at=NOW,
    )


def _types(monkeypatch: pytest.MonkeyPatch, rows: list[AppointmentType]) -> None:
    async def _list_active(
        self: object, session: object, tenant_id: uuid.UUID
    ) -> list[AppointmentType]:
        return rows

    monkeypatch.setattr(AppointmentTypesRepository, "list_active", _list_active)


# --- is_connected: the same three checks the USE path runs (D10) ---


async def test_is_connected_is_false_when_the_stored_credential_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`revalidate` flipped it. `active_for_provider` still returns the row —
    only the status check refuses it, and `credentials_for` refuses it too."""
    _stored(monkeypatch, _row(GatewayCredentialStatus.INVALID.value))
    connected = await _credentials().is_connected(TENANT_ID, cast(AsyncSession, _FakeSession()))
    assert connected is False


async def test_is_connected_is_false_when_the_secret_box_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid row this deployment cannot decrypt. `open_deposit` would raise
    SecretBoxNotConfiguredError -> 503, so the storefront must not offer it."""
    calls = _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))
    service = _credentials(secret_box=UnconfiguredSecretBox())
    assert await service.is_connected(TENANT_ID, cast(AsyncSession, _FakeSession())) is False
    # Refused before the read: the property checks are not decoration.
    assert calls == []


async def test_is_connected_is_false_when_the_gateway_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))
    service = _credentials(gateway=UnconfiguredGateway())
    assert await service.is_connected(TENANT_ID, cast(AsyncSession, _FakeSession())) is False
    assert calls == []


async def test_is_connected_is_false_when_nothing_is_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stored(monkeypatch, None)
    connected = await _credentials().is_connected(TENANT_ID, cast(AsyncSession, _FakeSession()))
    assert connected is False


async def test_is_connected_is_true_only_when_all_three_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))
    connected = await _credentials().is_connected(TENANT_ID, cast(AsyncSession, _FakeSession()))
    assert connected is True
    assert calls == [(TENANT_ID, "fake")]


# --- deposit_due: one predicate, two callers (D19) ---


def test_deposit_due_is_false_when_deposits_are_switched_off() -> None:
    """The toggle's FIRST backend reader. The master switch wins over the
    per-type flag and over a working gateway: she keeps taking bookings and
    stops collecting."""
    assert deposit_due(DEPOSITS_OFF, _appointment_type(), gateway_connected=True) is False


def test_deposit_due_is_false_when_the_toggle_was_never_set() -> None:
    """`tenants.settings` starts `{}`. Absent reads as off — a deposit is money."""
    assert deposit_due({}, _appointment_type(), gateway_connected=True) is False
    assert deposit_due(None, _appointment_type(), gateway_connected=True) is False


def test_deposit_due_is_false_when_the_amount_is_zero_or_unset() -> None:
    zero = _appointment_type(deposit_amount_agorot=0)
    unset = _appointment_type(deposit_amount_agorot=None)
    assert deposit_due(DEPOSITS_ON, zero, gateway_connected=True) is False
    assert deposit_due(DEPOSITS_ON, unset, gateway_connected=True) is False


def test_deposit_due_is_false_when_the_type_does_not_require_one() -> None:
    row = _appointment_type(deposit_required=False)
    assert deposit_due(DEPOSITS_ON, row, gateway_connected=True) is False


def test_deposit_due_is_false_with_no_connected_gateway() -> None:
    assert deposit_due(DEPOSITS_ON, _appointment_type(), gateway_connected=False) is False


def test_deposit_due_is_true_when_all_four_hold() -> None:
    assert deposit_due(DEPOSITS_ON, _appointment_type(), gateway_connected=True) is True


# --- the storefront disclosure (D10) ---


def _storefront(credentials: GatewayCredentialService | None) -> StorefrontService:
    return StorefrontService(
        _factory(),
        media_storage=UnconfiguredMediaStorage(),
        gateway_credentials=credentials,
    )


async def test_storefront_hides_the_deposit_with_no_connected_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F17 Q1: hide it entirely and book as if deposits were off. The router
    projects the row field by field, so the row itself has to say no deposit."""
    _types(monkeypatch, [_appointment_type()])
    _stored(monkeypatch, _row(GatewayCredentialStatus.INVALID.value))

    rows = await _storefront(_credentials()).list_appointment_types(TENANT_ID, settings=DEPOSITS_ON)
    assert [(row.deposit_required, row.deposit_amount_agorot) for row in rows] == [(False, None)]


async def test_storefront_discloses_the_deposit_with_a_connected_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _types(monkeypatch, [_appointment_type()])
    _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))

    rows = await _storefront(_credentials()).list_appointment_types(TENANT_ID, settings=DEPOSITS_ON)
    assert [(row.deposit_required, row.deposit_amount_agorot) for row in rows] == [(True, 15_000)]


async def test_storefront_hides_the_deposit_when_deposits_are_switched_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _types(monkeypatch, [_appointment_type()])
    _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))

    rows = await _storefront(_credentials()).list_appointment_types(
        TENANT_ID, settings=DEPOSITS_OFF
    )
    assert [(row.deposit_required, row.deposit_amount_agorot) for row in rows] == [(False, None)]


async def test_storefront_leaves_a_type_that_never_had_a_deposit_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _types(monkeypatch, [_appointment_type(deposit_required=False, deposit_amount_agorot=None)])
    _stored(monkeypatch, _row(GatewayCredentialStatus.VALID.value))

    rows = await _storefront(_credentials()).list_appointment_types(TENANT_ID, settings=DEPOSITS_ON)
    assert [(row.deposit_required, row.deposit_amount_agorot) for row in rows] == [(False, None)]


async def test_storefront_hides_the_deposit_with_no_gateway_service_wired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-wiring deployment. Unwired must read as not connected, never as
    connected — the whole point of the predicate is that money is opt-in."""
    _types(monkeypatch, [_appointment_type()])
    rows = await _storefront(None).list_appointment_types(TENANT_ID, settings=DEPOSITS_ON)
    assert [(row.deposit_required, row.deposit_amount_agorot) for row in rows] == [(False, None)]
