"""F37's two 409s, end to end through the real app, with no SOS route in sight.

⚠ **`main.py` registers an exception handler PER CONCRETE CLASS and there is no
handler on the `_DetailedConflictError` base** — verified by reading the module,
and this file is what keeps it verified. A missing block does not degrade to a
generic 409: Starlette walks `type(exc).__mro__`, finds nothing, and answers a
bare **500**. The two registrations are independent, so one missing is a real
shape, and both are exercised here rather than one being assumed from the other.

The probe routes are `test_middleware.py`'s `_probe_app` idiom: a route
registered on a live `create_app()` after construction, so the whole middleware
and handler stack is real. They are GETs because CSRF fences by METHOD, and a
403 from the origin check would mask the 409 this file is about.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import DomainValidationError
from app.floor.validation import (
    SosAlreadyAcceptedError,
    SosClosedError,
    _DetailedConflictError,
)
from app.main import (
    ROOM_OCCUPIED_BODY,
    SOS_ALREADY_ACCEPTED_BODY,
    SOS_CLOSED_BODY,
    STAFF_OCCUPIED_BODY,
    create_app,
)
from app.tenancy.middleware import TenantContext

NAMED = "/__probe/sos-accepted-named"
UNNAMED = "/__probe/sos-accepted-unnamed"
CLOSED = "/__probe/sos-closed"


TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})


async def _resolver(slug: str) -> TenantContext | None:
    return TENANT if slug == "bella" else None


def _probe_app() -> FastAPI:
    app = create_app(resolver=_resolver)

    @app.get(NAMED)
    async def _named() -> None:
        raise SosAlreadyAcceptedError({"staff_display_name": "דנה"})

    @app.get(UNNAMED)
    async def _unnamed() -> None:
        raise SosAlreadyAcceptedError()

    @app.get(CLOSED)
    async def _closed() -> None:
        raise SosClosedError()

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(_probe_app(), base_url="http://bella.localtest.me") as test_client:
        yield test_client


def test_a_losing_accept_is_a_409_that_names_the_owner(client: TestClient) -> None:
    """The ruling's «a 409 NAMING THE OWNER», and it is the whole reason
    `sos_alerts.accepted_by` exists as a column. `message` is English prose the
    console never renders for a MAPPED code, so the datum has to travel in
    `details` or the UI cannot reach it."""
    resp = client.get(NAMED)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "SOS_ALREADY_ACCEPTED",
            "message": "This SOS has already been accepted.",
            "details": {"staff_display_name": "דנה"},
        }
    }


def test_an_accept_whose_winner_cannot_be_named_omits_the_key_entirely(
    client: TestClient,
) -> None:
    """⚠ The key is ABSENT, never `null`. `accepted_by` points at a `staff_users`
    row that staff removal can soft-delete at any time, and the acceptor can be
    removed between her accept and the loser's read. «{{name}} כבר מגיעה.»
    rendering with an empty interpolation on a legally binding surface is worse
    than a sentence that admits it does not know — and `Record<string, string>`
    on the console has no room for a null anyway."""
    resp = client.get(UNNAMED)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "SOS_ALREADY_ACCEPTED",
            "message": "This SOS has already been accepted.",
        }
    }
    assert "details" not in resp.json()["error"]


def test_a_closed_alert_is_a_409_that_never_carries_details(client: TestClient) -> None:
    """SOS_CLOSED is deliberately the code WITHOUT the key. Three of four
    `details`-bearing codes would be drift; four would make it the default. And
    there is nobody to name: the remedy for a closed alert is not "go talk to
    her", it is "there is nothing to do"."""
    resp = client.get(CLOSED)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {"code": "SOS_CLOSED", "message": "This SOS is already closed."}
    }


def test_the_frozen_bodies_are_never_mutated_by_a_named_409(client: TestClient) -> None:
    """⚠ The leak this guards is cross-tenant. `base["error"]` is a module
    constant shared by every request in the process, so a handler that stamped
    `details` onto it instead of onto a copy would ship one boutique's staffer
    name in the NEXT tenant's 409. Asserted after a named raise, because that is
    the only request that could have done it."""
    assert client.get(NAMED).status_code == 409
    assert SOS_ALREADY_ACCEPTED_BODY == {
        "error": {"code": "SOS_ALREADY_ACCEPTED", "message": "This SOS has already been accepted."}
    }
    assert client.get(UNNAMED).json()["error"] == SOS_ALREADY_ACCEPTED_BODY["error"]


def test_the_two_sos_conflicts_are_not_validation_errors() -> None:
    """⚠ **This assertion is the ONLY thing that pins the parentage, and F37
    proved it by mutation rather than inheriting the claim.**

    Parenting `_DetailedConflictError` onto `DomainValidationError` leaves every
    HTTP assertion in this file GREEN: Starlette walks `type(exc).__mro__` and
    takes the FIRST match, so the handler registered on the concrete class still
    wins and the 409 is still a 409. The sentence this repo carried — "the
    shipped handler would answer 400 and leave the 409 handlers unreachable" —
    is false while concrete handlers exist.

    What the parentage decides is the fate of the NEXT subclass, shipped without
    its own handler: an `Exception` answers a loud 500 that a first-run test
    catches; a `DomainValidationError` answers a quiet, plausible 400 on a
    conflict. So the rule stands and the reason is different, and this is the
    test that keeps it."""
    for error in (SosAlreadyAcceptedError, SosClosedError):
        assert issubclass(error, _DetailedConflictError)
        assert not issubclass(error, DomainValidationError)


def test_exactly_four_bodies_in_the_product_can_carry_details() -> None:
    """The enumerable set, as an assertion. F36's Risk 8 named this PR as its
    trigger: `details` is an extension of an error envelope every other body
    treats as a two-field constant, which is fine while it stays deliberate and
    bad once it is the default. All four are frozen TWO-key dicts at rest —
    `details` only ever exists on a copy made at raise time."""
    for body in (
        ROOM_OCCUPIED_BODY,
        STAFF_OCCUPIED_BODY,
        SOS_ALREADY_ACCEPTED_BODY,
        SOS_CLOSED_BODY,
    ):
        assert set(body["error"]) == {"code", "message"}
    assert {c.__name__ for c in _DetailedConflictError.__subclasses__()} == {
        "RoomOccupiedError",
        "StaffOccupiedError",
        "SosAlreadyAcceptedError",
        "SosClosedError",
    }
