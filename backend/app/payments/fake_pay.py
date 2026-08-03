"""The dev-only hosted page the fake gateway redirects to (D21).

**F18 DELETES THIS FILE** when a real adapter's hosted page replaces it — the
route, the service, `register_fake_pay`, its call in `main.py`, and
`tests/test_fake_pay.py`. Nothing outside this module imports it.

It is not a nicety. `FakeGateway.create_session` returns
`FAKE_PAY_PATH?session={id}` and `FakeGateway` never posts a webhook to
anything, so without a page at that path every staging deposit redirects to a
404, sits on the awaiting-payment screen, and is expired and cancelled by
`DepositSweeper` one tick later — the exact inverse of the flow it is meant to
demonstrate, and invisible to F21's UAT.

**The production guard is `Settings`'s, reused rather than restated.**
`_forbid_fake_payment_paths_in_production` already boot-fails
`payment_provider="fake"` under `APP_ENV=production`, so "the fake gateway is
the configured provider" IS "this is not production". A second `app_env` check
here would be a second notion of production that could drift from the one that
boot-fails; `register_fake_pay` therefore consults `payment_provider` alone, and
when it is anything else the route is not registered AT ALL rather than
registered and refusing.

**The secret is read the way the verification path reads it and is never
rendered.** `verification_credentials_for` is the one credential read for
webhook material (D20), so a decrypted secret exists here for exactly as long as
it takes to HMAC two bodies. What reaches the browser is the two signed bodies
and their signatures — never the key that produced them.
"""

import dataclasses
import html
import uuid
from typing import Annotated

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.repositories.payments import PaymentsRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.payments.base import GatewayNotConfiguredError
from app.payments.fake import (
    # Private on purpose and imported anyway: `verify_webhook` reads the secret
    # under exactly this key, and a second literal here would silently sign with
    # "" the day the fake's credential shape changes.
    _WEBHOOK_SECRET_FIELD,
    FAKE_PROVIDER,
    fake_webhook_body,
    sign_fake_webhook,
)
from app.payments.service import GatewayCredentialService
from app.payments.validation import FAKE_PAY_PATH
from app.payments.webhook_router import MAX_SESSION_ID_LENGTH, SIGNATURE_HEADER
from app.tenancy.middleware import get_current_tenant

# The route IS the fake gateway's redirect target — imported, never retyped, so
# the page cannot end up at a path `create_session` does not send her to.
WEBHOOK_ROUTE = "/storefront/payments/webhook"


@dataclasses.dataclass(frozen=True)
class FakePayFacts:
    """Everything the page needs and nothing else. The amount is the payment
    row's OWN amount because `settle_from_webhook` 400s on a mismatch — a
    harness that guessed it would demo the mismatch branch instead of the
    settlement one."""

    amount_agorot: int
    webhook_secret: str


class FakePayService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        credentials: GatewayCredentialService,
    ) -> None:
        self._session_factory = session_factory
        self._credentials = credentials
        self._payments = PaymentsRepository()

    async def facts(self, tenant_id: uuid.UUID, *, session_id: str) -> FakePayFacts:
        provider = self._credentials.gateway.provider
        if provider is None:
            raise GatewayNotConfiguredError
        async with tenant_session(self._session_factory, tenant_id) as session:
            payment = await self._payments.by_provider_session_id(
                session, tenant_id, provider=provider, session_id=session_id
            )
        if payment is None:
            raise DomainNotFoundError("no payment for that session")
        credentials = await self._credentials.verification_credentials_for(tenant_id)
        return FakePayFacts(
            amount_agorot=payment.amount_agorot,
            webhook_secret=credentials.fields.get(_WEBHOOK_SECRET_FIELD, ""),
        )


def _button(label: str, *, outcome: str, body: bytes, signature: str) -> str:
    """The payload rides in ATTRIBUTES, not in the script body: the session id is
    query-string input, and inside a `<script>` a crafted one could close the
    element. `html.escape(quote=True)` is what makes an attribute safe."""
    return (
        f'<button data-outcome="{outcome}" '
        f'data-body="{html.escape(body.decode(), quote=True)}" '
        f'data-signature="{signature}">{label}</button>'
    )


def _page(*, session_id: str, facts: FakePayFacts) -> str:
    buttons = ""
    for outcome, label in (("pay", "Pay"), ("decline", "Decline")):
        body = fake_webhook_body(
            provider_session_id=session_id,
            # Distinct per outcome: `settle_from_webhook` short-circuits on a
            # transaction id it has already settled, so one shared id would make
            # "decline, then pay" a silent no-op — the likeliest click order in
            # a demo.
            provider_transaction_id=f"{session_id}-{outcome}",
            amount_agorot=facts.amount_agorot,
            paid=outcome == "pay",
        )
        buttons += _button(
            label,
            outcome=outcome,
            body=body,
            signature=sign_fake_webhook(webhook_secret=facts.webhook_secret, body=body),
        )
    return (
        "<!doctype html><meta charset=utf-8><title>Fake gateway</title>"
        f"<h1>Fake gateway</h1><p>Session {html.escape(session_id)} — "
        f"{facts.amount_agorot} agorot</p>{buttons}<pre id=out></pre>"
        "<script>document.querySelectorAll('button').forEach(b=>b.onclick=async()=>{"
        f"const r=await fetch({WEBHOOK_ROUTE!r},{{method:'POST',"
        f"headers:{{{SIGNATURE_HEADER!r}:b.dataset.signature}},body:b.dataset.body}});"
        "document.getElementById('out').textContent=r.status+' '+await r.text();});</script>"
    )


router = APIRouter()


@router.get(FAKE_PAY_PATH, response_class=HTMLResponse, include_in_schema=False)
async def fake_pay(
    request: Request,
    session: Annotated[str, Query(min_length=1, max_length=MAX_SESSION_ID_LENGTH)],
) -> HTMLResponse:
    tenant = get_current_tenant(request)
    service: FakePayService = request.app.state.fake_pay_service
    facts = await service.facts(tenant.id, session_id=session)
    return HTMLResponse(
        _page(session_id=session, facts=facts),
        # The embedded signatures describe one payment at one moment; a bfcache
        # replay after settlement would demo a redelivery nobody asked for.
        headers={"cache-control": "no-store"},
    )


def register_fake_pay(app: FastAPI, settings: Settings) -> None:
    """Call BEFORE `_register_spas`, which must stay last — the storefront
    catch-all claims `/{path:path}` and would otherwise answer `/fake-pay` with
    the SPA shell and a 200."""
    if settings.payment_provider != FAKE_PROVIDER:
        return
    app.include_router(router)
