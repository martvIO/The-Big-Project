# Spec: Feature 11 — SMS Foundation (Epic E3)

**Created**: 2026-07-28 · **Status**: draft — awaiting Gate 1 · **Epic**: E3 Feature 11 (first E3 feature) · **Effort**: M
**Depends on**: E1 #2 (provider decision groundwork, Railway env), E1 #3 (auth primitives this reuses: `FixedWindowRateLimiter`, `tokens.py`) — branches off `main` · **Feeds**: E3 #13 (booking creates customers only after OTP verification), E3 #16 (every lifecycle send goes through this port), E5 (client login reuses the OTP primitive)

## Problem

E3 turns the storefront into a surface that takes real bookings, and the entire customer control loop runs over SMS: the OTP that proves phone possession before a booking exists, the confirmation with the tokenized manage link, the 24h reminder, the owner-change notifications. None of it can be built feature-by-feature against a provider SDK scattered through services — the Spam-Law evidence trail (what was sent, to whom, when, with what outcome) must be structural, the provider must be swappable (the sender-ID registration is not even filed yet), and dev/CI/staging must run the whole lifecycle without a provider account existing.

So F11 is three things, none of them UI: a **NotificationService port** with the same adapter discipline as `app/storage/` (fake for dev/test, unconfigured degrading to 503, real adapter when the account exists), a **tenant-scoped `message_log`** written above the port so no adapter can skip it, and the **OTP send/verify primitive** — rate-limited, ≤5-minute expiry, single-use, attempt-capped — whose output is a short-lived `verification_token` that F13 will exchange for a customer record.

## Goal

A dev with zero SMS credentials runs the fast suite and sees a `FakeSmsSender` outbox capture an OTP send; the db suite proves the code expires at 5 minutes, burns after one use, locks after 5 wrong guesses, and that a second tenant can never read the first tenant's `message_log`. On staging (fake sender + `OTP_DEV_CODE`), `POST /storefront/otp/send` + `/verify` round-trips a verification token. In production with no provider configured, OTP send answers `503 SMS_NOT_CONFIGURED` — bookings are structurally gated on the sender-ID registration the user owns, and nothing 500s.

## Design

### Data (migration 0007)

Two tables, both `_STANDARD` + `GRANT SELECT, INSERT, UPDATE, DELETE TO app_user` + `enable_tenant_rls`, following `0005_boutique_settings.py` to the letter.

```sql
CREATE TABLE message_log (
    {_STANDARD},
    phone TEXT NOT NULL,                    -- E.164, normalized by validation
    kind TEXT NOT NULL CHECK (kind IN
        ('otp','confirmation','reminder','owner_cancel','owner_reschedule')),
    body TEXT NOT NULL,                     -- rendered body; OTP codes MASKED (see below)
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','failed')),
    provider_message_id TEXT,
    error TEXT,                             -- provider failure detail, never user-facing
    booking_id UUID                         -- nullable; no FK (house rule); F16 populates
);
CREATE INDEX idx_message_log_tenant_created
    ON message_log (tenant_id, created_at) WHERE deleted_at IS NULL;

CREATE TABLE otp_codes (
    {_STANDARD},
    phone TEXT NOT NULL,                    -- E.164
    code_hash TEXT NOT NULL,                -- sha256; hygiene, not a boundary (see below)
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 50),
    consumed_at TIMESTAMPTZ,
    verification_token_hash TEXT,           -- set on successful verify
    verification_expires_at TIMESTAMPTZ,
    verification_consumed_at TIMESTAMPTZ    -- F13 sets when the booking is created
);
CREATE INDEX idx_otp_codes_tenant_phone_active
    ON otp_codes (tenant_id, phone) WHERE consumed_at IS NULL AND deleted_at IS NULL;
```

- **`attempts` CHECK at 50 = 10× the service cap of 5** — the absurdity-ceiling convention from 0005: the DB bound exists to stop a broken write path, not to encode policy.
- **OTP hashing is hygiene, not a security boundary.** A 6-digit code has ~20 bits of entropy; sha256 does not make it uncrackable offline. The real controls are the attempt cap (5 per code), the verify budget, the 5-minute expiry, and the send rate limits. The hash's job is only that a DB read never shows a live code. Same reasoning applies to **masking the code in `message_log.body`** (`"קוד האימות שלך: ●●●●●●"`): the log is forever, the code is worthless in 5 minutes, and the Spam-Law evidence value is "an OTP was sent to this phone at this time", not the digits.
- **The masking has to hold on the failure path too.** Several SMS SDKs quote the failing request — body included — in their exception, so a raw `str(exc)` in `message_log.error` would write the unmasked code next to the masked one. Provider errors are truncated to 200 chars and any echo of the wire body is replaced with what the caller chose to retain. For the same reason the fake adapter does **not** log the body: staging runs it on a publicly reachable host whose log stream is widely readable, and an INFO line carrying the live code would hand verification to anyone with log access.
- **`verification_token_hash` lives on the otp row, not a new table** — one verify mints one token; the row already carries the phone, tenant and audit timestamps. F13 marks `verification_consumed_at` when it creates the booking, so a token is single-use by column, not by convention. All three verification columns ship now so F13's migration (0008) never touches this table.
- `message_log` gets full CRUD grants (status transitions update it), unlike `terms_versions` — it is operational telemetry with a compliance duty, not immutable financial evidence. Soft-delete discipline still applies; nothing ever hard-deletes.

### Module: `app/notifications/`

One module, mirroring `app/storage/` + the router/service/schemas/validation shape every feature uses:

| File | Contents |
|---|---|
| `base.py` | `SmsSender` Protocol: `async def send(*, phone: str, body: str) -> SendResult` (`SendResult` frozen dataclass: `provider_message_id: str \| None`); `SmsNotConfiguredError`; `SmsSendError` (carries no provider text — original is logged) |
| `fake.py` | `FakeSmsSender` — appends `(phone, body)` to an in-memory `outbox: list[SentSms]`, logs one INFO line, returns a fabricated message id. Dev + tests + staging until the real adapter lands |
| `unconfigured.py` | `UnconfiguredSmsSender` — `send` raises `SmsNotConfiguredError`; `is_configured = False`. The 503 degradation twin of `UnconfiguredMediaStorage` |
| `service.py` | `NotificationService` (the port wrapper that owns `message_log`: insert `queued` → adapter send → update `sent`/`failed` + `provider_message_id`/`error`, one `tenant_session` per phase so a provider hang never holds a transaction open) and `OtpService` (send/verify/consume, below) |
| `router.py` | the two public POSTs |
| `schemas.py` | `OtpSendRequest`, `OtpVerifyRequest`, `OtpVerifyResponse` |
| `validation.py` | phone normalization + every named constant |

Models `app/models/message_log.py`, `app/models/otp_code.py`; repositories `app/db/repositories/message_log.py`, `app/db/repositories/otp_codes.py` — stateless, session-first, explicit `tenant_id` predicate, house naming (`insert`, `update_status`, `latest_active_by_phone`, `by_verification_token_hash`).

**The adapter never sees the database and the repositories never see the adapter.** `NotificationService.send_sms(tenant_id, phone, body, *, kind, booking_id=None)` is the only path that writes `message_log`, so the evidence trail cannot be skipped by a future adapter or a future caller — F16's scheduler calls this same method.

### OTP flow (the F13 contract, fixed here)

```
POST /storefront/otp/send   {phone}        → 204
POST /storefront/otp/verify {phone, code}  → 200 {verification_token, expires_at}
```

- **send**: normalize phone → rate-limit gates (below) → invalidate any active code for (tenant, phone) (soft-delete; one live code per phone) → generate 6-digit code (`secrets.randbelow(1_000_000)`, zero-padded) → store hash, `expires_at = now + 5min` → `NotificationService.send_sms(kind="otp")`. Returns 204 whether or not the phone has ever been seen — there is nothing to enumerate.
- **verify**: fetch the single active row for (tenant, phone). No row → `OTP_INVALID`. Increment `attempts` **before** comparing (a crash between compare and increment must not grant a free guess); over the cap of 5 → `OTP_INVALID` (indistinguishable from a wrong code — an attacker learns nothing about why they failed). Compare `sha256(code)` via `secrets.compare_digest`. Expired → `OTP_EXPIRED` (distinguished deliberately: "request a new code" is real UX, and expiry reveals nothing an attacker doesn't know from the timestamp of their own send). Success → set `consumed_at`, mint `verification_token` (`generate_session_token()`, 256-bit), store `hash_token(token)` + `verification_expires_at = now + 10min`, return the token once. It is never derivable again.
- **consume** (service method, no route — F13 calls it inside the booking transaction): `consume_verification(session, tenant_id, phone, token) -> bool` — hash, match against an unconsumed, unexpired verification for that exact phone, set `verification_consumed_at`. Session-taking by design so the booking INSERT and the consumption commit or roll back together.
- **`OTP_DEV_CODE`**: when `settings.otp_dev_code` is set, `verify` also accepts that exact code (send still runs the full path — fake outbox, message_log, rate limits, so staging exercises everything). A `model_validator` makes the setting a **boot failure in production**, and the fake sender is likewise forbidden in production — the two lines that make "staging convenience" incapable of becoming "production hole".

### Rate limits (all `Settings` fields, all `FixedWindowRateLimiter` on `app.state`)

| Key | Default | What it protects | On exhaustion |
|---|---|---|---|
| `otp:phone:{tenant}:{phone}` | 5 / 3600s | SMS cost + bombardment of one victim's phone | **204, no SMS** (see below) |
| `otp:tenant:{tenant_id}` | 100 / 3600s | the tenant's SMS bill — a runaway brake like the storefront read budget, sized ~10× expected pilot peak | 429 |
| `otp:verify:{tenant}:{phone}` | 10 / 300s | brute force *across* codes, and the unauthenticated SELECT+locking-UPDATE per call | 429 |
| verify attempts | 5 per code (column-tracked, not limiter) | brute force *within* one code | 400 `OTP_INVALID` |

**The two send budgets answer differently, deliberately.** A tripped tenant ceiling is an operational fact about the boutique and 429s. A tripped per-phone budget is a fact about one person: answering 429 would make this endpoint an oracle for "is this number mid-booking at this boutique", on a surface whose entire posture is that known and unknown phones are indistinguishable. It therefore returns the same 204 and sends nothing.

**Verify needs its own budget, and the attempt cap is not a substitute.** The column cap burns one code; without a verify limiter an attacker simply requests a fresh code and keeps guessing — 10⁶ space, 300s TTL, no auth.

Per-IP keying is deliberately absent for the same documented reason as `_throttle` in `app/storefront/router.py`: behind an untrusted proxy the IP is the proxy, and `trust_forwarded_for` remains unresolved until F21. Per-phone is the control that matters — it is the resource being spent. All limiter checks record on the **attempt** path (success or failure), because the resource is the attempt itself.

**The attempt cap only works if the increment survives the failure.** `tenant_session` is `session.begin()`, so a `raise` inside the block rolls the transaction back — and would take the `attempts = attempts + 1` write with it, leaving the counter at 0 forever and the cap inert. `verify()` therefore **decides inside the transaction and raises outside it**. Once the cap is reached it also stops *writing*, not merely stops answering: the column's `CHECK (attempts <= 50)` is a defensive ceiling the service must keep unreachable, and incrementing forever would turn it into an `IntegrityError` 500 on an anonymous endpoint. Both properties have dedicated regression tests that read the persisted column, because a purely behavioural cap test passes either way.

### Router posture

New `APIRouter(prefix="/storefront")` in `app/notifications/router.py` — the existing storefront router is contractually GET-only (its own docstring), so the mutating OTP routes get a sibling router on the same prefix, registered after it in `create_app()`. The route table in `test_storefront_api.py` gains both routes and mechanically asserts: no `Staff` dependency, no cookie reads (byte-identical response with a valid owner cookie attached), not in `EXEMPT_PATHS`, `cache-control: no-store` (the verify response carries a bearer token; the send response carries nothing but must not differ).

**CSRF: structurally N/A, stated here once.** These endpoints read no cookie and no ambient credential — there is nothing a cross-site attacker can ride. `CsrfOriginMiddleware.PROTECTED_PREFIX` stays `/manage`, and the controls that matter are tenant-from-Host, the rate limits above, and OTP possession itself. The cookie-blindness test is what keeps this claim true forever.

### Errors (house shape, fixed bodies in `main.py`)

| Error | Status | Code |
|---|---|---|
| `SmsNotConfiguredError` | 503 | `SMS_NOT_CONFIGURED` — "Phone verification is not available." |
| `SmsSendError` | 503 | `SMS_UNAVAILABLE` — "Could not send the verification code. Try again." |
| `OtpInvalidError` | 400 | `OTP_INVALID` — "The code is incorrect." |
| `OtpExpiredError` | 400 | `OTP_EXPIRED` — "The code expired. Request a new one." |
| `OtpThrottledError` | 429 | `TOO_MANY_ATTEMPTS` (existing body) |
| invalid phone | 400 | `VALIDATION_ERROR` (existing handler) |

### Named constants (`app/notifications/validation.py`)

| Constant | Value | Why |
|---|---|---|
| `OTP_CODE_LENGTH` | 6 | industry floor; the attempt cap is what carries the entropy math |
| `OTP_TTL_SECONDS` | 300 | epic requirement (≤5 min) |
| `OTP_MAX_VERIFY_ATTEMPTS` | 5 | 5/10⁶ ≈ 0.0005% brute-force success per code |
| `VERIFICATION_TOKEN_TTL_SECONDS` | 600 | long enough to finish the booking form, short enough that an abandoned token dies before the slot picker goes stale |

Phone normalization (`normalize_israeli_mobile`): accept `05X-…`/`+9725X…`/`9725X…` in the charset `0123456789 ()-+`, normalize to `+9725XXXXXXXX`, reject everything else with `VALIDATION_ERROR`. Israeli mobiles only, deliberately: the pilot is Israeli, the SMS route is Israeli, and a wrong-country send is pure cost. The rule lives here once; F13/F14 reuse it. Mirrors the `waPhone` derivation precedent from F10 (`apps/storefront/src/lib/contact.ts`).

### Config (`Settings`)

```python
sms_provider: Literal["fake"] | None = None   # real provider literal added with its adapter
otp_dev_code: str | None = None
otp_send_max_per_phone_window: int = 5
otp_send_phone_window_seconds: int = 3600
otp_send_max_per_tenant_window: int = 100
otp_send_tenant_window_seconds: int = 3600
```

Validators: `sms_provider == "fake"` and `otp_dev_code` are both boot failures in production. `None` → `UnconfiguredSmsSender` in every environment (the media-bucket precedent: absence is a supported deployment that answers 503, never a crash). Dev/.env sets `SMS_PROVIDER=fake`; tests construct `FakeSmsSender` directly.

### Provider comparison & recommendation (research pass, 2026-07-28)

| Criterion | Twilio | InforU | 019 (Telzar) |
|---|---|---|---|
| Sender-ID viability (+972) & lead time | Registered domestic alphanumeric sender required; **~1 week**; Twilio files with the Israeli operators | Sender-name feature exists; process & lead time unconfirmed | Alphanumeric `source` (11 chars) as free per-message field; formal approval unconfirmed |
| Per-SMS price to +972 | **$0.2575/segment** (Hebrew = UCS-2, 70 chars/segment); Verify ≈ $0.31 | Not published; sales-mediated, subscription plans | Not published; market ~2–4.5 agorot/SMS, prepaid bundles, sales call |
| API quality (Python) | REST + official SDK, **test credentials + magic numbers** | JSON REST, Hebrew-first docs, no SDK | Single JSON endpoint, English docs, plain `requests` |
| Delivery reporting | Push webhooks (`StatusCallback`) | Claimed handset DLR; webhook spec unconfirmed | Pull-only DLR (7-day window), no webhooks |
| OTP fit | Verify is turnkey incl. SMS-pumping Fraud Guard (we still roll our own — the primitive must also serve E5 login and stay provider-portable) | OTP product exists, shape unconfirmed | Real generate-and-verify API |
| Signup friction | Fully self-serve; sender registration is the only gate | Sales-driven | Trial self-serve; API account sales-mediated |

**Recommendation: Twilio for the pilot.** It is the only option where every load-bearing fact is verified today — published pricing, a documented Israel sender-ID path, webhooks, self-serve signup, and test credentials that let the adapter be built and CI-tested without spending a shekel or waiting on a sales call. The ~25× per-SMS premium over local rates is immaterial at pilot volume (≈$30–80/month); the thin port makes switching a one-adapter job. **Runner-up: 019**, which wins at roughly >2,000–3,000 messages/month (≈$500+ vs ≈$30) *if* a sales call confirms near-market pricing and a workable alphanumeric sender.

**User actions (start immediately — this is the pilot's launch gate):** create a Twilio account, upgrade off trial (trial cannot use alphanumeric senders), submit the Israel alphanumeric sender-ID registration (Console → Messaging → Senders), with: brand sender ID ≤11 chars (Latin letters/digits, no generic INFO/SMS), legal business name + address, use-case "transactional: OTP verification, booking confirmations, appointment reminders", 2–3 sample Hebrew bodies, est. volume ~200–500/month. Lead time ~1 week. Verify during signup: any Israel registration fee; whether an Israeli business number is required; that one registration covers all four MNOs.

**Two operational notes the research surfaced, recorded for F16:** (a) no primary statutory text confirms the Amendment 40 transactional exemption — it rests on the "advertising material" definition plus uniform practitioner commentary, so templates stay strictly non-promotional and get a one-line counsel sign-off; (b) "kosher" phones block all commercial SMS including transactional — the booking flow must tolerate OTP delivery failure (the owner-side remedy path in F15 is the fallback; a voice channel is explicitly out of scope for v1).

The port above is provider-agnostic by construction; nothing in F11–F16 blocks on this decision. The Twilio adapter itself is **out of scope for F11** — it lands as its own small commit once the account and registered sender exist.

## Frontend changes

None. F11 is backend-only; F14 builds the OTP step UI against the contract fixed above.

## Testing

Fast suite (no marker): phone normalization table (formats, rejects), OTP code generation shape, `FakeSmsSender` outbox, masked-body rendering, limiter window math with injected clock.
`db`-marked: repo round-trips + RLS isolation for both tables (mirror `test_catalog_isolation.py` — a second tenant reads zero rows); full OTP lifecycle (send→verify→token); expiry with injected clock; single-use (second verify of the same code fails); attempt cap (5 wrong then the right code still fails); one-live-code (resend invalidates predecessor); `consume_verification` single-use + wrong-phone miss; `message_log` status transitions queued→sent and queued→failed (adapter raising); dev-code acceptance and its production boot failure; migration 0007 up/down round-trip.
API: route-table additions (auth-guard reverse, cookie-blindness, no-store), error bodies, 204 semantics, 429 on both limiter keys.

Expect the first CI run to surface something in the db-marked set that never ran locally — budget one fix commit, per house experience.

## Out of scope

Real provider adapter (lands as its own small commit once the account + sender ID exist — the port is its contract), booking creation (F13), lifecycle sends and scheduling (F16), any UI (F14), Redis-backed distributed rate limiting (F21).

## Risks

1. **Sender-ID registration lead time** — user-owned, multi-week, gates the pilot. Mitigated by filing immediately after Gate 1 approves the recommendation; tracked in `.planning/external-applications.md` row 4.
2. **In-process rate limiters reset on deploy** and don't aggregate across replicas — accepted single-instance pilot posture, same as login and presign throttles; F21 owns the upgrade.
3. **SMS cost abuse via the public send endpoint** — bounded by per-phone and per-tenant windows; until a real adapter exists the blast radius is zero (fake/unconfigured). **Re-derive both numbers at provider cutover against real per-SMS cost**: at the Twilio quote above, the current tenant ceiling is ~$25/hour of attacker-directed spend, and exhausting it also 429s real customers for the rest of the window. The mitigations that need a decision then, not now: metering *new* phones separately from resends, a proof-of-work/Turnstile on send, and per-IP keying once `trust_forwarded_for` is settled (F21).
4. **`APP_ENV` defaults to `"dev"`**, so a production deployment that sets `DATABASE_URL` and `BASE_DOMAIN` but forgets `APP_ENV` would accept `OTP_DEV_CODE` and the fake sender (on top of the pre-existing insecure-cookie and open-docs consequences). Pre-existing platform shape, widened by F11; making `app_env` mandatory is a cross-cutting change owned by F21, flagged here because F11 is what raises the stakes.
