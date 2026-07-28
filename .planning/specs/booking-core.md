# Spec: Feature 13 — Booking Core API (Epic E3)

**Created**: 2026-07-28 · **Status**: draft — awaiting Gate 1 · **Epic**: E3 Feature 13 · **Effort**: L
**Depends on**: E3 #11 (OTP verification token, `NotificationService`), E3 #12 (the slot engine and its grid), E2 #7 (appointment types, terms versions), E2 #8 (dresses, for the item-based path) — branches off `main` · **Feeds**: E3 #14 (the UI drives this API), E3 #15 (owner management reads and transitions these rows), E3 #16 (every lifecycle send hangs off a booking), E4 (`pending_payment` widens the status set)

## Problem

Everything around a booking now exists — verified phones, a slot grid, appointment types, versioned terms, a dress catalog — and nothing writes one down. This is the feature where the product stops being a brochure.

It is also the feature where getting it wrong is expensive in a way the others are not. A double-booked slot means two brides in one fitting room on a Sunday morning. A booking taken against an unverified phone strands a paying customer behind an SMS link that can never reach her. A booking that does not capture which terms version the customer accepted leaves the boutique with no defensible answer when a deposit is disputed in E4.

So the whole feature reduces to three invariants that must hold **structurally**, not by careful coding:

1. A slot cannot be oversold, under concurrency, ever.
2. A customer record exists only for a phone whose possession was proven.
3. The terms text the customer actually saw is recoverable years later.

## Goal

`POST /storefront/bookings` with a verified phone, a slot the grid actually offers, an appointment type, an accepted terms version and — on the item-based path — a dress, returns a confirmed booking. Two customers racing for the last place at 14:30 produce exactly one booking and one `409`, proven by a concurrency test against real Postgres. The same endpoint at capacity 3 produces exactly three bookings and then a `409`. And `GET /storefront/slots` stops lying: F12's `booked={}` seam becomes a real per-instant count in the same PR that creates the rows it counts.

## Design

### Data (migration 0008)

```sql
CREATE TABLE customers (
    {_STANDARD},
    phone TEXT NOT NULL,          -- E.164, normalize_israeli_mobile's output
    name TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_customers_tenant_phone_unique
    ON customers (tenant_id, phone) WHERE deleted_at IS NULL;

CREATE TABLE bookings (
    {_STANDARD},
    customer_id UUID NOT NULL,            -- no FK (house rule)
    appointment_type_id UUID NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    seat_index INTEGER NOT NULL CHECK (seat_index >= 1 AND seat_index <= 1000),
    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed','cancelled','no_show','completed')),
    attendance_confirmed_at TIMESTAMPTZ,
    terms_version_accepted INTEGER NOT NULL CHECK (terms_version_accepted > 0),
    terms_accepted_at TIMESTAMPTZ NOT NULL,
    appointment_type_name TEXT NOT NULL,  -- snapshot
    dress_id UUID,                        -- item-based path only
    dress_name TEXT,
    dress_size TEXT,
    notes TEXT
);
CREATE UNIQUE INDEX idx_bookings_slot_seat_unique
    ON bookings (tenant_id, starts_at, seat_index)
    WHERE deleted_at IS NULL AND status <> 'cancelled';
CREATE INDEX idx_bookings_tenant_starts
    ON bookings (tenant_id, starts_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_bookings_tenant_customer
    ON bookings (tenant_id, customer_id) WHERE deleted_at IS NULL;
```

> **Addendum (implementation, Gate 3.5):** `idx_bookings_tenant_customer` was
> added ahead of its consumers — F15's owner list and F16's reminder sweep both
> read a tenant's bookings by customer, and without it that is a full scan per
> owner page. Recorded here so the migration and this document stay in sync.

**`seat_index` is what makes the guard structural at any capacity.** A partial unique index on `(tenant, starts_at)` alone can only express capacity 1; adding the seat number expresses every capacity with the same one index. The `<= 1000` CHECK is the 0005 absurdity-ceiling convention against `MAX_RULE_CAPACITY`, not a policy.

**`status <> 'cancelled'` in the predicate, not `= 'confirmed'`.** A no-show or completed booking still occupied its seat; only a cancellation frees it. This is also what keeps the index correct when E4 adds `pending_payment` — a held seat is an occupied seat, and E4 widens the CHECK without touching the index.

**Snapshots are columns, not joins.** `appointment_type_name`, `dress_name` and `dress_size` are copied at booking time because the owner may rename a type or archive a dress, and a booking must render as what the customer agreed to. `dress_id` is kept alongside so the image can be resolved at read time — storing a storage key would duplicate the media lifecycle and storing a presigned URL would store something that expires.

**Terms are captured as a version number plus a timestamp, never as text.** `terms_versions` is append-only by DB grant (0005), so the number is a permanent pointer to the exact text. Copying the text into every booking would be the same evidence at many times the size.

### The claim — `app/booking/service.py`

The whole feature's correctness lives in one method. In order, inside a single `tenant_session`:

1. **Consume the verification token** (`OtpService.consume_verification`, the session-taking method F11 built for exactly this). Fails → `403 PHONE_NOT_VERIFIED`. This runs **first**: a caller who cannot prove the phone gets no further, and no lock is taken on their behalf.
2. **Load the appointment type** (must be active) and the **current terms version**. Unknown type → 404. Requested `terms_version` ≠ current → `409 TERMS_STALE`, because accepting a superseded policy is not acceptance.
3. **Load the dress** on the item-based path (must be active) and snapshot name; the size must be one of its active variants. Unknown/archived → 404.
4. **`pg_advisory_xact_lock(hashtext(tenant_id))`** — the `replace_weekly_rules` precedent. Everything from here to COMMIT is serialized per tenant.
5. **Re-materialize the grid** for `starts_at`'s own date and assert the requested instant is in it. This is not a formality: without it a caller books 03:00 on a closed Saturday by posting an arbitrary timestamp, and the picker is not a security boundary. The engine is fed the real `booked` counts, so this check also enforces capacity.
6. **Upsert the customer** by `(tenant, phone)` — attach if present, insert if not, updating the name.
7. **Insert the booking** with `seat_index = booked_count + 1`.

The advisory lock is the primary control and the unique index is the structural backstop: an `IntegrityError` on the index becomes `409 SLOT_UNAVAILABLE`, indistinguishable from losing the count check. `# ponytail: one lock per tenant serializes all claims; per-slot lock keys if pilot throughput ever cares.`

### The API — a sibling router, `app/booking/router.py`

`APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])`, registered after the read router. The F11 precedent, for the F11 reason: the storefront read router is contractually GET-only and this route mutates.

`POST /storefront/bookings`:
```json
{ "phone": "050-123-4567", "verification_token": "…", "name": "…",
  "appointment_type_id": "…", "starts_at": "2026-08-02T07:00:00Z",
  "terms_version": 3, "dress_id": "…", "dress_size": "38", "notes": "…" }
```
→ `201` with `{ id, starts_at, status, appointment_type_name, dress_name, dress_size }`.

**Anonymous and cookie-blind, like every other public route.** The credential is the verification token, which is single-use and bound to the phone that earned it. CSRF remains structurally N/A (no cookie, no ambient credential); the controls are tenant-from-Host, OTP possession, and the per-tenant create budget below.

**A per-tenant create throttle**, `Settings`-tunable like every other: `booking_create_max_per_window` (60) / `booking_create_window_seconds` (3600). Sized far above a pilot boutique's real volume — it is a runaway brake, not a defence, and the real cost gate is that every booking needs an OTP that was itself rate-limited.

### F12's seam closes here

`StorefrontService.list_slots` stops passing `booked={}` and passes a real `{starts_at: count}` from `BookingsRepository.count_by_start(window)`. One repository method, one line changed at the call site, zero lines in the engine — which is what the seam existed for. The F12 tests asserting the empty literal are updated in the same commit, so the change is a visible diff.

### Errors

| Error | Status | Code |
|---|---|---|
| `PhoneNotVerifiedError` | 403 | `PHONE_NOT_VERIFIED` — "Verify your phone number and try again." |
| `SlotUnavailableError` | 409 | `SLOT_UNAVAILABLE` — "That time was just taken. Choose another." |
| `TermsStaleError` | 409 | `TERMS_STALE` — "The booking terms changed. Review and accept them again." |
| unknown type / dress / size | 404 | `NOT_FOUND` (existing body) |
| `BookingThrottledError` | 429 | `TOO_MANY_ATTEMPTS` (existing body) |
| validation | 400 | `VALIDATION_ERROR` (existing handler) |

`SLOT_UNAVAILABLE` deliberately does not distinguish "taken" from "never offered": both mean *pick another time*, and the difference would tell a prober the shape of the boutique's grid.

### Named constants (`app/booking/validation.py`)

| Constant | Value | Why |
|---|---|---|
| `MAX_CUSTOMER_NAME_LENGTH` | 80 | a human name, not an essay; mirrors the catalog's name bounds |
| `MAX_BOOKING_NOTES_LENGTH` | 500 | "I'm bringing my mother and two sisters" — a paragraph, not a document |
| `MAX_SEAT_INDEX` | 1000 | matches `MAX_RULE_CAPACITY`; the DB CHECK is 10× nothing here because capacity itself is already the bound |

## Frontend changes

None. F13 is backend-only; F14 builds the flow against this contract. `packages/api-client`'s codegen adoption is F14's first commit, per its own OWNER note.

## Testing

**The headline is the concurrency proof** (`db`-marked, NullPool + `asyncio.gather`, copying `test_boutique_service.py::test_concurrent_weekly_replaces_never_union`):
- capacity 1, two concurrent creates for the same instant → exactly one 201 and one `SlotUnavailableError`;
- capacity 3, five concurrent creates → exactly three succeed, `seat_index` is `{1,2,3}` with no duplicates;
- a cancelled booking frees its seat and the slot is claimable again.

Also `db`-marked: an arbitrary off-grid `starts_at` (03:00, a closed day, a past instant) is `SLOT_UNAVAILABLE`; an unverified/expired/foreign-phone token is `PHONE_NOT_VERIFIED` and writes nothing; a stale terms version is `TERMS_STALE`; the customer upsert attaches rather than duplicating on a second booking; dress snapshot fields are frozen against a later rename; archived dress/type is 404; RLS isolation for both new tables; migration 0008 up/down round-trip.

Fast: request-shape validation, the status/seat constants, error mapping, route-table additions (the new POST joins the shadowing guard; the cookie-blindness assertion covers it).

## Out of scope

The manage/cancel token and all SMS sends (F16 — a booking created here sends nothing yet), owner-side transitions and reschedule (F15), any UI (F14), deposits and `pending_payment` (E4), waitlist (E5).

## Risks

1. **A booking currently sends no SMS.** Between this PR and F16 a customer gets a 201 and silence. Nothing links to the endpoint until F14, and F16 is the next PR — the same ordering argument F12 used for its seam, and recorded here so it is a decision rather than an oversight.
2. **The per-tenant advisory lock serializes every claim for a boutique.** At pilot volume this is free; a boutique taking hundreds of concurrent bookings would want per-slot keys. Marked in-code with the upgrade path.
3. **`notes` is free customer text that reaches the owner's console.** It is length-bounded and rendered as text, never HTML — but it is the first customer-authored string in the product, and F15 must not innerHTML it.
