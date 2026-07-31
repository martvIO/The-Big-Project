# Spec: Feature 18 — Lemon Squeezy payment adapter (TEST MODE ONLY)

**Created**: 2026-07-31 · **Status**: Gate 1 pre-authorized by the user (2026-07-31) — the material decisions were ruled when LS was chosen; this spec records them and builds · **Epic**: E4 · **Effort**: **M**
**Depends on**: F17 (the `PaymentGateway` port, `SecretBox`, migration 0012, the credential service) · **Feeds**: F19 (deposit flow), F29 (refund automation — LS test mode has a refunds API, which is what unblocked it)

---

## Problem

F17 shipped the port and a `FakeGateway`. The fake proves the *shape* — it does real HMAC and mints fake sessions — but it never crosses a network, so nothing in the repo has been exercised against a provider that returns unexpected JSON, rate-limits, or signs a webhook with its own scheme. F19 is about to build the deposit flow on top of this seam, and it should be built against something real.

The user supplied working Lemon Squeezy credentials on 2026-07-31 and ruled LS **test mode** the engine for E4.

## The bound that is not negotiable

**LS is merchant-of-record. It can never carry a boutique's deposit money.**

The deposit is legally the boutique's: `architecture.md:13` locks per-tenant merchant accounts, `e10-scale-polish.md:86` explicitly forbids platform collection of boutique deposits, and the boutique owes the Israeli receipt (קבלה/חשבונית). An MoR provider makes MODRYN the seller of the bride's transaction — a different business, and against LS's own terms, which cover software and digital goods rather than third-party appointment deposits.

So this adapter is a **development engine**: it exercises the port over a real network with a real signature scheme while the production Israeli PSP decision stays open (`external-applications.md` row 3). Three guards keep it from becoming anything else:

1. `APP_ENV=production` + `payment_provider="lemonsqueezy"` is a **boot failure**, exactly like the fake gateway's guard.
2. Migration 0013 widens 0012's CHECK to `('fake','lemonsqueezy')` and no further.
3. Every checkout this adapter creates sets `test_mode: true` explicitly, and the adapter **refuses to run** if it ever receives a non-test checkout back.

## Ground truth from the live API (verified 2026-07-31, not from documentation)

The LS docs return 403 to automated fetches, so the account was queried directly with the supplied key. What is actually true:

| Fact | Value |
|---|---|
| Auth | `Authorization: Bearer <key>`, `Accept: application/vnd.api+json` — works, returns JSON:API |
| Account | Maroun Issa · issamaroun07@gmail.com |
| Store `287880` | name `دعوة Dawa`, slug `automationscript`, **country IL, currency ILS**, plan `free` |
| Other store | `287879` `AutomationScripts` — not ours |
| Existing products | `DAWA PRODUCT` (published, 150000), `Reddit Video Generator` (draft) |
| Existing variants | 4, priced 5000–200000, belonging to the user's other business |
| Response envelope | `{meta:{page:{...}}, jsonapi:{version}, links:{...}, data:[{type,id,attributes,relationships}]}` |

**The design constraint this exposes.** LS's checkout API is a *product-catalog* checkout: it requires a `variant_id`. F17's port is amount-driven — `create_session(amount_agorot, reference, return_url, expires_in)` — because a deposit is an arbitrary sum that varies per boutique and per appointment type. The two do not line up natively.

The mechanism that bridges them is `checkout_data.custom_price` (integer, minor units), which overrides the variant's price. So the adapter needs **one dedicated placeholder variant** whose price is never used, and every checkout overrides it. That variant id becomes a credential field (`variant_id`), alongside `store_id` and `api_key`, declared through `credential_fields` — which is exactly what D5's adapter-declared credential shape was built for, and it means **no frontend change**: the console form renders from whatever the adapter declares.

Webhook verification (confirmed by the vendor's signing-requests documentation and corroborated across implementations): the `X-Signature` header carries an **HMAC-SHA256 hex digest of the raw request body**, keyed by the webhook signing secret. Raw bytes, not re-serialized JSON — F17's port already passes `body: bytes` for this reason, and `hmac.compare_digest` is already the house comparison.

## Design

`app/payments/lemonsqueezy.py`, one class implementing the F17 protocol. Nothing else changes shape.

- `provider` → `"lemonsqueezy"`; `credential_fields` → `frozenset({"api_key", "store_id", "variant_id", "webhook_secret"})`.
- `validate_credentials` → authenticated `GET /v1/stores/{store_id}`; a 401/404 raises `GatewayCredentialsRejectedError` (400 to the owner), a 5xx or timeout raises `GatewayUnavailableError` (503). **The distinction is the whole point** — "your key is wrong" and "LS is down" must not look the same to a boutique owner.
- `create_session` → `POST /v1/checkouts` with the JSON:API envelope: `data.type="checkouts"`, `attributes.checkout_data.custom_price = amount_agorot`, `attributes.checkout_options`, `attributes.custom_price`… plus `test_mode: true`, `attributes.checkout_data.custom = {"reference": reference}` to carry F17's opaque reference, and relationships to `store` and `variant`. Returns `PaymentSession(provider_session_id=data.id, redirect_url=data.attributes.url)`.
- `verify_webhook` → `hmac.new(secret, body, sha256).hexdigest()` vs the `X-Signature` header via `compare_digest`; on mismatch raise `GatewayWebhookInvalidError` (**400, never 503** — D25). Then parse `meta.event_name`, and read the reference back out of `meta.custom_data` / the order's `first_order_item`. Maps to `WebhookEvent(provider_session_id, provider_transaction_id, amount_agorot, paid)`.

`amount_agorot` maps 1:1 to LS minor units because the store's currency is **ILS** — verified above, not assumed. An adapter used against a non-ILS store would be silently wrong, so `validate_credentials` **must assert the store's currency is ILS** and reject otherwise.

## Non-goals

- **No live-mode support.** Guard 1 above.
- **No refunds.** F29's, and it now has an API to build against.
- **No subscription/recurring anything.** A deposit is one-shot.
- **No store or variant provisioning.** The placeholder variant is created by hand in the LS dashboard and its id typed into the console like any other credential.

## Tests

Fast, no network — an injected transport, exactly as F54's Twilio adapter does:
- `credential_fields` is the declared set; `provider` is `"lemonsqueezy"`.
- `validate_credentials`: 200 + ILS store → passes; 401 → `GatewayCredentialsRejectedError`; 500/timeout → `GatewayUnavailableError`; **200 with a non-ILS store → rejected**.
- `create_session` posts the JSON:API envelope with `test_mode: true`, `custom_price == amount_agorot`, the reference in `custom`, and returns the id + url from the response.
- **A response with `test_mode: false` raises** — the guard that keeps a mis-toggled store from taking real money.
- `verify_webhook`: a body signed with the secret verifies; a tampered body, a truncated signature, a wrong secret and a missing header each raise `GatewayWebhookInvalidError`; the digest comparison is `compare_digest` (asserted structurally).
- No credential, no signature and no raw provider body reaches any exception message or log line — the F54 scrub discipline, re-asserted here.

db-marked: migration 0013 round-trips and the widened CHECK admits `'lemonsqueezy'` while still rejecting anything else.

**Live proof is deliberately NOT in this feature's gates** — see Risks.

## Risks

1. **The supplied store belongs to another business.** `دعوة Dawa` (slug `automationscript`) already sells `DAWA PRODUCT`. Pointing MODRYN's deposit checkouts at it mixes two businesses under one MoR account, and a bride's LS receipt would carry that store's name. Fine for a development engine; it is one more reason this can never be the production path. **Flagged to the user.**
2. **Test mode could not be verified from the API.** The store record exposes no test-mode flag, and creating a checkout to find out would risk minting a *live* one against a real store. So this spec builds entirely against an injected transport, and the live end-to-end proof is parked until the user confirms Test Mode is toggled on in the LS dashboard. The `test_mode: false` rejection test is the belt-and-braces.
3. **`free` plan limits** may throttle or cap checkouts; unknown until exercised. Surfaces as `GatewayUnavailableError`, which the console renders as "temporarily unavailable" — the correct behaviour either way.
4. **LS may change its JSON:API shapes.** The adapter reads only `data.id`, `data.attributes.url`, `meta.event_name` and the custom payload; each is asserted in a test, so a shape change fails loudly rather than silently mis-parsing.
