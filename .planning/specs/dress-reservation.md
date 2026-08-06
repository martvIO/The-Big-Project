# Spec: Feature 28 — Date-bound dress reservation semantics (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals** (Q1: F28 touches neither payments, refunds, privacy-law text nor billing — it self-approves; the named exceptions are F17/F18/F19/F20/F29/F48. No new PII is stored — see D7) · **Epic**: E5 · **Effort**: M
**Depends on**: F8 (dresses/variants, the manual `reserved` flag), F13 (booking claim, dress snapshot path) · **Feeds**: Q9's "absorb sale and made-to-order later" — this table is where they land
**Settles**: the epic's open product question. LOOP-STATE F28 note is authoritative: **Q9 decided RENTAL** — a real date range (wedding date + cleaning/return buffer) with an overlap check, so the storefront can say "unavailable 12–18 Aug" and still take fittings on other dates.

---

## Problem

E2 #8 shipped `dresses.reserved` as a manual, date-less boolean — the owner ticks it, the storefront badges "הוזמן", and she must remember to untick it when the gown comes back. Under Q9's rental reading that flag answers the wrong question: a rented dress is not "reserved" in general, it is *away for specific dates* and fully available around them. Today the owner either over-blocks (badge scares off every bride) or under-blocks (two rentals collide on one gown, or a fitting is booked for a dress that is at someone else's wedding).

## Goal

The owner records date-bound reservations on a dress in the catalog editor; overlapping reservations for the same dress are structurally rejected; the storefront dress page states the booked-out ranges in plain Hebrew (no exclamation marks) while the booking CTA stays live; an item-based fitting whose date falls inside a window is refused with a "pick another date" error — and the slot engine, walk-ins, and non-item bookings are untouched. Hebrew-first RTL, `ar` keys untranslated (Q3/#47), axe zero-violation (IS 5568 / WCAG 2.0 AA).

## Conflicts between the brief and shipped reality (recorded)

1. **Epic brief: "blocked on pilot product decision"** — unblocked. LOOP-STATE's F28 note + interview Q9 settle it: RENTAL.
2. **Catalog spec's Feeds note: "date-bound reservation supersedes the manual `reserved` flag"** — supersession is read as *ownership of the semantics*, not deletion of the column. The boolean is **kept** as the manual, date-less hold (D5): under rental it still names a real state ("unavailable indefinitely, keep showing her"), it has shipped storefront/manage surfaces and tests, and migrating `reserved=true` rows into reservations would force a nullable/open-ended `ends_on` onto every future row for the sake of a shim. No data migration; the `dress.py` model comment is reworded from "supersedes" to "narrows".
3. **Epic brief: "reservation windows on a dress/variant"** — resolved to **per dress** (D1). Bookings snapshot `dress_id + dress_size`, the badge and flag are dress-level, and `dress_variants` are size buckets with quantities, not identifiable physical units. Per-variant granularity is the recorded ceiling, not the feature.

## What already exists to build on (verified against code)

- **`dresses.reserved`** (`models/dress.py`): boolean, server_default false; rendered as `catalog.reserved`/`dress.reserved` = "הוזמן" badges in the storefront (`storefront/router.py` `public_dress`/`public_dress_detail`), a checkbox in `DressEditor.tsx` (helper: "סימון ידני, ללא תאריך…"). DressPage test pins that **the booking CTA stays usable on a reserved dress**.
- **Booking claim** (`booking/service.py`): item path loads the dress + proves the size inside the claim; `pg_advisory_xact_lock(hashtext(tenant_id))` serializes everything per tenant (step 4); deposit (`pending_payment`) rides the same claim. Walk-ins (`owner.py create_walk_in`) carry **no dress**. `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")` lives in `storefront/validation.py`.
- **Catalog manage surface** (`catalog/router.py`): `/manage` prefix, `require_role(OWNER, SHIFT_MANAGER)` router-wide, REST-ish paths with path params (`/dresses/{id}/variants` PUT, media POST/DELETE), `tenant_session` + repositories + `AuditAction` rows in `catalog/service.py`.
- **Migrations**: raw-SQL house style (`_STANDARD` block, `update_updated_at` trigger, grants, `enable_tenant_rls`); **no EXCLUDE/daterange/btree_gist precedent anywhere** — concurrency guards are the tenant advisory lock plus partial unique btree indexes.
- **PII precedent** (`models/alteration_ticket.py` + `privacy/service.py`): `alteration_tickets.customer_id` is a **pointer, not a snapshot** — erase scrubs the `customers` row and every pointer renders the scrubbed name; F20's export sweep covers subject/bookings/messages/queue-tickets/terms and deliberately not pointer-keyed operational tables.
- **Head**: 0001–0025 merged; **F22 holds 0026 in a live worktree and F24/F25 plans are queued ahead** — this migration is **head+1 at build time**, renumber at rebase.

## Scope

**IN**
- `dress_reservations` table (per dress, date range, optional CRM pointer, notes) + migration.
- Owner CRUD (create/list/delete) in the catalog editor, audit-logged.
- Overlap rejection at write time under the tenant advisory lock.
- Storefront dress page: current/future unavailable ranges, stated copy, CTA untouched.
- Booking-claim check: item-based storefront claim inside a window → 409.
- FE prefill: wedding date + buffer constant fills the range; owner edits dates freely.

**OUT**
- Rental payments, pricing, deposits-for-rentals, contracts.
- Availability calendar UI beyond the date-range fields (no calendar widget, no greyed-out picker dates).
- Storefront-side reservation requests — the **owner** records reservations; brides phone the boutique.
- Per-variant/physical-unit granularity (ceiling recorded in D1).
- Enforcement on owner paths: walk-ins (no dress by construction), owner reschedule of item bookings — the owner is the authority the check protects; blocking her would force her to delete a reservation to make an exception she already decided.
- Slot engine, grid, waitlist (F22/F23), fitting-room/floor surfaces (`fitting_assignment_dress` is day-of in-store state, untouched).
- Removing or migrating the `reserved` boolean (kept, D5). A feature-toggle row (F27 can add one later).
- Reservation *edit* endpoint — delete + re-add covers a postponed wedding at pilot scale (ceiling recorded).

## Design

### D1 — Granularity: per dress

A reservation binds to `dress_id` alone. Rationale in Conflicts #3. `# ponytail:` per-variant (or per-physical-unit) reservations if a boutique with multiples per size ever rents both at once — the table gains a nullable `variant_id` then, and nothing here blocks it.

### D2 — Data model (one migration, head+1 at build time)

Raw-SQL house style (`_STANDARD`, trigger, grants, `enable_tenant_rls`):

```sql
CREATE TABLE dress_reservations (
    {_STANDARD},
    dress_id    UUID NOT NULL,          -- no FK, house rule; validated in app
    starts_on   DATE NOT NULL,          -- first unavailable local (Asia/Jerusalem) day
    ends_on     DATE NOT NULL,          -- last unavailable day (wedding + buffer), inclusive
    customer_id UUID,                   -- POINTER to customers, never a snapshot (D7)
    notes       TEXT,
    CHECK (ends_on >= starts_on),
    CHECK (ends_on - starts_on <= 3650) -- 10× MAX_RESERVATION_SPAN_DAYS, 0005 convention
);
CREATE INDEX idx_dress_reservations_dress
    ON dress_reservations (tenant_id, dress_id, ends_on) WHERE deleted_at IS NULL;
```

Dates, not timestamps: a rental leaves and returns on *days*; the boutique operates in one timezone (`BOUTIQUE_TIMEZONE`), and DATE columns make the overlap arithmetic exact and DST-proof. Inclusive `ends_on`: "unavailable 12–18" means the 18th is unavailable too.

### D3 — Overlap rule and concurrency

- **Predicate** (inclusive dates): existing `[a1,a2]` conflicts with new `[b1,b2]` iff `a1 <= b2 AND b1 <= a2`, among live rows (`deleted_at IS NULL`) of the same dress. Adjacent ranges (`ends_on` 18, next `starts_on` 19) are **legal** — the buffer already inside `ends_on` is the cleaning gap; same-day touch (18/18) is a conflict.
- **Write path**: create takes `pg_advisory_xact_lock(hashtext(tenant_id))` — the **same key the booking claim takes** — then runs the overlap SELECT, then inserts. Overlap → `409 RESERVATION_OVERLAP` carrying the conflicting range in `details` so the manage UI can say *which* dates collide.
- **No structural backstop**: range overlap is not expressible as a partial unique btree index, and the repo has no btree_gist/EXCLUDE precedent. The lock is sufficient — writers are staff sessions on a CSRF-fenced console, not the anonymous internet. `# ponytail: advisory lock only; EXCLUDE USING gist (btree_gist) is the upgrade if reservation writers ever multiply.`
- **Validation** (`catalog/validation.py`): `ends_on >= starts_on`, `MAX_RESERVATION_SPAN_DAYS = 365`, `MAX_RESERVATION_NOTES_LENGTH = 500` (booking-notes precedent), `customer_id` must resolve to a live, non-erased customer when given (the walk-in's D3d rule: an erased subject is a 404, no resurrected processing relationship).

### D4 — Interaction with the booking claim (the only enforcement point)

Inside `create_booking`'s **already-locked** section, on the item path only: one query — a live reservation for `dress_id` whose range contains `starts_at.astimezone(BOUTIQUE_TIMEZONE).date()` → `409 DRESS_UNAVAILABLE` ("השמלה אינה זמינה בתאריך שנבחר. אפשר לבחור תאריך אחר."). Placed after the advisory lock so an owner recording a rental and a bride claiming a fitting the same second serialize — both writers hold the same key.

- Deposit path (`pending_payment`) inherits the check by riding the same claim.
- Distinct from `SLOT_UNAVAILABLE` deliberately: the remedy differs (another *date* for this dress, not another time), and the windows are public on the dress page, so no oracle is opened.
- Non-item bookings at the same instant are untouched; the grid and `booked` counts never see reservations. **Slot engine: zero lines.**

### D5 — The old flag: kept as the manual, date-less hold

`dresses.reserved` keeps its exact shipped behaviour: owner checkbox, storefront badge, CTA live. It is now *narrowed* to "unavailable indefinitely, no dates" (sold/long-term hold under the rental reading). No precedence rule is needed — the flag drives the badge, reservations drive the date lines and the claim check; the two states are orthogonal exactly as the E2 #8 binding decision argued (three non-exclusive flags, no enum). The date-bound badge question is deliberately answered **no**: a dress rented 12–18 Aug is *available* to a bride whose wedding is in October — badging the card "הוזמן" for a passing window would drive her away from a dress she can have. Migration path recorded: none required; `reserved=true` rows behave identically before and after.

### D6 — Storefront presentation (dress page only)

- `GET /storefront/dresses/{id}` (`StorefrontDetail`) gains `unavailable_ranges: [{starts_on, ends_on}]` — live rows with `ends_on >= today` (boutique-local), ascending, whole list (a gown's future rentals are naturally few). List/card endpoints unchanged.
- `DressPage.tsx` renders, between sizes and the CTA, a plain information block when ranges exist: heading `dress.reservedDatesHeading` = "מוזמנת בתאריכים" and one line per range "12–18 באוגוסט" (Intl.DateTimeFormat `he-IL`, day + month, year appended when it differs from the current one; en-dash, `<bdi>`), followed by `dress.reservedDatesNote` = "בשאר התאריכים אפשר לקבוע מדידה." — Q9's rule spelled as copy. **No exclamation marks** (pre-decided #5). CTA stays exactly as the shipped reserved-dress test pins it.
- `BookPage` maps the new `DRESS_UNAVAILABLE` code through the house error handling → `booking.errors.dressUnavailable` ("השמלה אינה זמינה בתאריך שנבחר. אפשר לבחור תאריך אחר."). No picker changes (OUT).

### D7 — Who the reservation names: a CRM pointer, never PII text

`customer_id` is optional and follows the `alteration_tickets` precedent exactly: a pointer resolved to the live `customers` row at render time. **No name/phone TEXT columns** — an erase scrubs the customer row and every reservation renders the scrubbed name automatically; F20's export/erase surfaces need **zero changes** (pointer-keyed operational tables are outside the export sweep, the shipped F20 decision `alteration_tickets` already lives under — recorded as a shared, known posture for any future counsel pass, not a new gap). The manage form offers the existing CRM customer search as an optional picker; a renter not in CRM goes in `notes` free text — owner-authored operational text, the same accepted class as `bookings.notes` (bounded, rendered as text, never HTML).

### D8 — Manage UI (catalog editor)

- **Where**: a "הזמנות לתאריך" pane inside `DressEditor.tsx`, beside variants and gallery — edit mode only, disabled in create mode with the existing hint (shipped precedent: variants/gallery panes).
- **Pane**: list of live reservations (range · customer name when linked · notes · delete button), newest `starts_on` first; add form: wedding-date `<input type="date">` → prefills `starts_on = date`, `ends_on = date + RESERVATION_BUFFER_DAYS` (**FE named constant, 5** — Q9's cleaning/return buffer; a tenant setting is the recorded upgrade if a boutique wants a different default), both dates then freely editable; optional customer picker (existing CRM list search); notes field. Overlap 409 renders the conflicting range inline. Buttons `size="md"` (F-W1: 36px `sm` fails the 44px touch floor). Copy inline Hebrew like the rest of the manage app; no exclamation marks.
- **API** (`catalog/router.py`, same router → `OWNER`/`SHIFT_MANAGER` gating and `_no_store` inherited):

| Endpoint | Purpose |
|---|---|
| `GET /manage/dresses/{dress_id}/reservations` | live rows `{id, starts_on, ends_on, customer_id, customer_name, notes, created_at}` |
| `POST /manage/dresses/{dress_id}/reservations` | create `{starts_on, ends_on, customer_id?, notes?}` → 201; `409 RESERVATION_OVERLAP`; 404 unknown/archived dress |
| `DELETE /manage/dresses/{dress_id}/reservations/{reservation_id}` | soft delete → frees the window |

- **Audit**: `AuditAction.DRESS_RESERVATION_CREATED` / `DRESS_RESERVATION_DELETED` (plain-TEXT action column, no migration needed — shipped pattern). `details` carry the range and the two ids, **never a name or phone** (the walk-in audit rule).
- Service methods live in `CatalogService` beside the variant/media families: `tenant_session`, repository (`db/repositories/dress_reservations.py`), audit in-transaction.

## Frontend changes (summary, both apps)

- **storefront** (`Frontend/apps/storefront/src`): `api.ts` — `unavailable_ranges` on `StorefrontDetail`, `DRESS_UNAVAILABLE` code mapping; `DressPage.tsx` — the D6 block; i18n `he.ts`/`ar.ts` (`ar` untranslated) — `dress.reservedDatesHeading`, `dress.reservedDatesNote`, `booking.errors.dressUnavailable`.
- **manage** (`Frontend/apps/manage/src`): `api.ts` — three reservation calls + types; `DressEditor.tsx` — the D8 pane (new `ReservationsPane` component beside `VariantMatrix`/`MediaGallery`); inline Hebrew copy; existing `reserved` checkbox helper reworded to point date-bound cases at the new pane.

## Test plan

- **Fast (unit)**: overlap predicate edges — adjacent ranges legal (18|19), same-day boundary 409 (18|18), contained, spanning, identical, disjoint; validation — `ends_on < starts_on` 400, span > 365 400, notes bound, erased/unknown `customer_id` 404; claim date-containment — window edges inclusive both ends, and the **Jerusalem-vs-UTC boundary instant** (a 22:00 UTC booking is the *next* local day — must compare local date, not UTC date); FE unit — buffer prefill arithmetic (`date + 5`), range formatting (same-month, cross-month, cross-year).
- **db-marked**: RLS isolation on `dress_reservations` (house suite pattern); create→list→delete lifecycle + audit rows (details carry no name/phone); **concurrency proof** (NullPool + `asyncio.gather`, the F13 precedent): two concurrent creates with overlapping ranges → exactly one 201 and one `RESERVATION_OVERLAP`; concurrent reservation-create vs item-claim for the same dress-date → never both succeed; item claim inside window → `DRESS_UNAVAILABLE`, outside → 201, non-item claim same instant → 201; deposit-path claim inherits the check; soft-deleted reservation frees both the overlap and the claim; storefront detail returns only current/future ranges ascending, past rows excluded; archived dress 404 on all three endpoints; migration up/down round-trip; `test_exactly_one_migration_head` after rebase.
- **e2e (Playwright + axe)**: manage (`manage.spec.ts` pattern) — open a dress, add a reservation via the date inputs, row appears, overlapping add shows the inline conflict, delete clears it; storefront (`storefront.spec.ts` interception fixtures, route map extended) — dress page shows the range block with the fittings note, CTA still opens booking; **axe zero-violation** on the editor pane and the dress page with ranges; RTL rendering of the date lines (`<bdi>`).
- **Fixtures**: e2e route-map stubs for the three manage endpoints + widened dress-detail stub; db fixtures — a dress with past/current/future reservations.

## Traps (for the plan)

- Migration number is **head+1 at build time** — F22 holds 0026 in a live worktree, F24/F25 plans are queued ahead; renumber at rebase (`.memory/parallel-alembic-numbering`), then re-run the head test.
- `git add` pathspecs lowercase (`backend/…`, `frontend/…`), file reads capitalized.
- Compare **boutique-local** dates in the claim check, never `starts_at.date()` in UTC.
- The claim check goes **after** the advisory lock, and reservation create must take the **same lock key** — otherwise the serialization argument is fiction.
- Do not touch `public_dress` (card shape) — only the detail projection widens.
- `customer_id` in audit `details` only — never resolve a name into an audit row.

## Decisions log

| # | Decision | Basis |
|---|---|---|
| D1 | Per-dress granularity | bookings/badge/flag are dress-level; variants are stock buckets |
| D2 | DATE range, inclusive `ends_on`, CHECK + 10× span ceiling | one-timezone boutique; DST-proof arithmetic; 0005 convention |
| D3 | Overlap check in service under the tenant advisory lock; adjacent legal, touch is conflict; no EXCLUDE | no btree_gist precedent; writers are staff-only; F13 lock key reused |
| D4 | Enforcement only on the storefront item claim, inside the lock; distinct `DRESS_UNAVAILABLE` 409 | slot engine untouched; remedy differs from `SLOT_UNAVAILABLE`; windows are public |
| D5 | Keep `dresses.reserved` as the manual date-less hold; no data migration | shipped surfaces + tests; open-ended `ends_on` shim would poison the range model |
| D6 | Dress page states ranges + "other dates" note; card badge never date-aware; CTA untouched | Q9 verbatim; a passing window must not repel an October bride |
| D7 | Optional `customer_id` pointer, no PII text columns, F20 untouched | alteration-tickets precedent; erase-safe by construction |
| D8 | CRUD pane in `DressEditor`, create+delete only, FE buffer prefill constant (5) | shipped pane precedent; delete+re-add covers postponement at pilot scale |

## Open questions (non-blocking)

- `RESERVATION_BUFFER_DAYS = 5` is a guess at the cleaning/return norm — confirm with the pilot; promote to a tenant setting only if a boutique asks.
- Reservation *edit* (postponed weddings) — ships as delete + re-add; add PATCH if the pilot does it weekly.
- Whether F27's toggle matrix should carry a "date reservations" row once it ships — F27's spec owns that.
