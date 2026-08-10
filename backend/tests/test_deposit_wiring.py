"""The deposit's WIRING, which no unit test can check by construction.

`deposit_due()` is `deposits_enabled AND deposit_required AND amount > 0 AND
gateway_connected`, and the last conjunct is answered by a
`GatewayCredentialService` that `StorefrontService` and `BookingService` each
receive as an OPTIONAL constructor argument defaulting to `None`. Every unit test
of those two services passes it explicitly — including
`test_storefront_hides_the_deposit_with_no_connected_gateway`, which proves the
not-connected branch works. So the suite is green on both branches while the
ASSEMBLED app can still be pinned to one of them forever.

It was. Found 2026-08-10 by walking the deposit journey against a real database
with a real browser: with `deposits_enabled`, `deposit_required`, a 15000-agorot
amount and a gateway both connected and validated, `POST /storefront/bookings`
answered `deposit_due: false, redirect_url: null` and the storefront disclosed no
deposit at all. `create_app` built both services ~200 lines BEFORE it built the
gateway service, so both silently took the `None` default and every deposit in
the product was uncollectable.

These assertions are about the object graph `create_app` actually produces, which
is the only place the defect was visible.
"""

from fastapi import FastAPI

from app.main import create_app


async def _nothing_resolves(slug: str) -> None:
    return None


def _app() -> FastAPI:
    return create_app(resolver=_nothing_resolves)


def test_the_storefront_service_can_answer_whether_a_gateway_is_connected() -> None:
    app = _app()
    assert app.state.storefront_service._gateway_credentials is app.state.gateway_credential_service


def test_the_booking_service_can_answer_whether_a_gateway_is_connected() -> None:
    app = _app()
    assert app.state.booking_service._gateway_credentials is app.state.gateway_credential_service


def test_the_two_deposit_paths_share_ONE_gateway_service() -> None:
    """The disclosure a customer reads and the flow she then enters must not
    disagree about whether money is owed — `deposit_due`'s own docstring says so.
    Two different instances could answer differently after a connect or a revoke.
    """
    app = _app()
    assert (
        app.state.storefront_service._gateway_credentials
        is app.state.booking_service._gateway_credentials
    )


def test_the_waitlist_claim_shares_it_too() -> None:
    """F23's claim rides the same deposit branch and was the ONE caller wired
    correctly, because it is constructed after the payments block on purpose. It
    is asserted here so a future reordering cannot quietly unwire it instead."""
    app = _app()
    assert (
        app.state.waitlist_offer_service._gateway_credentials
        is app.state.gateway_credential_service
    )
