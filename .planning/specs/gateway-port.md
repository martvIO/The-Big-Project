# Spec: Feature 17 — Payment gateway port + credential management (Epic E4)

**Created**: 2026-07-30 · **Revised**: 2026-07-30 (adversarial review — 18 findings, 3 BLOCKER; see "Response to the adversarial review") · **Status**: **Gate 1 PENDING USER APPROVAL — F17 is on Interview Q1's stop-list (payments surface); 4 open questions below** · **Epic**: E4 (first E4 feature to build) · **Effort**: **M** (the epic sizes it S; revised at spec time — S was written when the feature was one credentials table, before Interview Q7 made the port and its fake adapter the deliverable and before the `payments` table entered scope)
**Depends on**: F7 (owner settings — `tenants.settings` JSONB, the atomic `merge_settings`, the `deposits_enabled` toggle), F31 (`require_role`, the default-deny walker this feature must satisfy), F11 (not a code dependency — the port shape this feature copies) · **Feeds**: F19 (deposit booking flow — every method here is one of its seams), F18 (the real Grow adapter drops in behind this port), F26 (invite-code signup's gateway-connect onboarding step)

---

## Problem

E4's entire deposit story is blocked on an external application nobody in this repo can file. The Grow (Meshulam) merchant account is `not-started` in `.planning/external-applications.md` row 3, it needs Israeli business registration plus bank documents, and it is named there as "the longest lead time left". Under the roadmap's original sequencing (F17 → F18 → F19, all three gated on that approval) the whole epic sits still, and the parts of it most likely to be *wrong* — the 15-minute slot hold racing a late webhook, the sweeper that frees an unpaid seat, the idempotency of a duplicate delivery — are precisely the parts that have nothing to do with Grow.

Interview Q7 rules that they get built now against a fake gateway, and names the precedent: this is the play F11 already ran for SMS. That decision is what this spec implements. It is the same shape, argued the same way, with one axis F11 did not have — **per-tenant secrets**. SMS has one platform sender; payments have a merchant account *per boutique* (external-applications #3: "the pilot boutique files its own"), which means credential material lands in a tenant-scoped table on our side and the security-checklist row that covers it (`Per-tenant gateway credentials KMS-encrypted; never logged`) is a ship-gate row, not a nice-to-have.

Nothing about payments exists in the backend today. `grep -rniE "payment|gateway|grow" Backend/app` returns only comments anticipating this feature. `tenants.settings.toggles.deposits_enabled` has shipped since F7 and has **zero readers** — `app/boutique/validation.py:58` validates it and nothing consumes it. `appointment_types.deposit_required` / `deposit_amount_agorot` ship with DB CHECKs (0005) and are already disclosed to anonymous visitors (`app/storefront/schemas.py:171-186`, whose docstring says "E4's payment step reads the same fields"). So the product already *promises* a deposit and has no machinery whatsoever to take one.

## Goal

A developer with no merchant account, no AWS credentials and no Docker runs the fast suite and watches a `FakeGateway` refuse a bad credential set, accept a good one, mint a payment session, and verify a real HMAC webhook signature. `PUT /manage/gateway/credentials` validates against the provider *before* storing, encrypts through a `SecretBox` port bound to the tenant, and stores a ciphertext the API can never read back. The owner console shows connected / not-connected / invalid with a last-validated timestamp, and warns when `deposits_enabled` is on with no gateway behind it. In production with no gateway configured, every gateway route answers `503 GATEWAY_NOT_CONFIGURED` and nothing 500s — and production *cannot* store a credential at all, because the fake secret box is a boot failure there and migration 0012's `provider` CHECK admits only `'fake'`. F19 then builds the deposit flow against `PaymentService.open_deposit` / `settle_from_webhook` without inventing a money table, and F18 drops a `GrowGateway` in behind an interface that already has tests.

## What already exists to build on (verified against code)

- **The port pattern, twice over.** `app/notifications/{base,fake,unconfigured,service}.py` and `app/storage/{base,memory,s3,unconfigured}.py` are the same play: a `Protocol` with an `is_configured` property, a recording fake, an "unconfigured" adapter that raises rather than returning a failure (`app/storage/unconfigured.py`: "Chosen over None so no call site grows a null check"), a service above the port that is the sole writer of the evidence table, and a `_build_*(settings)` function in `create_app()` that logs one INFO line so a typo'd env var is observable (`app/main.py:232-261`).
- **Two operationally distinct degradations, both 503, never 500.** `MediaNotConfiguredError`/`MediaStorageUnavailableError` and `SmsNotConfiguredError`/`SmsSendError` each get their own fixed body in `app/main.py:148-169`, and neither ever carries provider text. `NotificationService._scrub` (`service.py:140-147`) truncates provider exception text to `MAX_PROVIDER_ERROR_LENGTH = 200` before persisting it.
- **`require_role` and the default-deny walker.** `app/auth/dependencies.py:40-66` — a `RoleGate` carrying an introspectable `allowed_roles` frozenset, raising `NotAuthorizedError` → one generic 403 body (`main.py:105-107`). `tests/test_staff_role_gating.py` walks the live route table and fails the build for any `/manage` route without a gate; `OWNER_ONLY = {("POST", "/manage/terms")}` pins the narrowed set, and its comment already reserves the extension: "F51's staff router adds its rows here".
- **Migration house style.** `_STANDARD` block, `_updated_at_trigger(table)`, `GRANT … TO app_user`, `enable_tenant_rls(table)` (`app/db/rls.py`) — 0005 through 0011 verbatim. 0005 also carries the **append-only precedent**: `REVOKE ALL ON terms_versions FROM app_user` first (0002's `ALTER DEFAULT PRIVILEGES` auto-granted CRUD) then `GRANT SELECT, INSERT`.
- **Structural idempotency — a *two-layer* pattern, and reading it as one layer is how F17's first draft went wrong.** 0009's own comment states both halves: "The service converges that retry onto the existing row **under the per-tenant advisory lock**; this index is what makes a duplicate impossible even for a writer that skips the lock." Service-level convergence is the mechanism, the partial unique index is the backstop. `create_booking` (`app/booking/service.py:262`) shows the whole sequence — `pg_advisory_xact_lock(hashtext(tenant_id))`, read, converge, write, and `except IntegrityError → raise SlotUnavailableError` for the lost race — and it returns `BookingClaim(booking, created=…)` so the caller can tell a fresh write from a converged one and skip the SMS. `ScheduledMessageRepository.mark` (0010) adds the third tool: an UPDATE guarded on `status='pending'` that returns `None` rather than firing twice. D23 and D24 reuse all three verbatim.
- **The mechanical RLS sweep.** `tests/test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls` queries `pg_class`/`pg_attribute` for any table with a `tenant_id` column and no `relforcerowsecurity`. Two new tenant tables are picked up with **no test edit** — that is the whole point of it.
- **Audit log needs no migration.** `audit_log.action` is plain TEXT with no CHECK (0003) — `app/models/constants.py:85-88` states this explicitly for `AuditAction`. `AuditLogRepository.record(session, …)` is session-taking, so an audit row commits with the write it describes.
- **boto3 is already a dependency** (`Backend/pyproject.toml`, for S3) and the AWS account is live: external-applications #1 is `approved`, `il-central-1` opt-status `ENABLED`, scoped IAM keys already wired into Railway. AWS KMS is therefore reachable with **zero new dependencies**.
- **No reversible encryption exists anywhere in the repo.** `app/auth/tokens.py` is sha256 (one-way), `app/auth/passwords.py` is argon2 (one-way), and `cryptography` is not a dependency. A credential we must hand back to a provider cannot be hashed, so this feature introduces the repo's first at-rest encryption seam. There is nothing to reuse; there is a pattern to obey.
- **Frontend**: `Frontend/apps/manage/src/App.tsx` holds a flat `SectionKey` union + a `nav` array fed to `ConsoleShell`; `Staff` already carries `role: string` (`api.ts:66-71`); `packages/ui` exports a fully generic `PolicyBlockerBanner({message, actionLabel, onAction})` — gold stripe on paper, deliberately not red — which is exactly the affordance the deposits-on-with-no-gateway warning needs. `i18n/ar.ts` exists and ships untranslated keys (Interview Q3 / pre-decided #47).

## Design

### Data (migration 0012)

Raw-SQL in the 0007/0008 house style. **Two tables. Neither touches `bookings`** — the `pending_payment` status widening is F19's, and `app/models/constants.py:48` plus F34's LOOP-STATE note both say so; touching the `status` CHECK here would silently claim scope this feature has no writer for.

`tenant_gateway_credentials` — the architecture's own name for it (`architecture.md:52`):

```sql
CREATE TABLE tenant_gateway_credentials (
    -- _STANDARD: id, tenant_id, created_at, updated_at, deleted_at
    provider          TEXT NOT NULL CHECK (provider IN ('fake')),   -- 'grow' joins with F18's migration
    ciphertext        TEXT NOT NULL,          -- base64 SecretBox blob; NEVER a plaintext field, NEVER logged
    key_ref           TEXT NOT NULL,          -- which box + key wrote it; a rotation must know what it is replacing
    status            TEXT NOT NULL DEFAULT 'valid'
                      CHECK (status IN ('valid', 'invalid')),
    last_validated_at TIMESTAMPTZ NOT NULL,   -- NOT NULL is the invariant, see below
    validation_error  TEXT,                   -- scrubbed + truncated provider detail; operators only
    created_by        UUID NOT NULL            -- staff_users.id; no FK (house rule)
);
CREATE UNIQUE INDEX idx_tenant_gateway_credentials_active_unique
    ON tenant_gateway_credentials (tenant_id, provider) WHERE deleted_at IS NULL;
-- D20's verification lookup: the newest row for (tenant, provider) REGARDLESS of
-- deleted_at and status. Not partial, deliberately — the whole point is that it
-- still resolves after a disconnect or an `invalid` flip.
CREATE INDEX idx_tenant_gateway_credentials_newest
    ON tenant_gateway_credentials (tenant_id, provider, created_at DESC);
```

- **`last_validated_at NOT NULL` and no `'unvalidated'` status are the same decision as D4.** Credentials are pinged before they are stored, so an unvalidated stored credential is not a state this schema can represent. That is stronger than a service-level rule and it is free.
- **`provider IN ('fake')` is a security control, not just the D9 no-speculative-values rule.** `payment_provider = "fake"` is a production boot failure (below), so in production this table can hold **no rows at all** until F18 widens the CHECK alongside a real adapter. The window in which real merchant credentials could be stored by a fake secret box does not exist.
- **`ciphertext`, never columns per field.** What Grow's credential set actually contains is unknown — we have no account and no documentation access. See D5.

`payments`:

```sql
CREATE TABLE payments (
    -- _STANDARD: id, tenant_id, created_at, updated_at, deleted_at
    booking_id              UUID NOT NULL,     -- no FK (house rule)
    provider                TEXT NOT NULL,     -- snapshot: which gateway took this money
    amount_agorot           INTEGER NOT NULL CHECK (amount_agorot > 0),
    status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','paid','failed','expired',
                                              'refund_due','refunded','forfeited')),
    provider_session_id     TEXT,              -- the hosted-page session F19 redirects to
    provider_transaction_id TEXT,              -- the webhook's identity; the replay key
    hold_expires_at         TIMESTAMPTZ,       -- F19's sweeper reads this
    paid_at                 TIMESTAMPTZ,
    error                   TEXT               -- scrubbed provider detail; never a response body
);
-- Webhook replay protection BACKSTOP, the 0009 argument read correctly: the
-- service converges a redelivery under the guarded UPDATE (D24) and this index
-- is what stops a writer that skips it. It is NOT the mechanism — on the settle
-- path there is no insert for it to refuse, only an update to one row.
CREATE UNIQUE INDEX idx_payments_provider_txn_unique
    ON payments (tenant_id, provider, provider_transaction_id)
    WHERE deleted_at IS NULL AND provider_transaction_id IS NOT NULL;
-- At most one live hold per booking (the idx_scheduled_messages_pending_unique trick).
CREATE UNIQUE INDEX idx_payments_booking_pending_unique
    ON payments (tenant_id, booking_id) WHERE deleted_at IS NULL AND status = 'pending';
CREATE INDEX idx_payments_tenant_booking
    ON payments (tenant_id, booking_id) WHERE deleted_at IS NULL;
-- F19's expiry sweeper: "pending holds whose clock has run out", per tenant.
CREATE INDEX idx_payments_hold_expiry
    ON payments (tenant_id, hold_expires_at) WHERE deleted_at IS NULL AND status = 'pending';
```

`amount_agorot` is a **snapshot**, not a read-through to `appointment_types.deposit_amount_agorot` — the owner can change the deposit at any time and the amount charged must render as what the customer agreed to, the same argument 0008 makes for `appointment_type_name`/`dress_name`. There is no `currency` column (D10) and no receipt columns (D11).

**Grants on both tables depart from the house default:**

```sql
REVOKE ALL ON tenant_gateway_credentials FROM app_user;   -- 0002's ALTER DEFAULT PRIVILEGES auto-granted CRUD
GRANT SELECT, INSERT, UPDATE ON tenant_gateway_credentials TO app_user;
REVOKE ALL ON payments FROM app_user;
GRANT SELECT, INSERT, UPDATE ON payments TO app_user;
```

DELETE is revoked on both (D7). `UPDATE` stays because soft-delete and every status transition need it, and unlike `terms_versions` these rows genuinely change. `SELECT` stays because both are read on the hot path — and note the consequence the SCHEMA gotcha warns about does *not* bite here: with SELECT granted, `INSERT … RETURNING` works, so no client-side id/timestamp generation is needed. Both tables get `_updated_at_trigger` and the standard `enable_tenant_rls` policy.

#### Retention and erasure (D21)

Pre-decided #10 fixes a retention period for OTP codes, sessions, the message log, bookings and scheduled messages. It names neither of these two tables, and F20 owns the retention job that has to sweep them — so F17 must state what F20 is expected to do rather than leave two new tables outside every data class.

**Revoked DELETE does not block erasure.** `UPDATE` is granted, and pre-decided #34 already establishes the repo's erasure shape for exactly this situation: "auto-erase personal fields … operational history retained permanently but de-identified". Erasure here is column blanking, not row removal — the row survives as the financial/rotation record, its personal and secret payload does not.

| Table | Class | What F20 blanks | What survives |
|---|---|---|---|
| `payments` | personal data, via `booking_id` → the customer | nothing on the row itself; the row is de-identified by `bookings`' own scrub, which F20 already owns | amounts, statuses, timestamps, provider ids — the financial record |
| `tenant_gateway_credentials` | **not** personal data — a business secret | `ciphertext`, `validation_error` on every **superseded** (`deleted_at IS NOT NULL`) row | `key_ref`, `status`, `created_by`, timestamps — the rotation trail D6 exists for |

The `payments` retention period is deliberately **not** set here: it is a bookkeeping-law number, not a house-style one, and it goes to the user at Gate 1 (open question 3). The superseded-credential blanking period is a security number with no legal counterparty, so it is set here at 90 days — long enough for an incident review, short enough that a leaked-then-rotated merchant secret stops being recoverable from our disk.

### Two ports, not one (D1)

Two things are being abstracted and they are orthogonal:

| Axis | Port | Adapters shipped here | Adapter deferred |
|---|---|---|---|
| Which provider takes the money | `PaymentGateway` | `FakeGateway`, `UnconfiguredGateway` | `GrowGateway` (F18) |
| Which key manager protects the credential | `SecretBox` | `FakeSecretBox`, `UnconfiguredSecretBox` | `KmsSecretBox` (own commit) |

Collapsing them — putting encrypt/decrypt on the gateway adapter — would mean the fake gateway can never be exercised against real KMS and the real gateway can never be exercised without it, which is exactly the coupling that makes an integration untestable. Every credential blob encrypts identically whether Grow, Yaad or Tranzila reads it.

### Module: `app/payments/`

| File | Contents |
|---|---|
| `base.py` | `PaymentGateway` Protocol; the six errors; frozen dataclasses `GatewayCredentials`, `PaymentSession`, `WebhookEvent`. **Imports nothing from `app/db/` or any feature module** — the `notifications/base.py` rule, which is why `DepositHold`/`Settlement` live in `service.py`: they carry a `Payment` model and the port must not know one exists |
| `secretbox.py` | `SecretBox` Protocol + `FakeSecretBox` + `UnconfiguredSecretBox` + `SecretDecryptError`, `SecretBoxNotConfiguredError`. One file on purpose: ~60 lines, no adapter in it performs I/O. The split into `base/fake/unconfigured` earns itself when `kms.py` lands (D19) |
| `fake.py` | `FakeGateway` — records instead of calling, real HMAC on webhooks |
| `unconfigured.py` | `UnconfiguredGateway` — every **I/O** method raises `GatewayNotConfiguredError`; `is_configured = False`; the two metadata properties answer rather than raise (D22) |
| `service.py` | `GatewayCredentialService` (sole writer of `tenant_gateway_credentials`) and `PaymentService` (sole writer of `payments`) |
| `router.py` | the four owner-only `/manage/gateway` routes |
| `schemas.py` | `GatewayStatusResponse`, `SetGatewayCredentialsRequest` |
| `validation.py` | credential-shape validation + every named constant (product policy, never `Settings` — the F8/F10 rule quoted at the top of `app/notifications/validation.py`) |

Models `app/models/tenant_gateway_credential.py`, `app/models/payment.py`; repositories `app/db/repositories/gateway_credentials.py`, `app/db/repositories/payments.py` — stateless, session-first, explicit `tenant_id` predicate as defence-in-depth beside RLS, house naming:

| Repository | Methods |
|---|---|
| `gateway_credentials.py` | `insert`, `active_for_provider`, `newest_for_provider` (D20 — ignores `deleted_at` **and** `status`), `mark_status`, `soft_delete_active` |
| `payments.py` | `insert`, `live_pending_for_booking` (D23's converge read), `by_provider_transaction_id`, `by_provider_session_id`, `settle` (D24's guarded UPDATE, returns `None` when it does not fire) |

**The adapter never sees the database and the repositories never see the adapter.** `GatewayCredentialService` is the only path that writes a credential row; `PaymentService` is the only path that writes a payment row. F19's sweeper, F19's webhook route and F18's real adapter all go through them — a future caller cannot skip the row any more than a future SMS adapter can skip `message_log`.

#### `base.py`

```python
class GatewayNotConfiguredError(Exception): ...       # no adapter at all — a supported deployment
class GatewayNotConnectedError(Exception): ...        # adapter exists; THIS tenant has no valid credentials
class GatewayCredentialsRejectedError(Exception): ... # the provider said no to these credentials
class GatewayUnavailableError(Exception): ...         # unreachable/refused; carries no provider text
class GatewayWebhookInvalidError(Exception): ...      # signature did not verify — authentication, NOT an outage (D25)
class PaymentAlreadyHeldError(Exception): ...         # a live hold exists that open_deposit could not converge on (D23)

@dataclasses.dataclass(frozen=True)
class GatewayCredentials:
    provider: str
    fields: Mapping[str, str]      # opaque to everything except the adapter. __repr__ is overridden
                                   # to print field NAMES only — a stray log line or a traceback must
                                   # never render a merchant secret (the S3MediaStorage rule, made
                                   # structural because here the secret is IN the object).

@dataclasses.dataclass(frozen=True)
class PaymentSession:
    provider_session_id: str
    redirect_url: str

@dataclasses.dataclass(frozen=True)
class WebhookEvent:
    provider_session_id: str
    provider_transaction_id: str
    amount_agorot: int
    paid: bool

class PaymentGateway(Protocol):
    @property
    def provider(self) -> str: ...
    @property
    def is_configured(self) -> bool: ...
    @property
    def credential_fields(self) -> frozenset[str]: ...        # the adapter declares its own shape
    async def validate_credentials(self, credentials: GatewayCredentials) -> None: ...
    async def create_session(
        self, credentials: GatewayCredentials, *, amount_agorot: int,
        reference: str, return_url: str, expires_in: int,
    ) -> PaymentSession: ...
    def verify_webhook(
        self, credentials: GatewayCredentials, *, body: bytes, signature: str
    ) -> WebhookEvent: ...
```

`verify_webhook` is a plain `def` while the other two are `async`, for the reason `MediaStorage`'s docstring already gives about `presigned_post`: signature verification is local HMAC with zero I/O, and making it async would be a lie. It raises `GatewayWebhookInvalidError` — **never** `GatewayUnavailableError` (D25). `validate_credentials` returns `None` and raises `GatewayCredentialsRejectedError` rather than returning a bool — the caller must not be able to ignore the answer.

**`UnconfiguredGateway` answers its metadata, raises its I/O (D22).** `provider` returns `None`, `credential_fields` returns `frozenset()`, `is_configured` is `False`; only `validate_credentials`, `create_session` and `verify_webhook` raise `GatewayNotConfiguredError`. That is what makes `GET /manage/gateway` → 200 `configured: false` structural rather than a remembered `if` in the route, and it is the one place this port departs from `UnconfiguredMediaStorage` — which has no metadata properties to answer, so it settles nothing either way.

**No `refund()` method** (D12). **`reference` is a caller-supplied opaque string** (F19 will pass the booking id) so the port has no knowledge of the booking domain.

#### `secretbox.py`

```python
class SecretBox(Protocol):
    @property
    def key_ref(self) -> str: ...                     # persisted as tenant_gateway_credentials.key_ref
    @property
    def is_configured(self) -> bool: ...
    async def encrypt(self, plaintext: bytes, *, context: Mapping[str, str]) -> str: ...
    async def decrypt(self, ciphertext: str, *, context: Mapping[str, str]) -> bytes: ...
```

`async` because the real implementation is a network call (KMS), wrapped in `anyio.to_thread.run_sync` exactly as `S3MediaStorage.head_object` wraps botocore.

**`context` is the load-bearing parameter.** Every call passes `{"tenant_id": str(tenant_id), "purpose": ENCRYPTION_CONTEXT_PURPOSE}`. AWS KMS binds the encryption context into the AEAD's additional authenticated data, so a ciphertext blob copied into another tenant's row **cannot be decrypted** — the isolation is cryptographic, on top of RLS, on top of the explicit `tenant_id` predicate. That property is why KMS beats a Fernet key in env (D2), and `FakeSecretBox` emulates it (rejects a context mismatch) so the regression test for it exists in CI with no AWS account.

`FakeSecretBox` is base64 of `json({"context": …, "plaintext": …})` with an unmissable `fake-secretbox-v1:` prefix and `key_ref = "fake"`. It is not encryption and its docstring says so in the first line. Two things keep it out of production: the `Settings` validator below, and `provider IN ('fake')` in 0012.

`UnconfiguredSecretBox.encrypt/decrypt` raise `SecretBoxNotConfiguredError`; `is_configured = False`; `key_ref` raises. Chosen over `None` for the reason `app/storage/unconfigured.py` gives.

#### `fake.py`

`FakeGateway` mirrors `FakeSmsSender`: it records instead of calling.

- `credential_fields = frozenset({"merchant_id", "api_key", "webhook_secret"})` — a plausible shape, explicitly **not a claim about Grow's**.
- `validate_credentials` appends to `self.validations` and raises `GatewayCredentialsRejectedError` when `merchant_id == FAKE_INVALID_MERCHANT_ID` (`"invalid"`). One sentinel, one branch, both paths deterministic in tests, and staging can demonstrate the invalid state on demand.
- `create_session` appends to `self.sessions: list[FakeSession]` and returns `PaymentSession(provider_session_id=f"fake-{n}", redirect_url=f"{FAKE_PAY_PATH}?session=fake-{n}")` from an `itertools.count`, the `FakeSmsSender` message-id pattern. **No credential value is logged** — one INFO line naming the session id and the amount, matching `FakeSmsSender`'s refusal to log the body.
- `verify_webhook` computes `hmac.new(webhook_secret, body, sha256).hexdigest()` and compares with `hmac.compare_digest`, raising **`GatewayWebhookInvalidError`** on mismatch (D25). Real crypto, deliberately: F19's signature and tamper tests must exercise a real comparison, not a stub that returns `True`.

#### `service.py`

`GatewayCredentialService(session_factory, *, gateway, secret_box, connect_limiter, validate_limiter, clock)`:

| Method | Does |
|---|---|
| `status(tenant_id) -> GatewayStatus` | reads the active row (or its absence). **Never decrypts** — status is a read of metadata, and a route that answers "are we connected" must not touch key material |
| `connect(tenant_id, *, fields, actor_id)` | spend `connect_limiter` → validate shape → build `GatewayCredentials` → `gateway.validate_credentials` → `secret_box.encrypt` → one `tenant_session`: soft-delete the active row, insert the new one at `status='valid'`, write the audit row |
| `revalidate(tenant_id, *, actor_id)` | decrypt → ping → write `status` + `last_validated_at` (+ scrubbed `validation_error`), and an audit row on **every** outcome (D26) |
| `disconnect(tenant_id, *, actor_id)` | soft-delete the active row + audit row, one transaction; `DomainNotFoundError` when nothing is connected. **No precondition on in-flight payments** — see D20 |
| `credentials_for(tenant_id) -> GatewayCredentials` | the **use** path: authorisation to move new money. `GatewayNotConnectedError` when absent or `status='invalid'`. Called by `open_deposit` only |
| `verification_credentials_for(tenant_id) -> GatewayCredentials` | the **verification** path: `newest_for_provider` ignoring `deleted_at` and `status`. Called by `settle_from_webhook` only (D20) |

The network calls (`validate_credentials`, `encrypt`) happen **outside** the transaction, for the reason `NotificationService.send_sms` splits its own phases: a provider hang must never hold a DB transaction open. Ordering is deliberate: the ping and the encrypt both precede the write, so a rejected credential set leaves the previous working one untouched (D4).

**`revalidate` writes `status='invalid'` only for `GatewayCredentialsRejectedError` (D26).** A `GatewayUnavailableError` from the ping leaves `status` *and* `last_validated_at` untouched and surfaces 503 — the same asymmetry D4's decrypt carve-out already argues, for the same reason. A provider blip is not evidence that a merchant account is bad, and marking it `invalid` would take deposits offline for a boutique whose credentials are fine.

`PaymentService(session_factory, *, gateway, credentials, clock)`.

Its two returns are frozen dataclasses declared **here, not in `base.py`** — both carry a `Payment` model, and the port is not allowed to know one exists:

```python
@dataclasses.dataclass(frozen=True)
class DepositHold:
    payment: Payment
    redirect_url: str
    created: bool          # False == converged onto an existing live hold (D23)

@dataclasses.dataclass(frozen=True)
class Settlement:
    payment: Payment
    newly_settled: bool    # False == a redelivery, a lost race, or a late settlement (D24)
```

Both carry a flag rather than being a bare row, for `BookingClaim`'s reason: F19 gates its side effects — the booking-confirm and F16's confirmation SMS — on "did this call actually change anything", and a bare row cannot answer that.

- `open_deposit(tenant_id, *, booking_id, amount_agorot, hold_seconds, return_url) -> DepositHold` — the **only** path that inserts a payment row. Ordered as **D23** requires, and the ordering is the whole point:

  1. `credentials_for(tenant_id)` — the use path, so a disconnected or `invalid` credential 409s here and nothing is minted.
  2. `pg_advisory_xact_lock(hashtext(tenant_id))` — the `create_booking` lock, the same key, taken for the same reason. Everything from here to COMMIT holds it.
  3. `live_pending_for_booking(booking_id)` — **read first, and converge**. A live hold exists → return it unchanged with its stored `provider_session_id`, `created=False`, and **no gateway call at all**. This is the idempotent read F19's retry path wants anyway, and it is what makes a double-tap free rather than expensive.
  4. Only now `gateway.create_session`, then insert the `pending` row with `provider_session_id` and `hold_expires_at = now + hold_seconds`.
  5. `IntegrityError` on that insert → `raise PaymentAlreadyHeldError from exc`. The backstop for a writer that skipped the lock, mapped exactly as `create_booking` maps `SlotUnavailableError` — never an unhandled 500.

  **The gateway call is inside the lock and after the read, not before either.** Minting a hosted-page session before the row that can refuse the insert leaves a live, payable session at the provider with no row behind it — and if she pays on it, `settle_from_webhook` matches no row and the charge is unrecorded. A provider hang now holds the per-tenant lock, which is the accepted cost: the alternative loses money, and `create_session` is the one call in this path with a timeout the adapter owns.

- `settle_from_webhook(tenant_id, *, body, signature) -> Settlement` — `verification_credentials_for` (D20, **not** `credentials_for`) → `gateway.verify_webhook` → then **one guarded statement, not a read-modify-write** (D24):

  1. `by_provider_transaction_id` — already settled → `Settlement(payment, newly_settled=False)`, no write. The cheap sequential path.
  2. Otherwise `by_provider_session_id`, and **assert `event.amount_agorot == row.amount_agorot`** (D14). A mismatch persists its evidence and then refuses — see below.
  3. `settle(...)` — `UPDATE payments SET status='paid', paid_at=…, provider_transaction_id=… WHERE id=… AND tenant_id=… AND status='pending'`, the `ScheduledMessageRepository.mark` shape. Rowcount 0 → re-read and branch on what the row actually is, and **the two reasons it can be 0 are not the same event**:
     - the row is now `paid` with this same txn id → a concurrent delivery won the race. Return `newly_settled=False`. Exactly one of two concurrent redeliveries can transition the row, because the guard is evaluated by the database under the row lock, not by us.
     - the row is `expired` (F19's sweeper got there first) → **a late settlement: real money was taken against a hold that no longer exists.** It writes a `GATEWAY_LATE_SETTLEMENT` audit row and a scrubbed `payments.error`, and returns `newly_settled=False`. It is *not* silently discarded, and it is deliberately not auto-refunded or auto-honoured here — that is money policy and it is **open question 4**. F17's obligation is that the event is durable and distinguishable; F19 acts on it.

  **The unique index on `(tenant_id, provider, provider_transaction_id)` is the backstop, not the mechanism (D24).** 0009's comment is explicit that the service converges under the lock and the index catches the writer that skips it — and on *this* path there is no insert at all, only an update to one row, so two concurrent deliveries writing the same txn id to the same row never violate it. The guarded UPDATE is what actually makes the transition happen once.

**Failure paths persist their evidence, outside the raising transaction.** A rejected signature and an amount mismatch are both attacker-reachable outcomes (D14), and both currently leave nothing behind. Each writes its audit row in a `tenant_session` that is allowed to **exit and commit** before the exception is raised — the `.memory/patterns/commit-before-raise-in-tenant-session.md` rule, which names "future booking/payment failure records" verbatim as the class this is. The amount mismatch additionally writes the scrubbed detail to `payments.error` and leaves `status` at `pending`; it does **not** invent a `failed` transition, because whether a mismatched settlement expires or is chased by hand is F19's sweeper policy.

`settle_from_webhook` deliberately does **not** touch `bookings`. Flipping a booking to `confirmed` and firing F16's confirmation SMS is F19's transaction; a payments service reaching into the booking domain is the coupling that would make F19 unable to order its own writes.

### API surface

New router in `app/payments/router.py`, prefix `/manage`, **router-level `require_role(StaffRole.OWNER)`** — the first router in the repo that is owner-only in full (D13). Registered in `create_app()` after `owner_booking_router`; it is the fifth `/manage` router, so the same silent-shadowing hazard `main.py:626-635` documents applies and its own `ROUTES` table is what keeps it honest.

```
GET    /manage/gateway                → GatewayStatusResponse
PUT    /manage/gateway/credentials    → GatewayStatusResponse    body: {"fields": {...}}
POST   /manage/gateway/validate       → GatewayStatusResponse    no body — re-pings what is stored
DELETE /manage/gateway/credentials    → GatewayStatusResponse
```

PUT/DELETE rather than POST sub-paths, matching `app/boutique/router.py`'s existing `PUT /manage/settings` / `DELETE /manage/appointment-types/{id}` vocabulary.

`GatewayStatusResponse` — the whole response, in every state:

```json
{
  "provider": "fake",
  "configured": true,
  "connected": true,
  "status": "valid",
  "last_validated_at": "2026-07-30T09:12:00Z",
  "credential_fields": ["api_key", "merchant_id", "webhook_secret"]
}
```

- `provider` is `null` and `configured` is `false` when the platform has no adapter. **`GET` still answers 200 in that state**, never 503: a console that cannot read its own status cannot explain to the owner why deposits are unavailable.
- `connected` is tenant-level, `configured` is platform-level. Two booleans because the two facts have different owners and different remedies — the operator fixes one, the boutique fixes the other.
- `status` / `last_validated_at` are `null` when not connected.
- `credential_fields` is `gateway.credential_fields`, sorted. This is what lets the console render the right form without hardcoding a provider's field names — the payoff of D5, and it is why F18 needs no frontend change.
- **Nothing else.** No ciphertext, no `key_ref`, no `validation_error`, no field value, ever. `validation_error` is operator telemetry on the row, held to the same containment as `message_log.error`.

`PUT` body: `{"fields": {"merchant_id": "…", "api_key": "…", "webhook_secret": "…"}}`. Validation in `app/payments/validation.py`, mirroring `validate_profile`'s shape and message register: the key set must **equal** `credential_fields` exactly (a missing or unknown key is a `DomainValidationError` → the existing 400 handler, message `f"unknown credential fields: {…}"` / `f"missing credential fields: {…}"`), every value non-blank and `≤ MAX_CREDENTIAL_FIELD_VALUE_LENGTH`, and the serialized blob `≤ MAX_CREDENTIAL_BLOB_BYTES`.

**Credentials are write-only by construction.** The API has no read path for a field value, so the console form always starts empty and a save always sends the complete set. That is also why there is no PATCH: a partial update would require reading back what it is not replacing.

**Both outbound-calling routes carry a limiter, and they are two instances, not one.** The house rule is stated four times in `main.py` — "max_attempts lives on the LIMITER, not per key, so a second key on an existing budget could never trip first" — so one budget means one instance:

| Route | Limiter | Budget | Why |
|---|---|---|---|
| `POST /manage/gateway/validate` | `validate_limiter` | 10 / hour / tenant | an authenticated route that makes an outbound provider call; a runaway brake on a stuck button, not a defence |
| `PUT /manage/gateway/credentials` | `connect_limiter` | 10 / hour / tenant | it does strictly more: an outbound ping, a KMS `Encrypt`, **and** a soft-delete + insert on a table whose DELETE is revoked (D6, D7). That last clause is verbatim why `terms_creation_max_per_window` exists — "the table is append-only by DB grant, so spam on this path is permanent bloat" — and rotation-by-insert makes a loop on PUT unreclaimable table growth plus unbounded KMS request spend |

Sized like the terms budget it is copied from, and wired on the service exactly as `terms_rate_limiter` is (`main.py:303-310`).

**CSRF is covered, not argued away.** `CsrfOriginMiddleware.PROTECTED_PREFIX` is `/manage`, and these are cookie-authenticated state-changing routes — the opposite of the OTP router's structural N/A. No middleware change.

Every mutation writes `audit_log`, with seven new `AuditAction` members and **no migration** — `audit_log.action` is unconstrained TEXT (0003). `details` carries **field names only, never values**, the rule F53's LOOP-STATE note states for PII and which matters more here.

| Action | Written when | Actor |
|---|---|---|
| `GATEWAY_CONNECTED` | `connect` succeeds | `actor_id` (owner) |
| `GATEWAY_DISCONNECTED` | `disconnect` succeeds | `actor_id` (owner) |
| `GATEWAY_VALIDATED` | `revalidate` returns `valid` | `actor_id` (owner) |
| `GATEWAY_VALIDATION_FAILED` | `revalidate` returns `invalid` | `actor_id` (owner) |
| `GATEWAY_WEBHOOK_REJECTED` | a signature does not verify | none — an unauthenticated caller (D25) |
| `GATEWAY_AMOUNT_MISMATCH` | the webhook's amount ≠ the recorded row's | none — same (D14) |
| `GATEWAY_LATE_SETTLEMENT` | a verified webhook settles a hold that already `expired` | none — same (D24) |

The first four commit **in the same `tenant_session` as the write they describe**; the last three are failure-path writes and must commit *before* the raise (or the return), per `.memory/patterns/commit-before-raise-in-tenant-session.md` — which names "future booking/payment failure records" as this exact class.

**`GATEWAY_VALIDATED` exists because the `invalid → valid` flip is the transition that re-enables money movement for the boutique** (D26). Auditing only the failure would leave the *recovery* — the state change an incident review most wants to place in time — with no row at all, while still mutating `status` and `last_validated_at`. And every owner-initiated action carries a real `actor_id`: `AuditLogRepository.record` defaults it to `None`, so an omitted argument is silent, not a type error, and an owner tap would be indistinguishable from a system-initiated sweep.

### Errors (house shape, fixed bodies in `main.py`)

| Error | Status | Code | Message |
|---|---|---|---|
| `GatewayNotConfiguredError` | 503 | `GATEWAY_NOT_CONFIGURED` | "Deposits are not available." |
| `SecretBoxNotConfiguredError` | 503 | `GATEWAY_NOT_CONFIGURED` | same body (D18) |
| `GatewayNotConnectedError` | 409 | `GATEWAY_NOT_CONNECTED` | "Connect a payment account first." |
| `GatewayCredentialsRejectedError` | 400 | `GATEWAY_CREDENTIALS_REJECTED` | "The payment account details were refused." |
| `GatewayUnavailableError` | 503 | `GATEWAY_UNAVAILABLE` | "The payment provider is temporarily unavailable." |
| `SecretDecryptError` | 503 | `GATEWAY_UNAVAILABLE` | same body |
| `GatewayWebhookInvalidError` | **400** | `GATEWAY_WEBHOOK_INVALID` | "The webhook could not be verified." (D25) |
| `PaymentAlreadyHeldError` | 409 | `PAYMENT_ALREADY_HELD` | "A deposit is already pending for this booking." (D23) |
| validate **or connect** budget exhausted | 429 | `TOO_MANY_ATTEMPTS` | existing body |
| bad credential shape | 400 | `VALIDATION_ERROR` | existing `DomainValidationError` handler |
| disconnect with nothing stored | 404 | `NOT_FOUND` | existing `DomainNotFoundError` handler |

400 for a rejected credential set, not 409: the request is well-formed but its *content* is wrong, and the owner's remedy is to retype it — the same reading `MediaMismatchError` applies in reverse.

**A failed signature is 400, never 503 (D25).** Folding it into `GatewayUnavailableError` would report an authentication failure as a provider outage: it invites the provider to retry a forgery, it is indistinguishable from a real outage in logs and alerting, and it would make the checklist row "webhook signature verification + replay protection" unprovable from the outside. F19 owns the webhook route and answers 400 there; F17 owns the error that makes 400 the only sane mapping.

**A decrypt failure does not flip `status` to `'invalid'`.** A blob we cannot open is our problem — a rotated key, a wrong encryption context, an operator error. Marking it `invalid` would render "your merchant account was refused" to an owner whose account is fine, and would send her to Grow's support desk over our bug.

### Config (`Settings`)

```python
payment_provider: Literal["fake"] | None = None       # the real provider literal arrives with its adapter
gateway_secret_box: Literal["fake"] | None = None     # "kms" arrives with KmsSecretBox
gateway_validate_max_per_tenant_window: int = 10
gateway_validate_window_seconds: int = 3600
gateway_connect_max_per_tenant_window: int = 10        # rotation is insert-only; a loop is permanent bloat
gateway_connect_window_seconds: int = 3600
gateway_superseded_credential_retention_days: int = 90  # D21's blanking clock, read by F20
```

Validators, mirroring `_forbid_sms_test_paths_in_production` and `_require_usable_media_config`:

1. `app_env == "production"` and `payment_provider == "fake"` → boot failure. The fake gateway reports money received that was never charged; in production that is a silent revenue hole with a confirmed booking on top of it.
2. `app_env == "production"` and `gateway_secret_box == "fake"` → boot failure. The fake box is base64.
3. `payment_provider` set with `gateway_secret_box` unset → **boot failure**. This is the `MEDIA_REGION is required when MEDIA_BUCKET is set` case, and 0005's reasoning applies verbatim: "a MISSING bucket is never a boot failure … a WRONG one is". A gateway with nowhere to put credentials is a misconfiguration, not a deployment.

Both unset in every environment → `UnconfiguredGateway` + `UnconfiguredSecretBox`, every gateway route 503s, deposits are simply unavailable. That is a supported deployment, exactly like a missing media bucket. `_build_payment_gateway` and `_build_secret_box` each log one INFO line, because `Settings.model_config` is `extra="ignore"` and a typo'd `PAYMENT_PROVDER` is otherwise silent (`main.py:232-261`).

No `gateway_kms_key_id` / `gateway_kms_region` yet — they arrive with the adapter that reads them.

### Named constants (`app/payments/validation.py`)

| Constant | Value | Why |
|---|---|---|
| `MAX_CREDENTIAL_FIELD_VALUE_LENGTH` | 512 | a provider key or secret; anything longer is a paste error, and the cap is what keeps a hostile blob out of the KMS call |
| `MAX_CREDENTIAL_BLOB_BYTES` | 3000 | **AWS KMS `Encrypt` accepts at most 4096 plaintext bytes.** The cap exists so the fake box and the future KMS adapter cannot disagree about what fits — otherwise a credential set that saves in staging fails in production |
| `ENCRYPTION_CONTEXT_PURPOSE` | `"gateway_credentials"` | the AAD label; a second purpose gets its own, never this one widened |
| `MAX_VALIDATION_ERROR_LENGTH` | 200 | the `MAX_PROVIDER_ERROR_LENGTH` value from `notifications/service.py`, same reason |
| `FAKE_INVALID_MERCHANT_ID` | `"invalid"` | the fake's deterministic rejection path |
| `FAKE_PAY_PATH` | `"/fake-pay"` | where the fake's redirect points; F19 decides what serves it |

## Frontend changes

New owner-only section in the manage console. Assembled entirely from existing `packages/ui` primitives (`Card`, `SectionHeading`, `Input`, `Button`, `Badge`, `PolicyBlockerBanner`, `useToast`) → the design gate **self-approves** under Interview Q2; no novel interaction pattern.

- **`App.tsx`**: `SectionKey` gains `"gateway"`; one nav row. **The nav item is hidden for non-owners inline** — `staff.role === "owner"` (the field already exists on `Staff`) — because F51 owns the general role-filtered nav table and shipping a nav item whose every call 403s is worse than three lines of duplication (D16).
- **`api.ts`**: `GatewayStatus` type + `gatewayStatus()`, `setGatewayCredentials(fields)`, `validateGateway()`, `disconnectGateway()`. Wire format is snake_case verbatim, per the file's own header — there is no case-conversion layer in this app.
- **`components/GatewaySection.tsx`**:
  - Status card — three renderings: **not configured** (platform has no gateway; an explanatory line, no form, no buttons), **not connected** (the form), **connected** with a `Badge` for `valid`/`invalid` and `last_validated_at` rendered through the existing `lib/jerusalem.ts` helpers with `<bdi dir="ltr">` isolation (R19).
  - **A test-environment notice above the form whenever `provider === "fake"`** — `"סביבת בדיקות — אין להזין פרטי סליקה אמיתיים"`, keyed in `he.ts`/`ar.ts`. Both production boot failures are keyed on `app_env == "production"` and 0012's CHECK admits `'fake'` everywhere, so **staging runs `FakeSecretBox` and will store a real merchant credential set as base64 of plaintext** — and Risk 7's answer, operator-assisted onboarding, happens on staging first. The three guards at Risk 5 protect production and say nothing about this. The API already returns `provider`, so the whole fix is one conditional block.
  - Credentials form generated by mapping over `credential_fields` — every input `type="password"` with `autoComplete="off"`, always empty on load (write-only, above). Submitting sends the complete set. A field with no `gateway.field.*` key falls back to **`<bdi dir="ltr" lang="en">{field}</bdi>`** — an untranslated LTR snake_case run inside an RTL Hebrew form needs both the bidi isolation this repo already applies to non-numeric labels (`VariantMatrix.tsx:183`) and the WCAG 3.1.2 language mark. An axe pass cannot catch it, because a `<label>` element exists either way.
  - "Validate now" → `POST /validate`; a resulting `invalid` re-renders the badge and shows the generic refusal copy — never a provider message, because the API does not return one.
  - "Disconnect" is two-step (reveal-then-confirm), the F16 cancel precedent: disconnecting stops deposits for the whole boutique.
  - **`PolicyBlockerBanner`** when `toggles.deposits_enabled` is true and `connected` is false, reused verbatim from `packages/ui` — the one cross-section fact the owner must see, composed from the two calls the console already makes rather than a derived field on the API (see open question 1 for what the *storefront* should do in that state; this feature ships only the owner-side warning).
- **`i18n/he.ts` + `i18n/ar.ts`**: a new `gateway.*` section plus `nav.gateway`, all keys as dotted literals; Arabic values are the Hebrew standing in, per that file's own header and pre-decided #47. **`i18n.test.ts` does not currently see them, and this feature is what fixes that** — its `f15Entries()` filter is hardcoded to `nav.bookings` and the `booking.` prefix, and the only `ar` assertion is "carries no empty string", which is vacuous for a *missing* key. So the `ar` bundle could ship with zero gateway keys and the suite stays green. See the Testing section: widening the filter and adding a real he/ar parity assertion is new work in this feature, not an existing guarantee to lean on.
- **No storefront change.** The deposit amount is already disclosed (`AppointmentTypeRow.deposit_*`), and nothing customer-facing changes until F19.

## Testing

Fast suite (no marker) — runs with no Docker, no AWS, no provider:

- **`test_payments_validation.py`** — the credential-shape table: exact-set match, unknown key, missing key, blank value, over-length value, over-blob-bytes; each constant asserted against its documented reason (the `MAX_CREDENTIAL_BLOB_BYTES` case names the KMS 4096-byte ceiling in the test, so a future raise has to argue with it).
- **`test_payments_adapters.py`** (`test_notifications_adapters.py` shape) — `FakeGateway`: validate accepts, validate rejects the sentinel, `create_session` records the call and returns a stable id, `verify_webhook` accepts a correctly-signed body and rejects (a) a tampered body, (b) a signature made with the wrong secret — **asserting `GatewayWebhookInvalidError` by type, not merely "rejected"**, since an assertion that any exception raised is exactly what lets D25's misclassification ship green. `UnconfiguredGateway`: `is_configured is False`, **`provider is None` and `credential_fields == frozenset()`**, and every *I/O* method raises `GatewayNotConfiguredError`. `FakeSecretBox`: round-trip; **decrypt with another tenant's context raises `SecretDecryptError`** — the emulated KMS guarantee, and the only place it is testable without AWS. `UnconfiguredSecretBox` raises on both. Plus: `repr(GatewayCredentials(...))` contains the field names and **none of the values** (the assertion that survives a refactor of the dataclass).
- **`test_payments_api.py`** (`test_boutique_api.py` shape — fake service, hardcoded resolver, no DB) — a module-level `ROUTES` table for all four, **exported for `test_staff_role_gating.py` to import**; 401 with no cookie; four happy paths; PUT with an unknown field → 400 `VALIDATION_ERROR`; PUT when the ping rejects → 400 `GATEWAY_CREDENTIALS_REJECTED` **and the fake service records no write**; GET with no platform gateway → 200 `configured: false` (not 503); validate budget → 429; **connect budget → 429**; and a **whole-body substring sweep** over every response asserting a sentinel secret value never appears.
- **`test_staff_role_gating.py`** — two edits, and the second is the one that matters:
  1. `OWNER_ONLY` gains the four `/manage/gateway*` rows. Until it does, **`test_route_table_matches_the_permission_matrix`** fails with "routes lock shift_manager out but are not in OWNER_ONLY". **That red build is the intended first state**, the F11 sibling-router precedent: narrowing the shift manager's surface is meant to be a deliberate, reviewed edit.
  2. `test_payments_api.ROUTES` is imported and added to the `[*ROUTES, *CATALOG_ROUTES]` walk in **both** `test_shift_manager_is_admitted_everywhere_except_terms_publishing` and `test_unknown_role_is_403_on_every_gated_route`. Without this the four new rows get **no end-to-end 403 assertion at all**: those two tests iterate hand-maintained tables imported from `test_boutique_api` and `test_catalog_api`, exactly as that file's own docstring says ("the HTTP matrix reuses the hand-maintained ROUTES tables … so it covers exactly what those modules cover"). A gateway route is in neither, so they stay green either way, and adding the `OWNER_ONLY` rows would silence the one structural test while the HTTP wiring went unproven. Wired the way F8's and F31's tables were.
- **`test_config.py`** — the three new boot failures. *Note for the builder:* this file already shows two failures locally that are false, caused by `Backend/.env` leaking `MEDIA_BUCKET`; CI is green. Do not chase them.

`db`-marked (**CI only — no Docker locally, so these debut on the first CI run**; budget one fix commit, per house experience with F11 and F16):

- **`test_payments_repositories.py`** — credential insert / soft-delete / rotate round-trip; the active-unique index converges a double connect; `payments` insert and each status transition; the `provider_transaction_id` unique index rejects a replayed webhook row; the pending-per-booking unique index rejects a second live hold.
- **`test_payments_isolation.py`** (`test_notifications_isolation.py` shape) — tenant B reads zero rows from both tables; a cross-tenant UPDATE is a no-op. `test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls` picks both tables up with **no edit**, which is the assertion that keeps future tables honest.
- **`test_payments_service.py`** — `connect` writes exactly one credential row and one audit row in one transaction; a rejected ping writes **neither**; `revalidate` flips `valid → invalid`, records `GATEWAY_VALIDATION_FAILED` **with a non-NULL `actor_id`**, and stores a truncated `validation_error`; `revalidate` on a *successful* ping records `GATEWAY_VALIDATED` (the `invalid → valid` recovery leaves a row); **a `GatewayUnavailableError` from the ping leaves `status` AND `last_validated_at` untouched** (D26); a decrypt failure raises `GatewayUnavailableError` and leaves `status = 'valid'`; `credentials_for` raises `GatewayNotConnectedError` for an `invalid` row.

  The four cases the previous draft's sequential assertions could not fail on — `.planning/architecture.md:56` makes "explicit concurrency/race tests (double-book, waitlist claim, **duplicate webhooks**)" standing strategy, and every one of these needs a genuinely concurrent driver (two `asyncio.gather`ed calls), not a loop:

  - **Two concurrent redeliveries of the same transaction produce exactly one `pending → paid` transition** — `newly_settled=True` on exactly one, `False` on the other, and one `paid_at`. A sequential second-delivery test passes while D24 is broken, which is the whole reason this one exists.
  - **Two concurrent `open_deposit` calls for one booking yield one payment row and one `provider_session_id`** — and the `FakeGateway` records **exactly one** `create_session` call. That second assertion is the orphaned-session check: it fails if the gateway is called before the converge read even when the row count is right.
  - **A webhook settles after `disconnect`** (D20). Open a hold, disconnect, deliver a correctly-signed webhook → it verifies and settles. This is the money-loss regression; it fails outright against a `settle_from_webhook` that resolves through `credentials_for`.
  - **A webhook settles after the credential flips to `invalid`** — same path, same reason.

  Plus the two failure-path evidence cases, asserted as `.memory/patterns/commit-before-raise-in-tenant-session.md` demands — **that the row exists after the failure**, not merely that the exception raised: a forged signature raises `GatewayWebhookInvalidError` **and** leaves a `GATEWAY_WEBHOOK_REJECTED` audit row; an amount mismatch raises **and** leaves a `GATEWAY_AMOUNT_MISMATCH` row plus a scrubbed `payments.error`, with `status` still `pending`.
- **`test_migrations.py`** — 0012 up/down round-trip; the `provider` CHECK admits `'fake'` and **rejects `'grow'`** (so nobody later assumes F18's value is already allowed); the DELETE revoke is real — an `app_user` DELETE on each table raises `permission denied`, the shape of F31's app-role UPDATE probe.

Frontend: **`GatewaySection.test.tsx`** — all three status renderings, the write-only form (empty on load, full set on submit), the two-step disconnect, the deposits-on-with-no-gateway banner, the nav item absent for a `shift_manager`, **the `provider === "fake"` test-environment notice present (and absent for any other provider)**, and **the unkeyed-field label rendering as `<bdi dir="ltr" lang="en">`** beside the keyed path; axe pass.

**`i18n.test.ts` needs two edits before it asserts anything about this feature** — the current file is scoped to F15 and would report green on a completely empty `gateway.*` section in both bundles:
  - widen `f15Entries()` to a general dotted-literal predicate (or add a sibling `gatewayEntries()`), so `nav.gateway` and every `gateway.*` key is actually in scope;
  - add the **he/ar key-parity assertion that does not exist anywhere today** — `Object.keys(ar.translation)` equals `Object.keys(he.translation)`. The existing `describe("the ar bundle")` only forbids an empty *value*, which is vacuous for a missing key.

**No new E2E** — there is no customer-visible surface until F19 and the console flow is fully covered by the component test; the existing Playwright suite must stay green, which is what the CI gate checks.

## Out of scope

- **The real Grow adapter (F18, parked on the merchant account)** — including Grow's actual credential field names, its session API, its webhook signature scheme, and the `provider = 'grow'` CHECK widening. The port is its contract.
- **The `KmsSecretBox` adapter and the KMS key itself** — its own commit when a key exists, exactly as F11 held the Twilio adapter out (D3). Provisioning the key is an infra action.
- **The deposit booking flow (F19)**: the `pending_payment` booking status and its CHECK widening, the 15-minute slot hold, the expiry sweeper, webhook → `confirmed` → F16's confirmation SMS, reschedule carrying the deposit, and the refund-due / forfeit branches off the accepted terms version.
- **Refunds of any kind**, and any refund method on the port. F18 wraps the call, E5 #29 automates it under pre-decided #21's rails.
- **Receipt (קבלה/חשבונית) issuance and its storage columns** — blocked on the merchant account; see Risk 1.
- **Anything customer-facing.** No storefront change, no new public route, no webhook endpoint (F18/F19 own the route; F17 owns the verification method behind it).
- **The checklist's CSP row** ("CSP forbids card fields / third-party scripts on our origin") — no card field exists on our origin and none is added here; the header is F21's.
- Redis-backed distributed rate limiting for the validate and connect budgets (F21).

## Risks & open items

1. **The epic's own F17 scope contains an item F17 cannot discharge.** The brief requires F17 to "verif[y] whether Grow auto-issues receipts (קבלה/חשבונית) for charges and refunds — an Israeli legal obligation for J4 charges". That needs the merchant account, which is `not-started`. It is carried out of scope with its `payments` columns unbuilt, because guessing the shape of a receipt record before knowing whether one exists is the wrong kind of work. If Grow does not auto-issue, receipt issuance enters F19's scope **and needs a `payments` migration**. *Owner: user (file the Grow merchant application — external-applications #3). Trigger: Grow approval; re-checked every loop iteration.*
2. **The security-checklist row "Per-tenant gateway credentials KMS-encrypted; never logged" is still unchecked when F17 merges.** Nothing is exposed by that — production forbids the fake box at boot and 0012's `provider` CHECK admits only `'fake'`, so a real credential cannot be stored anywhere until both the KMS adapter and F18 land. The row is unmet, deliberately and safely. Recorded here so F21's audit finds a ruling rather than a deviation. **Whether that deferral is acceptable is open question 2** — it is a ship-gate row, so the ruling is the user's, not the spec's. *Owner: user. Trigger: KMS adapter commit; re-derived at the F21 audit.*
3. **The KMS adapter will ship with no automated coverage.** No LocalStack, moto or KMS container is a dependency (`testcontainers[postgres,minio]` only), and adding one for ~40 lines buys more CI surface than it protects. It will be verified by a scripted manual round-trip against the real key, written into `docs/infra-runbook.md` — the pattern the F10 S3 smoke test established, which is also what caught a real `generate_presigned_post` bug that MinIO tests never saw. *Owner: team. Trigger: KMS adapter commit.*
4. **"Deposits on, gateway not connected" is an unresolved product state, and F17 is what makes it reachable.** `deposits_enabled` has had zero readers since F7; this feature gives it its first meaning. F17 ships only the owner-side warning banner. See open question 1. *Owner: user. Trigger: Gate 1, and again at F19's Gate 1.*
5. **The fake gateway marks money as received.** On staging it will flip payments to `paid` with nothing charged, and F19's flow will confirm bookings off that. This is the same accepted posture as `FakeSmsSender` under Interview Q7, bounded by three independent guards: two production boot failures and a DB CHECK. *Owner: team. Trigger: F18.*
6. **`payments` ships with seven statuses and a writer for none of them.** That is a departure from the D9 / `ScheduledMessageKind` "no speculative values" rule, taken because F19 is the next queued feature and its brief names every transition (`pending_payment` hold, sweeper expiry, webhook paid, refund-due, forfeit, manual refund). If F19's spec renames one, the correction is a single migration. *Owner: team. Trigger: F19 spec.*
7. **A non-technical owner will type merchant credentials into a form, and F17 ships no operator path to help her.** The validate-before-store ping catches a typo. It does **not** catch a *valid* credential set belonging to the wrong account — that routes real deposits to a stranger, and no technical mitigation exists short of the provider's own confirmation screen. The previous draft named "operator-assisted onboarding" as the answer; stated plainly, **that is not a capability this feature builds**. D13 makes all four routes owner-only and cookie-authenticated on the tenant subdomain, the operator is not a `staff_users` row on any tenant, and the audited CLI exposes only provision / suspend / reset-password / backfill-booking-links / list — no gateway command and no impersonation. So for the pilot, operator-assisted onboarding means **the operator sits beside the owner in her own session**, and the audit row correctly attributes the action to her. No operator gateway command is added here: pre-decided #20 is "no console-only powers", and forking the audit surface for this would be exactly what it forbids. A real operator-assisted path, if one is wanted, is F26's to design. *Owner: user. Trigger: F26's gateway-connect onboarding step.*
8. **Both gateway limiters are in-process** — they reset on deploy and do not aggregate across replicas, the standing single-instance pilot posture (F11 Risk 2, login and presign throttles). *Owner: team. Trigger: F21.*
9. **`FakeGateway.credential_fields` is a guess, and the console renders its form from it.** When F18 declares Grow's real field set, the form changes with no frontend edit — which is the design working — but any Hebrew label keyed to a fake field name becomes dead. Labels therefore fall back to the raw field name when no `gateway.field.*` key exists — wrapped in `<bdi dir="ltr" lang="en">`, since that raw name is an LTR snake_case run inside RTL Hebrew. **`GatewaySection.test.tsx` is what asserts the fallback**, not `i18n.test.ts`: the previous draft claimed the i18n test covered it, and that test cannot see a key it never renders. *Owner: team. Trigger: F18.*

## Open questions — Gate 1, the user's call

F17 is on Interview Q1's stop-list (payments surface), which is what these are for. Each is a money, product or legal decision with no codebase-consistent default; none of them blocks writing the code, and each names what the spec does in the meantime so an unanswered question is a stated posture rather than a gap.

1. **Deposits on, no gateway connected — what does the *storefront* do?** `deposits_enabled` has had zero readers since F7; F17 is what makes this state reachable. The options are: (a) the storefront hides the deposit entirely and books as if deposits were off — the boutique keeps taking bookings, and silently stops collecting; (b) it shows the deposit amount but takes no payment, which is the current disclosure behaviour and arguably a promise we do not keep; (c) appointment types requiring a deposit become unbookable, which is safe for money and hostile to a boutique who toggled a setting she did not understand. **F17 ships only the owner-side `PolicyBlockerBanner`** and changes nothing customer-facing, so the answer can land in F19 without rework — but F19 cannot start its flow without it. *Also re-asked at F19's Gate 1.*
2. **Is shipping with "per-tenant gateway credentials KMS-encrypted" unchecked acceptable?** D3 holds `KmsSecretBox` for its own commit, exactly as F11 held Twilio. Nothing is exposed — production boot-fails on the fake box and 0012's CHECK admits only `'fake'`, so no real credential can be stored anywhere until both the KMS adapter and F18 land. The question is whether that ship-gate row may stand unchecked through F17's merge, or whether the KMS adapter must come into this feature's scope. **Default if unanswered: deferred, per D3**, with Risks 2 and 3 carrying it.
3. **How long do `payments` rows live before F20 scrubs them?** D21 sets the credential side (90 days for superseded ciphertext, a pure security number) but deliberately not this one: bookkeeping-retention practice for financial records (7 years, and 10 for tax — the number pre-decided #34 already uses for employment documents) runs directly against Amendment 13's minimisation duty and the data-subject deletion right. That trade is a legal call, not a house-style one. **Default if unanswered: 7 years, matching pre-decided #10's `bookings` row**, since a payment without its booking is not a record of anything — but it needs to be a stated position, not an inherited one.
4. **A verified webhook arrives for a hold that already expired — is the money honoured or refunded?** F19's sweeper frees the seat on expiry; a late-but-genuine payment can then land against a booking whose slot is gone. Honouring it means overbooking; refusing it means holding a customer's money with nothing to show. **F17 makes the event durable and distinguishable** (`GATEWAY_LATE_SETTLEMENT` + `payments.error`, `newly_settled=False`) and does nothing else with it, so either answer is implementable in F19 without touching this port. There is no safe default here — it is the one question in this list where guessing is worse than waiting.

## Response to the adversarial review (18 findings)

Applied in full: **1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18**. The three BLOCKERs (1, 10, 11) each changed a decision rather than becoming a risk — D20, D23 and D24 respectively — and all three reuse the booking slot-claim discipline (`pg_advisory_xact_lock` → converge-on-read → index-as-backstop, and `ScheduledMessageRepository.mark`'s guarded UPDATE) rather than inventing a mechanism. Findings 8/14, 9/10 and 3/18 are the same defect seen from two lenses and are fixed once each.

Two corrections to findings that were nonetheless applied — recorded so a later reader does not inherit the reasoning along with the fix:

- **Finding 12** over-claims. It argues the two planned tests "cannot both pass"; in fact a route that branches on `is_configured` before reading `provider` satisfies both, so the spec was not self-contradictory. The fix is taken anyway, because the spec's own text specifies reading `gateway.credential_fields` *unconditionally*, and a metadata property that raises is a footgun F18 and F19 would both have to remember to avoid. D22 makes the null-provider contract structural instead.
- **Finding 6** is right that no retention period was stated for either new table and wrong that revoked DELETE blocks erasure. `UPDATE` is granted, and pre-decided #34 already establishes that erasure in this repo is field-blanking with operational history retained — so D7 and true erasure were never in conflict. The finding's further claim that merchant credential ciphertext is the owner's personal data is not accepted either: it is a business secret, and its retention is a security question with a house answer (D21, 90 days), not a data-subject-rights question. What *was* genuinely missing — the `payments` number — is a legal call and is routed to open question 3 rather than settled here.

Nothing was rejected outright. Every finding named a real defect in the reviewed draft.

## Conflicts with the authority documents (recorded, then resolved codebase-consistent)

1. **Epic brief: "per-tenant Grow credentials stored KMS-encrypted (KMS provisioned here)."** The repo has no encryption code, no `cryptography` dependency, no KMS key, and no way to test a KMS adapter in CI. This contradicts the F11 precedent the same brief instructs this feature to mirror — F11 shipped fake + unconfigured and held the real adapter for "its own small commit once the account and registered sender exist". **Taken**: port + fake + unconfigured now, `KmsSecretBox` as its own commit. Risks 2 and 3 carry it.
2. **Epic brief: F17 "verifies whether Grow auto-issues receipts."** Blocked on the unfiled merchant account. **Taken**: out of scope, Risk 1 names the owner and the trigger.
3. **ROADMAP line 52 gives F19 dependencies `7, 16, 18`** — i.e. F19 needs the real Grow adapter. Interview Q7 and `LOOP-STATE.md` both give F19 `deps: [F7, F16, F17]`. **Taken**: the interview and the loop state, which are newer and explicit ("F17 and F19 are buildable now. F18 stays parked").
4. **`.planning/specs/staff-roles-gating.md` calls its permission matrix "locked"**, and it grants shift_manager everything except terms publishing. A fully owner-only `/manage/gateway` router extends that matrix. Not a contradiction in substance — `OWNER_ONLY`'s comment in `test_staff_role_gating.py` already reserves the extension ("F51's staff router adds its rows here") — but recorded because the word "locked" appears, and because the extension is enforced by a test that must be edited in the same commit.
5. **`architecture.md:12` pins Pusher for real-time from E6** while pre-decided #23 rules no vendor. Not this feature's business; noted only so a reader does not take `architecture.md` as uniformly current.

## Decisions Log

- **D1 — Two ports: `PaymentGateway` and `SecretBox`.** Which provider takes the money and which key manager protects the credential are orthogonal, and collapsing them makes the fake gateway untestable against real KMS and the real gateway untestable without it. Declined: encrypt/decrypt methods on the gateway adapter; a module-level `encrypt()`/`decrypt()` pair with a settings branch inside (same behaviour, no seam, no fake).
- **D2 — AWS KMS as the eventual real box, with a per-tenant encryption context.** boto3 is already a dependency and the AWS account is live, so this adds none. The context (`{tenant_id, purpose}`) rides in KMS's AAD, so a ciphertext moved between tenant rows is cryptographically undecryptable — isolation on top of RLS. Declined: `cryptography`/Fernet with a key in env (a new dependency, key material in the same env dump an attacker already has, no per-tenant binding, bespoke rotation); one AWS Secrets Manager secret per tenant (gives the app `CreateSecret`, costs per tenant, still needs a mapping row, and removes RLS from the protection story); plaintext columns on the argument that "the volume is encrypted at rest" (that defends against a stolen disk, not against the SQL injection, backup leak or over-broad read the checklist row exists for).
- **D3 — `KmsSecretBox` is out of scope; F17 ships fake + unconfigured.** Exactly F11's split, and stronger here: with no merchant account there are no real credentials to protect, and production cannot store one (two boot failures plus the `provider` CHECK). Declined: shipping an untested `KmsSecretBox` now; adding LocalStack or moto to CI to test forty lines.
- **D4 — Validate before store; a rejected ping stores nothing and overwrites nothing.** A typo'd replacement must not cost a boutique its working credentials. It also removes a state from the schema — there is no `'unvalidated'` status and `last_validated_at` is `NOT NULL`. Declined: store-then-validate with `status='unvalidated'` (persists known-bad credentials and makes "connected" a lie for one round trip).
- **D5 — The credential blob is opaque JSON whose keys the adapter declares via `credential_fields`.** We have no Grow account and no documentation, so any fixed column set is a guess that a migration would have to correct. The API echoing `credential_fields` is also what lets F18 change the field set with **no frontend change**. Declined: fixed `api_key` / `merchant_id` / `secret` columns; a `JSONB` column (the value must be a single ciphertext string — structure would defeat the point).
- **D6 — One active credential row per `(tenant, provider)`; rotation soft-deletes and inserts.** The superseded row is the rotation trail an incident review needs, and the partial unique index makes "one active set" structural. Declined: UPDATE in place (destroys the trail); a full history table (the soft-delete column already is one).
- **D7 — DELETE revoked on both tables** (`REVOKE ALL` then `GRANT SELECT, INSERT, UPDATE`), the `terms_versions` precedent from 0005. A hard DELETE of a payment row destroys financial evidence, and of a credential row destroys the rotation trail. Declined: the default full-CRUD grant every other tenant table gets.
- **D8 — `provider` CHECK admits only `'fake'`.** The D9 / `ScheduledMessageKind` rule, with a security payoff on top: production cannot store a credential row at all until F18's migration widens it alongside a real adapter. Declined: pre-adding `'grow'` (speculative, and it would open exactly the window this closes).
- **D9 — F17 owns the `payments` table, not only the credentials table.** The brief instructs this feature to mirror "a service that is the single writer of the log table"; for SMS that is `message_log`, for payments it is `payments`. Without it there is no single-writer service to build and F19 would have to invent one — losing the property that no adapter and no future caller can skip the money row. Declined: leaving `payments` entirely to F19.
- **D10 — No `currency` column.** Agorot are ILS by definition, the whole codebase spells money `*_agorot`, and nothing on any roadmap is multi-currency. A column with one legal value lies about being optional. Declined: `currency TEXT NOT NULL DEFAULT 'ILS' CHECK (currency = 'ILS')` — reversible in one migration if a second currency ever appears.
- **D11 — No receipt columns.** Whether Grow auto-issues a קבלה is unverifiable today (Risk 1), and the storage shape depends on the answer. Declined: `receipt_number` / `receipt_url` now (columns nothing writes, shaped by a guess).
- **D12 — No `refund()` on the port.** F18 wraps the call, E5 #29 automates it, and at pilot volume refunds are executed by hand in Grow's console. No consumer, no method. Declined: declaring it now "so the interface is complete" — an interface with one unimplemented method is not complete, it is speculative.
- **D13 — `/manage/gateway` is owner-only in full**, and `OWNER_ONLY` in `test_staff_role_gating.py` gains its four rows. A shift manager has no relationship to the boutique's merchant account, and the read itself discloses whether the business can take money — the same reading that makes F51's staff router owner-only. Declined: admitting shift_manager to `GET` (splits one surface across two policies for no operational gain); waiting for the F21 audit to narrow it later (default-deny means narrow first).
- **D14 — `settle_from_webhook` asserts the webhook's amount against the recorded row and refuses a mismatch without marking paid.** Pre-decided #21 makes the amount assertion doctrine for refunds; a settlement is the same class of write with the same failure mode. Declined: trusting the provider's amount (a webhook is attacker-reachable input even with a valid signature, if the signing secret ever leaks).
- **D15 — Webhook replay protection is a partial unique index on `(tenant_id, provider, provider_transaction_id)`.** The 0009 argument: make it impossible for a writer that skips the check, not merely unlikely. Declined: an in-process seen-set (dies with the process, wrong across replicas); a dedicated nonce table (a second table for a uniqueness constraint the money row already carries). **Amended by D24** — the reviewed draft treated this index as the *whole* mechanism, which it cannot be: the settle path performs no insert, so two concurrent deliveries writing the same txn id to the same row never violate it. The index is the backstop behind the guarded UPDATE, exactly as 0009 describes.
- **D16 — The gateway nav item is hidden inline for non-owners.** Three lines using the `role` field the `Staff` type already carries. Declined: waiting for F51's role-filtered nav (ships a visible nav item whose every call 403s); building the general role-filtered nav table here (F51's named scope, and doing it in a payments feature would bury it).
- **D17 — No `Cache-Control: no-store` on the gateway routes.** The reason it exists on the OTP router is that the verify response carries a bearer token; nothing here carries bearer material or a secret. Adding the header to one of five `/manage` routers is drift, not defence. Declined: adding it (and normalising all five, which is F21's cross-cutting cleanup, listed there beside the throttle-error reparenting).
- **D18 — `SecretBoxNotConfiguredError` maps to the existing `GATEWAY_NOT_CONFIGURED` code and body.** Same operational fact to the owner ("deposits are unavailable") and the same remedy (contact the operator). A second wire code for one fact is what booking-comms D10 declined as "a fourth spelling of *too many attempts*". The two are still distinguishable server-side, which is where the difference matters. Declined: `SECRET_BOX_NOT_CONFIGURED` as its own code.
- **D19 — `SecretBox` lives in `app/payments/secretbox.py`.** Payments is its only consumer today. Declined: a top-level `app/crypto/` package now — when F20's PII work or F48's billing wants a box, the move is a rename, not a redesign, and inventing a package for one caller is the un-lazy thing this repo names repeatedly.

*Added at the adversarial-review revision — D20 through D26 replace decisions the reviewed draft got wrong, not new scope.*

- **D20 — Webhook *verification* credentials resolve from the newest row for `(tenant, provider)`, ignoring `deleted_at` and `status`; only the *use* path requires a live valid credential.** Verifying a signature is not authorisation to charge — it is reading evidence about money that has **already moved**. The reviewed draft resolved both through `credentials_for`, so a `disconnect` (or a `revalidate` flip to `invalid`) permanently stranded every in-flight payment: the charge succeeds at the provider, the webhook can never be verified, the row stays `pending`, F19's sweeper frees the seat, and the `webhook_secret` sits in a soft-deleted row no code path reads. That is a money-loss hole in the port contract, and F18 and F19 would both have inherited it. Two methods, two purposes, one new repository read (`newest_for_provider`) and one non-partial index. Declined: refusing `disconnect` while any `payments` row is `pending` — it inverts the incident case, because a disconnect is precisely what an owner does when a key leaks, and it would make the safe action unavailable exactly when it is needed; also a boutique with one stale `pending` row could never disconnect at all. Declined: reading the soft-deleted row opportunistically inside `credentials_for` — same method, two meanings, and every future caller has to know which one it got.
- **D21 — Retention is stated for both new tables; erasure is column blanking, never row removal.** Pre-decided #10 names neither table and F20 owns the sweeper, so leaving them outside every data class would have shipped two tables no retention job knows about. Revoked DELETE (D7) does not conflict with the checklist's "true erasure, not soft-delete" — `UPDATE` is granted and pre-decided #34 already establishes blanking-with-retained-history as the repo's erasure shape. Superseded credential ciphertext blanks at 90 days (a security number, settled here); the `payments` period is a bookkeeping-law number and goes to the user (open question 3). Declined: silently leaving both tables unclassified; deciding the `payments` number in an engineering spec.
- **D22 — `UnconfiguredGateway` answers its metadata properties and raises only on I/O.** `provider` → `None`, `credential_fields` → `frozenset()`. This is what makes `GET /manage/gateway` → 200 `configured: false` structural rather than a remembered branch, and it is a deliberate departure from `UnconfiguredMediaStorage`, which has no metadata properties and therefore settles nothing. Note `UnconfiguredSecretBox.key_ref` still raises — it has no null-safe answer, because a `key_ref` is written to a row and a wrong one is unrecoverable. Declined: raising from all five members and branching in the route (the null-provider contract then lives in a caller that F18 and F19 must each remember).
- **D23 — `open_deposit` takes the per-tenant advisory lock, converges on an existing live hold, and calls the gateway only after that read.** The `create_booking` sequence exactly: `pg_advisory_xact_lock(hashtext(tenant_id))` → read → converge → write, with the partial unique index as the backstop for a writer that skips the lock and `PaymentAlreadyHeldError` as its mapped domain error. The reviewed draft minted the hosted-page session **before** the insert that `idx_payments_booking_pending_unique` can refuse, so a double-tap left a live payable session at the provider with no row behind it — and a charge on that session matches nothing in `settle_from_webhook`. Returning the existing hold is also the idempotent read F19's retry path wants anyway, so the correct ordering is cheaper than the wrong one. Declined: catching `IntegrityError` and retrying (a failed flush aborts the Postgres transaction — the same reason `create_booking` reads rather than catches); leaving the collision to surface as a 500, which contradicts this spec's own Goal.
- **D24 — Settlement is one guarded UPDATE (`WHERE status='pending'`) and returns `newly_settled`.** The reviewed draft's read-then-write was only *sequentially* idempotent: two concurrent redeliveries both see no settled row, both match the same row by session id, both write the same txn id to it, and the unique index — which has no insert to refuse on this path — never fires. `ScheduledMessageRepository.mark` already solves this in-repo. `Settlement(payment, newly_settled)` is `BookingClaim`'s `created` flag for `BookingClaim`'s reason: F19 gates a booking-confirm and an F16 SMS on it, and a bare row cannot carry the distinction. This also corrects the draft's reading of 0009 — its comment says the service converges under the lock and the index is the backstop for a writer that skips it, not that the index replaces application logic. Declined: relying on the unique index alone; a `SELECT … FOR UPDATE` then write (two statements where one does it, and it still needs the rowcount branch for the `expired` case).
- **D25 — A failed webhook signature is `GatewayWebhookInvalidError` → 400, never `GatewayUnavailableError` → 503.** An HMAC mismatch is an authentication failure, not a provider outage: 503 invites a retry of a forgery, buries the event among real outages in logs and alerting, and leaves the checklist row "webhook signature verification + replay protection" unprovable from outside. It also gets an audit action, so an attempt leaves a row. Declined: reusing `GatewayUnavailableError` for a fifth spelling of "something went wrong" — the two are operationally opposite and the remedies share nothing.
- **D26 — `revalidate` takes `actor_id`, audits every outcome, and flips `status='invalid'` only on `GatewayCredentialsRejectedError`.** Three corrections in one method. `AuditLogRepository.record` defaults `actor_id=None`, so omitting it is silent rather than a type error and an owner tap would be indistinguishable from a system sweep. Auditing only the failure loses the `invalid → valid` recovery — the transition that re-enables money movement, and the one an incident review most wants to place in time. And a `GatewayUnavailableError` from the ping must leave `status` *and* `last_validated_at` untouched: the reviewed draft wrote the ping's result unconditionally, so a transient provider blip during a "Validate now" tap would take the boutique's deposits offline over a working merchant account. That is the same asymmetry D4 already argues for a decrypt failure, for the same reason. Declined: a third `'unknown'` status for the unreachable case (a state D4 spent an argument removing, reintroduced for a condition that is by definition temporary).
