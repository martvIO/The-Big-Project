# Spec: F50 — Owner-created bookings, the walk-in half (Epic E3-carveout, phase SMC-6)

**Created**: 2026-08-04 · **Status**: **Gate 1 self-approved under Interview Q1** — the stop-list is enumerated (F17, F18, F19, F20, F29, F48) and F50 is not on it. It is not a money surface (no deposit, no payment row, no gateway read) and, **as designed below, not a legal one either: this path collects no personal data from anybody**, which is the entire reason it self-approves rather than parking on counsel's Hebrew. That conclusion is load-bearing and D3 is where it is argued; if the design is ever changed to let the dialog *create* a customer, the gate reopens. · **Epic**: `.planning/epics/shift-manager-console.md` (SMC-6), carved from `.planning/epics/interview-2026-07-30.md` Q6 · **Effort**: **M** — one migration that widens two NOT NULLs and adds one column plus two named CHECKs, one endpoint on a router that already exists, one repository writer, one `AuditAction` member, one dialog on a board that already exists — and **seven ripple sites the nullability change breaks, one of which is a live 500 on a shipped privacy route** — plus five typed test factories the new required `source` field breaks before a single test runs.
**Revised 2026-08-04** after adversarial review: 11 findings, 9 applied in full, 2 applied with a replaced fix, 1 sub-claim rejected on the record. See *Findings raised and REJECTED*. The changes: D1 gained a `downgrade()` and a ruling on what it does to walk-in rows; D1b's site 6 was two interfaces pretending to be one; D2's "never in the feed" gained its one real exception (Risk 8); D9's `refresh()` needed a terminal guard `reschedule()` did not; the frontend section named the wrong test file, missed a fourth test file, and would not have compiled.
**Depends on**: **F15** (`owner_router.py`'s routes, `OwnerBookingService`, `OwnerBookingRow`/`OwnerBookingDetail`, `_row_fields`, `BookingDetail.tsx`) · **F34** (`bookings.checked_in_at`, `BoardSection.tsx`, the list→patch contract) · **F53** (`GET /manage/customers?q=` — the customer picker this feature does not build) · **F20** (`0024_privacy_consent.py`, `MarketingConsentSource`, the §11 collection-point table) — all merged.
**Feeds**: nothing. **The remote/scheduled owner-create half stays open in `LOOP-STATE.md`'s F50 entry after this merges** — see *Out of scope*, which states exactly what it still needs.

---

## Problem

Two brides are standing at the counter and the console can do nothing for either.

**The first was cancelled by a mis-tap.** F15 made `cancelled` terminal, on purpose and with a proof: reviving a cancelled row re-enters both partial unique indexes against a seat that may since have been sold, so the UPDATE fails with an `IntegrityError` in the common case and silently double-books in the race (`owner-booking-management.md:127`). Its Risk 1 accepted the consequence in writing — "a mis-tapped cancel has no in-product remedy … owner-created bookings are out of scope, so the owner's recovery is to have the customer rebook through the storefront" — and named the trigger as *this spec, which the loop must still queue*. The bride is in the shop. Sending her home to re-run a six-step storefront flow with an OTP is not a remedy.

**The second simply arrived** — for a fitting nobody entered, or as the overflow of a walk-in the queue already holds. She is physically in the building and the board, whose entire job is answering *is she here yet*, has no row to put her on. Everything the floor does downstream is keyed to a booking or a queue ticket: F36 claims a room (`ClaimRoomRequest.booking_id`), F41 opens an alteration ticket, F58 dispatches. A person with neither is invisible to all of it.

**And the reason F15 refused is real, not ceremonial.** Interview Q6, verbatim: "A booking the owner creates has no bride-verified phone and no accepted terms, so the SMS control link would target an unverified number — new legal and security ground that earns its own spec, not a corner of F15." Both halves of that are true of a booking created from *nothing*. Neither is true of a booking created for a customer the boutique already holds — and `Customer`'s own docstring is why: rows exist "ONLY after OTP verification proved possession of that number" (`models/customer.py:12-15`). **That single sentence is the hinge of this whole feature**, and it is what lets the walk-in half ship without touching consent, terms text, or a word of Hebrew in front of a member of the public.

What remains dangerous is narrower and entirely mechanical: `bookings.terms_version_accepted` and `terms_accepted_at` are `NOT NULL` today, so a booking with no terms evidence is *not currently representable*, and the only two ways to create one are to lie (stamp the current version, manufacturing legal evidence nobody gave) or to widen the schema. This spec widens the schema, and spends most of its length on what that widening breaks.

## Goal

`BoardSection` gains one control: **«תור חדש»**. It opens a dialog that searches the boutique's existing customers, takes one appointment type, and creates a **real `bookings` row** — `source = 'walk_in'`, `starts_at = now`, `checked_in_at = now`, `seat_index = 1`, **NULL terms**, **no manage token**, **no SMS**, **no scheduled message**, **no marketing-consent write**, **no deposit**. The row appears on the board on the next refresh, already checked in, and every floor verb downstream works on it because it is an ordinary booking.

**F50 ships one migration, one endpoint, one repository writer, one `AuditAction` member, one dialog — and zero new error codes, zero new handlers, zero new Hebrew in front of a member of the public, and zero new rate limiters.**

## What already exists to build on (verified against code)

- **A `customers` row is proof of phone possession, and that is written down.** `models/customer.py:12-15`: "Keyed by (tenant, phone) and created ONLY after OTP verification proved possession of that number — an unverified phone would strand a paying customer behind an SMS link that can never arrive." The only writer is `CustomersRepository.upsert`, called from `create_booking` step 6 (`service.py:460-462`) **after** `consume_verification` succeeded at step 1 (`service.py:318-322`). F53's CRM patches notes and tags; F15's phone correction re-points a booking at another row. **Nothing creates a `customers` row without an OTP.** So a booking bound to an existing `customer_id` inherits a verified phone by construction.
- **The customer picker is already an endpoint and already role-gated.** `GET /manage/customers?q=` (`customers/router.py:84-101`), router-level `require_role(OWNER, SHIFT_MANAGER)` (`:73-79`), `_no_store` (`:64-65`). Its search runs **both** a name leg on the raw term and a phone leg on `phone_search_term(term)` — because `customers.phone` holds strict E.164 and the leading `0` a human reads off a card was destroyed before storage, so `%050%` would answer "no results" for a customer who demonstrably exists (`db/repositories/customers.py:14-33`). `CustomerRow` ships `id`, `name`, `phone`, `tags` — and the phone ships deliberately, "the disambiguator for the shared-name case" (`customers/schemas.py:27-34`). This is exactly the picker this feature needs, and F50 adds nothing to it.
- **`bookings.source` does not exist.** `grep -rn "ALTER TABLE bookings" backend/migrations/versions/` returns four hits, all in `0010` (`manage_token_hash`, `cancelled_at`, `cancelled_by`) and `0014` (`checked_in_at`). `models/booking.py` declares no such column. `LOOP-STATE.md:1439` already records the gap from F19's recon — "bookings.source not existing (it is F50's, unbuilt)".
- **The terms columns are `NOT NULL` columns, not a CHECK.** `0008_bookings.py:69-70`: `terms_version_accepted INTEGER NOT NULL CHECK (terms_version_accepted > 0)` and `terms_accepted_at TIMESTAMPTZ NOT NULL`. The only CHECK on either is the inline `> 0`, whose name is Postgres-generated.
- **`checked_in_at` exists and is nullable.** `0014_booking_check_in.py:37`, `models/booking.py:45`. Its comment already anticipates this feature's semantics: status says what became of the appointment, this says whether she is in the building, "and the two are true at once".
- **Two shipped writers mint a manage token on a booking that has none, and both are excluded by `starts_at`.** `ManageLinkBackfill` feeds off `list_confirmed_without_manage_token`, whose predicate is `status = 'confirmed' AND starts_at > after AND manage_token_hash IS NULL` (`db/repositories/bookings.py:744-762`), driven by a platform-operator route (`platform/service.py:123`) that is explicitly safe to re-run. And F15's `_guard_live` refuses link rotation and resend on any booking with `starts_at <= now` (`booking/owner.py:1106-1128`). **Neither is a promise this feature makes; both are shipped predicates it can satisfy.** D2 is where that is spent.
- **Every dangerous owner verb is already clock-split.** `owner.cancel` requires a future `starts_at` (F15 D3); `no_show` and `complete` require a past one; `confirm` takes no clock bound at all ("a mis-tap is correctable whenever it is noticed", `owner.py:362-372`, the sentence at `:366`); F34's check-in and its undo take neither. So a row born at `now` is, from its second millisecond, in exactly the state the shipped verb set was designed for a bride who is present.
- **The router is the right home and its gate is structural.** `booking/owner_router.py` mounts `/manage` with `dependencies=[Depends(_no_store), Depends(require_role(OWNER, SHIFT_MANAGER))]` (`:79-85`); `test_staff_role_gating.py`'s walker reads `allowed_roles` off the **live** route table, so a route added here is policy-checked with no new test. Path parameters and real HTTP verbs are the shipped `/manage` convention and the `.claude/rules` RPC guidance is "Kotlin boilerplate for another codebase" — F15 D7's ruling, repeated verbatim in `customers/router.py:36-39`.
- **`audit_log.action` is plain `TEXT` with no CHECK** (`0003_auth.py:71-79`), so a new `AuditAction` member needs no migration. `AuditAction` already carries nine `BOOKING_*` members added on exactly this basis (`models/constants.py:269-284`).
- **Both error handlers this feature needs are app-level.** `DomainNotFoundError` at `main.py:1027-1028` and `SlotUnavailableError` at `main.py:1127-1129` (409, `SLOT_UNAVAILABLE`). `BookingNotFoundError` subclasses the former (`booking/service.py:122`).
- **The board's mutation discipline is a hook now, and it is reusable verbatim.** F57 moved the poll's six mechanisms and the `{401,403}` classifier into `lib/usePoll.ts`; `BoardSection.mutate` (`:229-285`) is the shape to copy — `mutationsRef += 1`, `poll.clearTick()`, `poll.bump()`, re-arm in the `.finally()` and never in the success path. `poll.refresh()` (`usePoll.ts:345-349`) bumps, cancels and fetches immediately, and `reschedule()` no-ops while the loop is stopped (`BoardSection.tsx:134-135`).
- **`Modal` is exported from `@boutique/ui`** (`packages/ui/src/index.ts:30-31`), and `apps/manage` already uses the dialog pattern five times (`RescheduleDialog`, `RoomsRegistryDialog`, `SosRaiseDialog`, `RoomHandoverDialog`, `RoomDressDialog`).
- **`api.listAppointmentTypes()` exists** (`apps/manage/src/api.ts:1341-1342`, `GET /manage/appointment-types`), and `AppointmentTypesRepository.by_id` returns `None` for an unknown or archived type — the exact behaviour `create_booking` maps to `BookingNotFoundError` (`booking/service.py:332-334`).

## Where the brief and the code disagree

The `LOOP-STATE.md` F50 note was written 2026-07-30. Twelve features have merged since, F20 four hours ago. Five of its claims do not survive contact, and the codebase-consistent reading is taken in every case.

| # | The brief says | The code says | Taken as |
|---|---|---|---|
| 1 | "a real booking with `source='walk_in'`" | **`bookings.source` does not exist.** No migration adds it; `models/booking.py` has no such attribute. `LOOP-STATE.md:1439` already recorded this from F19's recon. | **Correct in intent, unbuilt.** F50 adds the column — and D1 argues it earns its place as the *terms CHECK's discriminator*, not as a label. |
| 2 | "NULL terms (**DB CHECK** keeps storefront rows non-null)" | **There is no such CHECK.** `terms_version_accepted INTEGER NOT NULL` and `terms_accepted_at TIMESTAMPTZ NOT NULL` (`0008:69-70`) — plain NOT NULL columns. The only CHECK on either is the inline `terms_version_accepted > 0`. | **Inverted.** The brief describes the CHECK as pre-existing protection this feature can lean on. It does not exist, and **this feature is the one that must build it** — which is precisely what makes dropping the two NOT NULLs safe rather than reckless. D1. |
| 3 | "the recorded danger (SMS link to an unverified number) **evaporates because no link is minted**" | **Not minting one is not sufficient.** Two shipped writers mint tokens on bookings that have none: `ManageLinkBackfill` (feed: `confirmed AND starts_at > now AND manage_token_hash IS NULL`, `bookings.py:744-762`) and F15's resend/phone-correction (`_guard_live`, `owner.py:1106-1128`). A `confirmed` future-dated row with a NULL hash is exactly the backfill's feed. | **Under-argued, and the real discharge is different — twice over.** The number is verified in the first place (a `customers` row requires an OTP, `models/customer.py:12-15`), *and* `starts_at = now` puts the row outside both writers' predicates. D2 and D3. |
| 4 | "the only remedy path for F15's Risk 1" | Risk 1's mis-tap is a cancel on a **future** booking. A walk-in row is stamped at `now`. It cannot restore next Tuesday. | **Half true, and the half matters.** This feature remedies the mis-tap **discovered at the door** — the bride arrives, the board says `cancelled`, and she needs a real row to be checked in, roomed and dispatched. The mis-tap **discovered in advance** is not remedied and stays with the remote half. Risk 1 is re-pointed, not closed. Stated in *Out of scope*. |
| 5 | (implicit) a walk-in belongs in `bookings` | **F33 shipped `queue_tickets` and ruled the opposite for its case**: "A queue ticket is NOT a booking, and that is the point: no starts_at, no seat, no terms acceptance, no manage token, no SMS. Folding walk-ins into `bookings` would have meant a nullable starts_at on the table whose oversell guard is keyed on (tenant_id, starts_at, seat_index)" (`models/queue_ticket.py:12-17`). | **No conflict, and the distinction is the scope line.** F33's walk-in is a stranger with no appointment who waits her turn — `queue_tickets`, and the F58 dispatch works off it with no booking at all (`ClaimRoomRequest.booking_id` is optional). F50's walk-in is a **known customer being given an appointment that is happening now**. She has a `starts_at` (this instant), a seat and a type. `LOOP-STATE.md:556` states the same boundary from F33's side: "a queue ticket is NOT a booking, which is what keeps it distinct from F50's walk-in". D3 keeps the two from colliding by refusing the case that belongs to F33. |

## Design

### D1 — The migration: one column, two named CHECKs, two dropped NOT NULLs — and the exemption is enumerated, never the requirement

**Revision id and `down_revision` are resolved from `alembic heads` at build time, not from this document.** HEAD reads `0024` today (`0024_privacy_consent.py`, merged 2026-08-04), so this feature's migration is **`0025_walk_in_bookings.py` revising `0024`** — and this sentence is not the source either. Re-read `alembic heads` when the branch is cut, and keep this file as the **last commit on the branch** so a renumber at rebase is one amend to one file (0017's and 0024's recorded hazard, `0024_privacy_consent.py:9-15`). Everything below keyed to a literal means *this feature's migration*, and D1's pinned assertions are keyed to *after this feature's migration*, never to a number.

```python
def upgrade() -> None:
    # WHICH SURFACE CREATED THIS BOOKING. Not decoration and not analytics: it
    # is the DISCRIMINATOR the terms CHECK below needs. Without it, a NULL
    # terms_version_accepted has two indistinguishable meanings — "a staffer
    # created this row and nobody accepted anything" and "a storefront booking
    # lost its evidence to a bug" — and only the first is legal.
    #
    # NOT NULL DEFAULT 'storefront' is metadata-only in PG 11+ (non-volatile
    # default, no rewrite), and the default is load-bearing rather than
    # convenient: it is what makes the terms CHECK below true of 100% of
    # existing rows with no backfill UPDATE, because every row that exists today
    # WAS created by the storefront. 0017's `tags TEXT[] NOT NULL DEFAULT '{}'`
    # is the precedent.
    op.execute("ALTER TABLE bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'storefront'")
    # NAMED and its own statement — 0011's and 0024's shape. An inline CHECK on
    # ADD COLUMN takes a Postgres-generated name, and the remote half's widening
    # ('owner') then depends on guessing it.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_source_check "
        "CHECK (source IN ('storefront','walk_in'))"
    )

    # The two NOT NULLs go, and the CHECK below is what replaces them. Dropping
    # NOT NULL never fails on existing data and never rewrites.
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_version_accepted DROP NOT NULL")
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_accepted_at DROP NOT NULL")

    # ⚠ THE EXEMPTION IS ENUMERATED, NOT THE REQUIREMENT, and that direction is
    # the whole design of this constraint. Written the other way round —
    # `source <> 'storefront' OR (...)` — it says the same thing today and the
    # OPPOSITE thing tomorrow: the remote/scheduled half adds 'owner' to the
    # source CHECK above and would silently inherit a terms exemption it must
    # not have. Written this way, a third source value is a FAILING INSERT until
    # its author decides about terms on purpose.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_terms_evidence_check "
        "CHECK (source = 'walk_in' OR "
        "(terms_version_accepted IS NOT NULL AND terms_accepted_at IS NOT NULL))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_terms_evidence_check")
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_source_check")
    # ⚠ DELIBERATELY ABLE TO FAIL, and deliberately without a pre-clean. On a
    # table holding any walk_in row these two statements raise, and that is the
    # refusal, not a defect: the only ways to make them succeed are to DELETE
    # real appointment records or to stamp terms evidence nobody gave, and this
    # feature exists because the second one is not allowed. An operator who
    # genuinely wants to go back decides about those rows by hand, on purpose.
    # F57's `test_the_downgrade_refuses_to_narrow_past_a_floor_role_row`
    # (`test_migrations.py:352`) is the precedent and its docstring the argument:
    # "a lenient downgrade leaves the database describing a state its own schema
    # forbids." The db test asserts the failure rather than describing it.
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_accepted_at SET NOT NULL")
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_version_accepted SET NOT NULL")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS source")
```

**The downgrade's failure mode is a ruling, not an omission.** Every sibling migration in this repo ships an explicit `downgrade()` with a round-trip test (`test_migration_0011_round_trips` … `test_the_privacy_migration_round_trips`), and `0024_privacy_consent.py:112-119` is the immediate precedent for the drop-by-name shape. What is new here is that the reverse direction *can* fail on real data. It is spelled so it does, for the reason in the comment, and both halves are pinned: a round-trip on a table with **no** walk-in rows, and a **refusal** on a table with one.

`ADD CONSTRAINT` validates existing rows, so neither ALTER can fail on live data: every pre-migration row has `source = 'storefront'` from the default and two non-NULL terms columns from the NOT NULLs being dropped in the same transaction *after* they were satisfied. Both halves are proven on a **populated** table by a db-marked test, following 0011's and 0024's precedent — a `NOT VALID` constraint would pass the positive half alone and this paragraph would be a lie.

**The inline `CHECK (terms_version_accepted > 0)` is deliberately untouched.** A CHECK over a NULL evaluates to NULL, which is not FALSE, so it passes on a walk-in row without an edit — and hunting for its Postgres-generated name to drop and re-add would be work that buys nothing. Stated so a reviewer does not go looking.

Deliberately absent, each for a verified reason:

- **No `GRANT`.** `0008:107-110` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO app_user`; table grants are column-agnostic. (`.claude/CLAUDE.md`'s `ALTER DEFAULT PRIVILEGES` gotcha is about newly *created* tables.)
- **No `enable_tenant_rls`.** RLS is a table property, forced on `bookings` since `0008:109-110`. F50 adds no table, so `test_every_tenant_id_table_has_forced_rls` staying green **unedited** is the assertion that none snuck in.
- **No `_updated_at_trigger`.** `trg_bookings_updated_at` exists from `0008:105`.
- **No index on `source`.** Nothing filters or sorts on it — the board reads the day and renders the value. A partial index would serve no reader and cost every write.
- **No touch to the status CHECK or either partial unique index.** A walk-in is `confirmed`, occupies its own instant, and both indexes bind on it exactly as they bind on a storefront row. The migration proves this mechanically: the db test re-reads `pg_get_constraintdef` for the status CHECK and `pg_indexes.indexdef` for `idx_bookings_slot_seat_unique` and `idx_bookings_tenant_customer_starts_unique` **after** this feature's migration and pins all three against literals — F34's highest-value test, extended rather than re-invented.

**The ORM is the second half of this migration and it is not optional.** `models/booking.py` declares every column explicitly and nothing derives a mapping from a migration:

```python
source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'storefront'"))
terms_version_accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
terms_accepted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

### D1b — The seven ripple sites the nullability change breaks, and one of them is a live 500

This is the part of the feature that is dangerous, and it is dangerous in a *shipped* module rather than in anything F50 writes. `grep -rn "terms_version_accepted\|terms_accepted_at" backend/app frontend/apps` returns exactly these readers:

| # | Site | What breaks | Fix |
|---|---|---|---|
| 1 | **`privacy/service.py:237`** — `versions = sorted({row.terms_version_accepted for row in bookings})` | **A live 500 on F20's §13 subject-export route** for any subject who has a walk-in booking. `sorted()` over a set containing `None` raises `TypeError: '<' not supported between instances of 'NoneType' and 'int'`. This is the single highest-risk consequence of the migration and it is in a legally-mandated route. | Add `if row.terms_version_accepted is not None` to the comprehension. One line. |
| 2 | **`privacy/schemas.py:125-126`** — `ExportedBooking.terms_version_accepted: int`, `terms_accepted_at: datetime` | `ExportedBooking(...)` is **constructed explicitly** at `privacy/service.py:289-290`, and a plain pydantic `BaseModel` validates on construction — `None` raises `ValidationError` → 500 on the same route. | `int \| None` / `datetime.datetime \| None`. The export must show the absence honestly; a walk-in genuinely has no terms evidence and the §13 answer must say so. |
| 3 | **`booking/schemas.py:205-206`** — `OwnerBookingDetail.terms_version_accepted: int`, `terms_accepted_at: datetime` | Every `/manage/bookings/{id}` response for a walk-in fails serialisation. | `int \| None` / `datetime \| None`. `owner_router.py:139-140` needs no edit — it already passes the attribute straight through. |
| 4 | **`booking/manage.py:225`** — `self._terms.by_version(session, tenant.id, booking.terms_version_accepted)` | Type error under mypy; **unreachable at runtime** — this is the bride's tokenized page and a walk-in has no token (D2). | Narrow with an explicit `if booking.terms_version_accepted is None` branch rather than a cast. Unreachable-by-construction plus a `# type: ignore` is how a later feature that *does* mint a token turns a static guarantee into a runtime crash. |
| 5 | **`booking/owner.py:308`** — `version = booking.terms_version_accepted` inside `payments_for` | Type error under mypy; **unreachable at runtime** — the line sits inside `if payment.status == PAID` and a walk-in has no `payments` row at all (D4: no deposit path). | Same treatment: an explicit `is None` continue, not a cast. |
| 6 | **`apps/manage/src/api.ts:375-376`** — `OwnerBookingDetail.terms_version_accepted: number`, `terms_accepted_at: string`, rendered at **`BookingDetail.tsx:365-372`** | **One** `<Fact label={t("booking.terms")}>` holds *both* values in one body — `isolateLtr(t("booking.termsVersion", {version}), String(version))`, a `·`, then `<bdi>{jerusalemDate(terms_accepted_at)}</bdi>`. With NULLs it renders «גרסה null» and `jerusalemDate(null)`. | `number \| null` / `string \| null`. **One Fact, two bodies**: the existing body when `terms_version_accepted !== null`, and `t("booking.termsNone")` otherwise. There is no second Fact to make conditional and no split to invent. |
| 6b | **`apps/manage/src/api.ts:1056-1057`** — `ExportedBooking.terms_version_accepted: number`, `terms_accepted_at: string` | A **different interface**: F20's §13 subject-export mirror of `privacy/schemas.py:110-128`, opened at `api.ts:1046`. Nothing renders it — `grep` over `components/` and `pages/` returns only `BookingDetail.tsx`. | `number \| null` / `string \| null`, **type-only, no renderer**. Stated separately from site 6 because the two are *not* duplicates of one shape: de-duplicating them would break the privacy export, which carries `checked_in_at` and omits `seat_index` and `customer_phone`. |

The grep is complete for `Backend/app`: the only other hits are `bookings.py:98-99` (the `insert` writer's own parameters, which D5 leaves alone), `service.py:496-497` (the storefront create, which supplies real evidence), `models/booking.py:48-49` (the ORM, D1), and a comment at `core/config.py:336`.

Sites 1 and 2 are the reason this feature is **M** and not **S**. A build that ships the migration without them ships a green test suite and a 500 on the one route the Privacy Protection Authority would ask about.

### D2 — `starts_at = now`, and it is a safety mechanism before it is a timestamp

The row's `starts_at` is the UTC instant of creation, at full microsecond precision. It is *not* a slot the staffer picks, and it is not rounded.

**The obvious reading is that it records when she arrived. The load-bearing reading is that it disarms four shipped writers.** Each of these is a predicate that exists today, verified, not a guard F50 adds:

| Shipped writer | Its predicate | Effect on a walk-in row |
|---|---|---|
| `ManageLinkBackfill` → `list_confirmed_without_manage_token` (`bookings.py:744-762`) | `status='confirmed' AND starts_at > after AND manage_token_hash IS NULL` | **Never in the feed** — with one bounded exception, stated rather than glossed. `run()` captures `now = self._now()` **once** (`backfill.py:66`) and passes it to every tenant as `after=now` (`:87`), so a walk-in created *between* that capture and its own tenant's chunk query has `starts_at > after` and does match. The consequence is a spurious `manage_link_issued: true` and a token **nobody can ever hold**: the lead is milliseconds, `reminder_send_after` returns `None` under the 2h band (`comms.py:86-91`), the backfill `continue`s without inserting a `scheduled_messages` row (`backfill.py:97-102`), and the plaintext token dies as a local. The backfill is a manual one-shot operator route, not a scheduled job. **Not fixed here** — re-reading `now` per chunk is F16's file and buys nothing this feature needs; Risk 8. |
| F15 resend-link and phone-correction → `_guard_live` (`owner.py:1106-1128`) | `status='confirmed' AND starts_at > now` | **409 `BOOKING_TRANSITION_INVALID`.** A staffer cannot text an SMS control link for a walk-in, by the guard F15 already wrote. |
| `owner.cancel` (F15 D3's clock split) | future `starts_at` | Refused. The right verbs for someone in the building are `no_show` and `complete`, which are the ones a past `starts_at` admits. |
| `reminder_send_after` (`comms.py`) | returns `None` inside the 2h suppression window | Would answer `None` anyway. F50 never calls it, and does not need to. |

**This is what actually discharges the brief's "no link is minted", and the brief's own version of that claim was unsupported** (conflict 3). "This feature does not mint one" is a statement about *this feature*; the backfill is a different feature that mints one on any row matching a predicate. `starts_at = now` is a property of the row, so it holds against writers this spec has never read.

**Declined: letting the staffer pick a time.** That is the remote/scheduled half, and picking a future time is exactly what re-arms all four rows of the table above. It is the clean scope line and it is why the split exists.

**Declined: rounding to the minute or to a grid instant.** Rounding puts many walk-ins on one `starts_at`, which turns the `(tenant_id, starts_at, seat_index)` index from a free backstop into a real contention point (D4), and it would make a walk-in look like a slot claim on F12's grid, which it is not.

### D3 — **The request body is two UUIDs, and that is what makes this feature legal**

```
POST /manage/bookings/walk-in
{ "customer_id": "<uuid>", "appointment_type_id": "<uuid>" }   -> OwnerBookingDetail
```

**No name. No phone. No terms. No `marketing_consent`. No `starts_at`. No notes.** Every one of those absences is a ruling.

**(a) No name and no phone — so this is not a §11 collection point at all.** F20 enumerated the collection points and what each must show (`ppl-compliance.md:70-77`); the duty attaches to *obtaining personal data from the subject*. A staffer picking a customer the boutique already holds obtains nothing. There is therefore no notice to give, no new public-facing Hebrew, and — decisively for Gate 1 — nothing here that belongs to counsel.

The alternative was a dialog that types a name and a phone, and it fails on its own terms. It would be a **fourth collection point**, and F20's own §11 rule is that the notice must stand *at the moment of collection*, in front of the person whose data it is. There is no screen facing the bride: the board is on a staffer's phone. The best that surface could do is print an instruction telling the staffer to recite a legal notice aloud — an unenforceable delivery of a legally-required disclosure, dressed as compliance. F20 already ruled the analogous case for staff records: the platform ships the *text* and records that delivery is the boutique's own process (`ppl-compliance.md:76`, point 4). Building a third intake behind a fourth notice is not the lazy answer and it is not the safe one.

**And it is unnecessary, because both real intake routes are already built behind approved notices.** A bride with no `customers` row has used neither the storefront booking form (notice #1, `BookPage` `details` step, `boutique.privacy_notice_text`) nor F33's `/checkin` walk-in queue form (`checkin.notice`, `storefront/he.ts:550`, the counsel-gated interim). So: **an unknown customer is a 404**, and the dialog's empty-search state names the QR check-in as the remedy. That composes with what shipped rather than duplicating it — F33 built the poster (`CheckinQrSection`), F58 dispatches off queue tickets with no booking required, and a true stranger belongs in the queue.

**(b) No `marketing_consent`, and the correct value is "no field", not `false`.** This was the design question the brief leaned hardest on, and the codebase has already answered its near neighbour. `customers_marketing_consent_source_check` admits exactly `'booking_form'` (`0024:61-64`), and `MarketingConsentSource`'s docstring says why F33's walk-in opt-in was **kept out** of the column: "that form has no possession proof of any kind, so promoting it into this column would launder an unverified submission into evidence that a specific woman consented — degrading every other row in a column whose only job is to be provable under the Spam Law" (`constants.py:203-216`). An owner-created booking has *less* than F33's form, not more: not even a box she ticked herself, only a staffer's recollection. **So the CHECK is not widened with `'walk_in'`, and the answer is not `marketing_consent: false` — it is no field at all.** A field is something a caller can set; an absent field is the only spelling of "this surface cannot express consent" that a future caller cannot flip.

The consequence for an *existing* consent is the one that needs stating: the walk-in path issues **no** clearing statement, so a customer who consented through the booking form keeps her consent and her original timestamp. That is F20's D20 rule applied unchanged — "the ABSENCE of the call is the whole semantics of an unticked box … withdrawal must be an affirmative act" (`booking/service.py:463-470`). Both named CHECKs on `customers` are satisfied trivially and untouched: this path writes no column on `customers` at all.

**(c) No notes.** A staffer's free text about a bride is personal data obtained *not from her*, on the one path this spec has just argued collects nothing — and it is unnecessary, because `customers.notes` is the shipped home for exactly this (F53's CRM, `set_notes_and_tags`). Two required UUIDs and no free-text field is a body with no PII surface whatsoever, which is what lets (a) be stated without a residue.

**(d) An erased subject is a 404.** F20's §14 erase sets `erased_at` and scrubs the phone (`privacy/service.py:434`). Creating a new booking for an erased subject would resurrect a processing relationship the erasure record says ended, and the honest status for "there is no data subject here" is the same 404 the rest of this router gives for an unknown id — `BookingNotFoundError`, zero new codes. **The picker shows her**: `_search_where` (`db/repositories/customers.py:34-46`) filters on `tenant_id` and `deleted_at` only, so an erased row matches its own `[erased]` placeholder name, and `CustomerRow` carries no `erased_at` to render (`customers/schemas.py:27-40` — four fields: `id`, `name`, `phone`, `tags`). So she can be selected and the server refuses. Cosmetically rough, structurally correct; Risk 4.

**(e) Real HTTP verb, path-free, on F15's router.** `POST /manage/bookings/walk-in` is a verb sub-path on the collection, the `/no-show`, `/complete`, `/resend-link`, `/check-in` shape — with no path parameter because there is no booking yet. Both roles are admitted at router level and it does **not** join `test_staff_role_gating.py`'s `OWNER_ONLY` set: a shift manager runs the floor, and a board she cannot act on is not a shift manager's board (F34 D5, and the SMC locked matrix keeps owner-only to staff management and `POST /manage/terms`).

### D4 — Why this does not collide with the slot engine, and why there is no advisory lock

`create_booking`'s claim protocol is seven ordered steps under `pg_advisory_xact_lock(hashtext(tenant_id))` (`service.py:383-518`), and the lock exists for exactly one reason: the seat is **picked from a count** — `active_seats_at` reads, then `insert` writes, and the lock is what stops two readers picking the same free index (`db/repositories/bookings.py:113-119`). **The walk-in path has no such read.** It writes `seat_index = 1` unconditionally, so there is no read-modify-write to serialise and no lock to take. Taking one anyway would serialise every walk-in against every public booking create and every owner reschedule, for nothing.

**A walk-in consumes no slot capacity, deliberately.** `offered_slot` is never called: it would reject `now` twice over — the instant is not on the published grid, and `create_booking`'s own horizon guard requires `now < starts_at` (`service.py:297-298`). She has no reservation because she made none. The two consequences, both correct and both stated so neither is a surprise:

- **F12's grid does not count her.** `count_by_start` groups on exact `starts_at` (`bookings.py:764-786`), and a microsecond-precise instant matches no grid slot. So the storefront keeps offering the boutique's published capacity while the shop fills with walk-ins. That is a **real operational ceiling**, not a bug — the boutique chose to take her outside its published grid — and it is Risk 1.
- **Both partial unique indexes still bind, as free backstops.** `idx_bookings_slot_seat_unique` on `(tenant_id, starts_at, seat_index)` and `idx_bookings_tenant_customer_starts_unique` on `(tenant_id, customer_id, starts_at)` both key on `starts_at`, which is unique per microsecond. Two walk-ins colliding requires two INSERTs in the same microsecond on one tenant. The `IntegrityError` is caught and re-raised as `SlotUnavailableError` — the same 409 `SLOT_UNAVAILABLE` the storefront gives, mapped by the app-level handler at `main.py:1127-1129`, **zero new codes**.

  `# ponytail: seat_index is always 1 — microsecond-unique starts_at makes the` \
  `# (tenant, starts_at, seat) index collision-free in practice, and the index` \
  `# is the backstop when it is not. If walk-ins ever need to share an instant,` \
  `# that is the moment to take the advisory lock and pick from active_seats_at.`

**No deposit, ever.** `deposit_due` is not evaluated and `open_deposit` is not called. The predicate needs a gateway read and an appointment type's `deposit_required` (`service.py:86-119`), and a walk-in at the counter pays at the counter — F19's hosted checkout is a storefront redirect flow with a return URL, which there is nothing to return to. The row's `payment_status` and `refund_due_agorot` are `None`, which `_row_fields:114-118` already documents as "the field is the marker, not a claim that a deposit was expected".

**No rate limiter.** The two budgets `create_booking` spends are keyed on the phone and the tenant and exist because the storefront create is reachable by anyone holding an OTP (`service.py:300-313`). This caller holds a live staff session, is CSRF-fenced and is standing in the shop; a budget here is a self-DoS with no attacker on the other side of it — F15's ruling on this same router (`owner-booking-management.md:173`), unchanged.

### D5 — One repository writer, one service method

**Repository** — `BookingsRepository.insert_walk_in`, beside `insert`:

```python
async def insert_walk_in(
    self, session, *, tenant_id, customer_id, appointment_type_id,
    appointment_type_name, at: datetime,
) -> Booking:
    # starts_at and checked_in_at are ONE instant, passed in rather than read
    # here: a service that computes `now` twice can produce a row that was
    # checked in before it started. (`created_at` is NOT that instant and must
    # not be described as one — `models/base.py:21-23` is a `now()` server
    # default, which is transaction-start time, and under an injected `_clock`
    # in tests the two are years apart.)
    #
    # source='walk_in', terms columns NULL, manage_token_hash NULL, seat_index 1,
    # dress_* NULL, notes NULL. IntegrityError from either partial unique index
    # surfaces exactly as `insert`'s does — the caller maps it to
    # SlotUnavailableError.
```

**Declined: adding `source`, `checked_in_at` and nullable terms as defaulted keyword arguments to the existing `insert`.** Its signature already takes fourteen parameters and its docstring already carries a load-bearing precondition about the advisory lock that this caller deliberately does **not** satisfy (`bookings.py:113-119`). Folding a lock-free caller into the method whose docstring says every caller holds the lock is how that docstring stops being true. Two short writers, one precondition each.

**Service** — `OwnerBookingService.create_walk_in`, in one `tenant_session`:

```python
async def create_walk_in(self, tenant_id, *, customer_id, appointment_type_id, staff) -> OwnerMutation
```

1. `now = self._now()` — once, captured.
2. `customers.by_id` → `None` ⇒ 404 `BookingNotFoundError`; `erased_at is not None` ⇒ the same 404 (D3d).
3. `types.by_id` → `None` ⇒ the same 404. Indistinguishable by design, the `BookingNotFoundError` docstring's own rule (`service.py:122-124`).
4. `insert_walk_in(..., appointment_type_name=type_row.name, at=now)`, `IntegrityError` ⇒ `SlotUnavailableError`.
5. Audit row (D6), same transaction, before commit.
6. Return `OwnerMutation(booking=..., changed=True, manage_token=None)` — F15's shape, so `owner_router` renders it through the existing `_detail_of` with no new projection.

`OwnerBookingService.__init__` gains one line: `self._types = AppointmentTypesRepository()`. It already holds `_bookings`, `_customers`, `_terms`, `_audit` and `_clock` (`owner.py:189-196`).

**No `_transition` five-step shape.** That shape is load → compare → 409 → guarded write → audit, and its steps 2 and 3 exist to answer *what state was this row in*. There is no row. A create has one outcome and no idempotency question: **it is deliberately not idempotent**, and a double-tapped dialog produces two rows. The dialog's `disabled={busy}` is the control, and if it fails, the remedy is F15's cancel on a row a staffer can see — which is cheaper and more honest than an idempotency key on a surface where "she came in twice today" is a real thing that happens (F33 made the same call for a second queue ticket on one phone: "a second ticket for the same phone on the same day is a real, expected outcome", `queue_ticket.py:24-26`).

### D6 — One `AuditAction` member, no migration

| Member | Value | Written by | `details` |
|---|---|---|---|
| `BOOKING_WALK_IN_CREATED` | `booking_walk_in_created` | every successful create | `{"customer_id": "…", "appointment_type_id": "…"}` |

`action` is plain TEXT with no CHECK (`0003_auth.py:71-79`), `actor_id=staff.id`, `entity=str(booking.id)` — F15's `_record` shape verbatim (`owner.py:1177-1198`). **No phone and no name in `details`**: F20's rule for its own rows is `phone_last4` and never the number (`constants.py:580` and `:605`), and here even that is unnecessary because `customer_id` resolves it.

This row is the only record of *who* created a booking carrying no terms evidence, which is what makes it the audit entry that most earns its place in this area. Nothing reads these rows in v1 (F15 Risk 7, unchanged).

### D7 — Errors: zero new codes, zero new handlers

| Condition | Status | Code | New? |
|---|---|---|---|
| Unknown customer id, **erased** customer, unknown/archived appointment type (indistinguishable under RLS and by design) | 404 | `NOT_FOUND` | no — `BookingNotFoundError` subclasses `DomainNotFoundError`, handler at `main.py:1027-1028` |
| Lost a microsecond race on either partial unique index | 409 | `SLOT_UNAVAILABLE` | no — `SlotUnavailableError`, handler at `main.py:1127-1129` |
| No session / expired | 401 | `NOT_AUTHENTICATED` | no — app-wide. **Terminal**; `poll.fail()` stops the board (F34 D4.3) |
| Role outside `{owner, shift_manager}` | 403 | `NOT_AUTHORIZED` | no — F31's generic body. **Terminal**, same branch |
| Foreign-origin mutating `/manage` request | 403 | `CSRF_ORIGIN_MISMATCH` | no — `Backend/app/csrf.py:18-21` (the body), `:51` (the 403) |

`test_booking_owner_api.py`'s `SPEC_ERROR_CODES` is asserted by **set equality** and F50 adds no member — a real result, not laziness. Declined: `WALK_IN_CUSTOMER_UNKNOWN` (it would distinguish, on an authenticated route, a customer who exists from one who does not — and `main.py` has no error registry, so every invented code is a handler somebody has to remember, and an unmapped typed error is a bare 500).

### D8 — `source` joins the row shape; the detail explains the absent terms

`OwnerBookingRow` gains `source: str`, inherited by `OwnerBookingDetail`, and `_row_fields` (`owner_router.py:100-119`) gains one line. It ships on the **row** because the board is the only reader that matters and the board only ever reads the list.

Two shipped list-row literal assertions red-fail on the new field and that is the point of them — `test_booking_owner_api.py`'s list-defaults payload and its detail payload, both asserted with `==` against a full dict. The plan updates both as a visible, reviewed edit. On the frontend the same widening breaks **five** typed test factories, enumerated in *Testing*.

**Why the row and not only the detail.** A NULL `terms_version_accepted` on the detail is ambiguous on its own — missing because walk-in, or missing because something broke? `source` is the discriminator in the API for the same reason it is the discriminator in the CHECK (D1). `BookingDetail.tsx` renders the two terms `<Fact>`s only when non-null and otherwise renders one muted line, `booking.termsNone` — «נוצר בבוטיק · אין אישור תנאים» — which states the fact rather than leaving a hole.

## Frontend changes

### Files

| File | Change |
|---|---|
| `apps/manage/src/api.ts` | `OwnerBookingRow` gains `source: string` (**required**, not optional — see the test-factory row below for what that costs). `OwnerBookingDetail.terms_version_accepted` → `number \| null`, `terms_accepted_at` → `string \| null` (`:375-376`, the rendered one). **Separately** `ExportedBooking` (`:1046`, terms fields at `:1056-1057`) → the same two nullable, **type-only, no renderer** — it is F20's §13 mirror of `privacy/schemas.py:110-128`, not a second copy of `OwnerBookingDetail`, and must not be de-duplicated into one. New `createWalkInBooking(body: WalkInBookingRequest): Promise<OwnerBookingDetail>` → `POST /manage/bookings/walk-in`. New `WalkInBookingRequest { customer_id: string; appointment_type_id: string }`. **No case conversion anywhere** — this app's `apiFetch` sends and receives snake_case as the backend spells it; the `.claude/rules` `keysToSnake` guidance is for another codebase and no file in `apps/manage` does it. |
| `apps/manage/src/components/WalkInDialog.tsx` | **New.** The only new component. |
| `apps/manage/src/components/BoardSection.tsx` | One `<Button>` and one `useState`; one `create` handler reusing `mutate`'s discipline (D9). |
| `apps/manage/src/components/BookingDetail.tsx` | The **single** `<Fact label={t("booking.terms")}>` at `:365-372` gains a second body: its existing contents when `terms_version_accepted !== null`, `t("booking.termsNone")` otherwise. One Fact, two bodies — there is no second Fact. |
| **`apps/manage/src/__tests__/BookingsSection.test.tsx`** | **Not optional and easy to miss** — `row()` at `:24` is `(overrides: Partial<OwnerBookingRow>) => OwnerBookingRow`, so a required `source` makes it TS2739 and `pnpm build` reds before a single test runs. Gains `source: "storefront"`. |
| `apps/manage/src/i18n/he.ts` | ~14 new `walkin.*` keys plus `board.newWalkIn`, `booking.termsNone`, `booking.sourceWalkIn`. Flat dotted literals, the file's shipped form. |
| `apps/manage/src/i18n/ar.ts` | The same keys with the Hebrew as values — that file's own header rule (Interview Q3 / pre-decided #47). ⚠ **This is load-bearing, not courtesy.** The earlier claim that "no he/ar parity guard exists" was wrong in two ways: `i18n.test.ts:1431-1434` is a **key-presence** guard (`HE.map(([key]) => key).filter((key) => !(key in ar.translation))`) and it **does** bind on `board.newWalkIn` (selected by `HE_F34`'s `board.` prefix) and on `booking.termsNone` / `booking.sourceWalkIn` (selected by `HE_F15`'s `booking.` prefix), so those three red the suite if `ar.ts` is skipped. There is also a **value**-parity guard, scoped by name to `rooms.` keys only. What does **not** exist is a general value-parity guard, and F50 still adds none (F15 Risk 5, unchanged). |
| **`apps/manage/src/__tests__/i18n.test.ts`** | The file is `i18n.test.ts` — there is no `i18n-keys.test.ts` in this app. It does **not** scan the bundle: it declares one `HE_F*` constant per feature and unions them into `HE`, and its own comment warns that *"a block declared and not spread is skipped silently and greenly."* No selector matches `walkin.`, so all ~14 keys would be invisible to the resolve check, both register guards and the ar-presence guard. Gains `const HE_F50 = entries(he.translation, (key) => key.startsWith("walkin."))`, **spread into `HE`**, with its own `toBeGreaterThanOrEqual` floor — the per-feature-floor rule every other block follows (`:252`, `:330`, `:1277`). |

**All of this Hebrew is staff-facing console copy, which is the self-approving class** (F34 shipped thirty `board.*` strings with no gate). **There is no public-facing string in this feature**, because D3 removed the surface that would have needed one. That is stated here rather than assumed, because it is the fact Gate 1 turns on.

### The control

One `<Button variant="secondary">` labelled «תור חדש», rendered **outside the `Card`**, between the freshness bar and the `role="status"` cue, whenever `rows !== null && terminal === null`.

**Why outside the Card, corrected.** The reason is *not* that `EmptyState` cannot hold it — it can: `EmptyStateProps` has an `action?: ReactNode` slot for exactly this (`packages/ui/src/components/EmptyState.tsx:4-9`, "Optional CTA (a Button, a link)"). The reason is that `action` renders **only** in the empty state, and this control must be on the board whether the day is empty or full. One button in one place beats the same button declared twice. And it is not in the freshness bar: «השהיה» and «תור חדש» on one line is a pause control beside a create control, and a hurried thumb should not have those adjacent.

### The dialog

`Modal` from `@boutique/ui`, the `RescheduleDialog`/`SosRaiseDialog` shape. Three steps in one dialog, no wizard:

1. **Customer** — an `Input` bound to `api.listCustomers({ q, offset: 0, limit: 10 })`, debounced, results as a radio list showing `name` + `<bdi dir="ltr">{phone}</bdi>`. The phone is the disambiguator two brides named «מיכל לוי» need, which is why `CustomerRow` ships it (`customers/schemas.py:27-34`).
2. **Appointment type** — a `Select` from `api.listAppointmentTypes()`, fetched once when the dialog opens.
3. **Confirm** — one primary Button, `disabled` until both are chosen, `loading` while in flight.

**States, all six:**

| State | What shows |
|---|---|
| Default | Search box focused, empty type Select, disabled confirm |
| Loading (search) | `Skeleton variant="text"` under the box; the confirm stays disabled |
| Empty (no match) | **The load-bearing one.** «לא נמצאה לקוחה עם השם או הטלפון האלה. לקוחה חדשה נרשמת דרך טופס הרישום בכניסה — הקוד מופיע בעמוד «קוד רישום».» — the D3 ruling as product copy, pointing at F33's shipped QR surface. Not an error, not `role="alert"`; it is the ordinary answer to a search that matched nothing. |
| Error | `role="alert"` inside the dialog with `bookingErrorText(error, t)` from `lib/booking.tsx`; on a 404 the copy says the customer or the type is no longer available and the next search will show the current list |
| Success | Dialog closes, `poll.refresh()`, the board's `role="status"` cue reads «נוצר תור חדש עבור {{name}}.» — the `board.checkedInCue` shape |
| Terminal (401/403) | `poll.fail(error)` returns true; the dialog closes and the board's own terminal screen takes over — the classifier is the hook's, so this is one line and not a second classifier |

**Poll interaction — F34 D4(4)'s discipline, copied and not re-derived.** The create wraps in `mutationsRef.current += 1` / `poll.clearTick()` / `poll.bump()`, and the `.finally()` decrements and then calls **`poll.refresh()`** rather than `poll.reschedule()`. Refresh on **both** arms, success and non-terminal failure, so there is one rule: a rejected create must not park the loop either, which is the same reason F34 put the re-arm in the `.finally()` rather than the success path (`BoardSection.tsx:277-283`).

⚠ **The terminal arm is the one exception, and swapping `reschedule` for `refresh` is what creates it.** F34 could put its re-arm in an unguarded `.finally()` precisely because `reschedule()` **no-ops while the loop is stopped** (`BoardSection.tsx:134-135`). `refresh()` has no such guard — it is three unconditional statements, `generationRef += 1` / `clearTick()` / `runRef.current(...)` (`usePoll.ts:345-349`). So on the 401/403 arm, where `poll.fail(error)` returns true and the board's terminal screen takes over, an unguarded `.finally()` fires **one more fetch against a session already known to be dead**, which can only 403 again. Not a loop — `run()`'s own `finally` re-arms through `reschedule()`, which does no-op — but one guaranteed doomed request, and it contradicts the Terminal row of the states table.

The shape, one local flag and no second classifier:

```ts
let terminated = false;
try { … } catch (error) {
  if (poll.fail(error)) { terminated = true; return; }
  setError(…);
} finally {
  mutationsRef.current -= 1;
  setBusy(false);
  if (mutationsRef.current === 0 && !terminated) poll.refresh();
}
```

**`poll.refresh()` rather than a client-side sorted insert**, and this is the one place a shortcut is taken on purpose. The response is an `OwnerBookingDetail`, so the F15 list→patch contract *could* place it — but the new row belongs at `(starts_at, seat_index)` order, not at the head, so patching means writing a second sorter for a list the server already orders and that the very next tick re-sorts anyway. One extra request per walk-in — call it one an hour — buys the server's own ordering and no divergence. `refresh()` bumps, cancels and fetches immediately (`usePoll.ts:346-350`), and `reschedule()` no-ops while the loop is stopped, so a create from a paused board does one fetch and stays paused (`BoardSection.tsx:134-135`).

### The row

A walk-in row renders exactly like any other, plus one muted word beside the type name — «נכנסה» via `booking.sourceWalkIn` — in the `attendance_confirmed_at` treatment (`BoardSection.tsx:551-554`): muted words, never a second `Badge`, never a tint. It arrives with `checked_in_at` set, so F34's rules give it the arrival line and the undo control with no edit. A staffer who created it by mistake has three shipped remedies and F50 adds none: undo the check-in, mark `no_show`, mark `completed`.

### Accessibility

IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38). The dialog inherits `Modal`'s focus trap and Esc; focus lands on the search `Input` at open and returns to «תור חדש» at close; the results radio group carries a real `<fieldset>`/`<legend>`; the empty-state and error copy are text, never colour. **The focus-trap, Esc and focus-return assertions belong to Playwright and not to vitest** — `setup.ts` stubs `HTMLDialogElement.showModal()` as `this.open = true`, so a jsdom assertion about any of the three measures the stub and cannot fail.

## Testing

**Migration (db)** — `test_migrations.py`, on a **populated** table: `source` defaults to `'storefront'` on every pre-existing row; both new constraints exist by name via `pg_get_constraintdef`; a `storefront` row with NULL terms is **rejected**; a `walk_in` row with NULL terms is **accepted**; `source='queue'` is rejected by `bookings_source_check`; and the status CHECK plus both partial unique indexdefs are re-pinned against literals **after this feature's migration** (F34's test, extended). **Downgrade, both halves:** it round-trips on a table containing **no** walk-in rows (the `test_migration_00NN_round_trips` family), and it **raises** on a table containing one — the refusal asserted rather than described, in `test_the_downgrade_refuses_to_narrow_past_a_floor_role_row`'s idiom (`test_migrations.py:352`).

**Repository (db)** — `insert_walk_in` writes `source`, NULL terms, NULL `manage_token_hash`, `seat_index=1`, and one instant across `starts_at`/`checked_in_at`; a second insert at a **forced identical** `starts_at` for the same customer raises `IntegrityError` (both indexes, one test each).

**Service (db)** — happy path; unknown customer → 404; **erased customer → 404**; unknown and archived type → 404; the audit row exists with `actor_id`, `entity` and both ids in `details`; **no `customers` row is written and an existing `marketing_consent_at` is unchanged**; **no `scheduled_messages` row is created**; **`manage_token_hash` is NULL**.

**The four disarm assertions (db), and they are the highest-value tests in the feature** — each pins a *shipped* predicate against a walk-in row, so a future edit to any of the four collides with a test instead of with a bride:
1. `list_confirmed_without_manage_token` does not return a walk-in row.
2. `resend-link` on a walk-in answers 409 `BOOKING_TRANSITION_INVALID`.
3. `POST /manage/bookings/{id}/phone` on a walk-in answers 409.
4. `cancel` on a walk-in answers 409; `no-show` and `complete` answer 200.

**API** — the route joins `ROUTES` in `test_booking_owner_api.py` (`:96`); `SPEC_ERROR_CODES` (`:117`) is unchanged (set equality); `source` on the list row and both terms fields nullable on the detail; the two full-dict literals updated.

**Privacy regression (db) — this is the ripple test and it must be written before the migration lands.** A subject with **one storefront booking and one walk-in booking**: `GET`/`POST` the §13 export answers **200** with `terms_version_accepted: null` on the walk-in and the real version on the other, and the `terms` array carries exactly the one version that exists. Without D1b sites 1 and 2 this test is a 500, and it is the assertion that says so.

**Role gating** — the structural walker covers the new route with no edit; the HTTP matrix asserts a `shift_manager` create succeeds and it is **absent** from `OWNER_ONLY`.

**Frontend (vitest)** — `WalkInDialog.test.tsx` (new): search debounce and results; empty-state copy present and pointing at the check-in code; confirm disabled until both fields chosen; the create body is exactly two keys; error copy from `bookingErrorText`. `BoardSection.test.tsx` extended: the button renders in the empty state and in the populated state and **not** on the terminal screen; a successful create closes the dialog, fires exactly one extra fetch and writes the cue; a 403 from the create drives the terminal screen **and issues no further fetch** (the D9 exception, asserted); **no poll tick is issued while the create is in flight, and exactly one is armed after it settles — on the success and the non-terminal-failure arms**. `BookingDetail.test.tsx` extended: a walk-in detail renders `booking.termsNone` in the terms Fact and neither the version nor the date.

**The type edit touches five test factories, not two**, and all five must gain `source` in the same commit or `pnpm build` reds on TS2739 before any test runs: `BookingsSection.test.tsx:24` `row()`, `BoardSection.test.tsx:34` `row()` and `:50` `detail()`, `BookingDetail.test.tsx:54` `detail()` and `:81` `listRow()`. Nullable terms fields break none of them (`number` is assignable to `number | null`); the required `source` breaks all five.

**`i18n.test.ts`** — a new `HE_F50` block **spread into `HE`**, with a floor. Without the spread the ~14 `walkin.*` keys are silently uncovered by every guard in the file, which is the failure its own comment names.

**E2E (Playwright + axe)** — open the board, open the dialog, search an existing customer, create, see the row appear already checked in; axe clean on the open dialog; **Esc closes and focus returns to «תור חדש»** (the assertion vitest structurally cannot make).

## Out of scope

- **The remote/scheduled owner-create half.** It stays open in `LOOP-STATE.md`'s F50 entry and this merge does not close it. What it still needs, none of which this spec builds: **a picked future `starts_at`**, which re-arms all four writers D2 disarms and therefore needs the manage token, the reminder row and the confirmation SMS; **a terms answer** — the remote half's `source` value (`'owner'`) hits `bookings_terms_evidence_check` and fails until its author decides, on purpose, whether an owner-created future booking carries terms evidence and whose acceptance it records; **consent capture**, because a phone typed by a staffer for a customer who does not yet exist is the unverified number Interview Q6 named, and it needs either an OTP round-trip or a written narrowing of the invariant stated three times (`e3-booking-and-comms.md:18`, `:54`, `booking-core.md:10`); and **a §11 collection notice**, whose Hebrew is the user's under the F19/F33/F20 precedent. D1's constraint direction is the hand-off: adding `'owner'` to `bookings_source_check` without deciding about terms is a failing INSERT, not a silent exemption.
- **Restoring a mis-tapped cancel on a *future* booking.** Conflict 4. This feature remedies the mis-tap discovered **at the door**; the one discovered in advance is not remedied, and **F15's Risk 1 is re-pointed at the remote half rather than closed by this merge.**
- **A walk-in for a customer who does not exist yet.** D3. The remedy is F33's `/checkin` form or the storefront booking form — both shipped, both behind an approved notice.
- **Widening `customers_marketing_consent_source_check` with `'walk_in'`.** D3b. That belongs to whatever feature builds a *verified* promotion of a queue ticket's opt-in, exactly as `MarketingConsentSource`'s docstring already says.
- **Making a walk-in consume grid capacity.** D4, Risk 1. Rounding to a grid instant to make F12 count her is a change to the meaning of a slot claim, not a bug fix.
- **A deposit on a walk-in.** D4. She pays at the counter and there is nothing to redirect back to.
- **Notes on the create.** D3c. `customers.notes` is F53's and is the shipped home.
- **An idempotency key or a duplicate-create guard.** D5. A second walk-in for one customer on one day is a real outcome and the remedy is a visible row a staffer can cancel.
- **Any change to `queue_tickets` or to F58's dispatch.** A queue ticket is not a booking and this feature does not promote one into a booking. If it should, that is a spec that has to answer what happens to `marketing_opt_in_at`, which is precisely the laundering `MarketingConsentSource` forbids.
- **An audit-trail read endpoint** (F15 Risk 7, unchanged) and **a he/ar parity guard** (F15 Risk 5, unchanged).

## Risks & open items

1. **A walk-in occupies the shop but not the grid.** `count_by_start` groups on exact `starts_at`, so a walk-in at a microsecond-precise instant contributes to no published slot and the storefront keeps offering full capacity while the boutique fills. Deliberate — she took no reservation — but at pilot volume a busy Sunday of walk-ins can oversell the *room*, which is the real constraint, while every index stays satisfied. Mitigated by the board showing everyone and F36's rooms being the actual gate. *Owner: team. Trigger: the first pilot report of two brides and one mirror, or F36 reporting room contention.*
2. **The nullability change reaches a legally-mandated route.** D1b sites 1 and 2 are in F20's §13 subject export, which the Privacy Protection Authority is the audience for. The migration and those two edits **must land in one commit**; a build that splits them ships a green suite and a 500 on the one route that must never fail. The privacy regression test is the guard and it is named as write-first in *Testing*. *Owner: team. Trigger: code review — this is the review's first question.*
3. **`bookings.terms_version_accepted` is no longer a guarantee, and four readers now assume it is.** Two are unreachable-by-construction today (D1b sites 4 and 5) and are narrowed rather than cast, but the class of bug is now open: any future reader that assumes terms evidence exists will be right for every row it sees in development and wrong for the first walk-in. `bookings_terms_evidence_check` bounds the damage — the *only* rows that may be NULL are `walk_in` ones — but nothing enforces that a reader checks. *Owner: team. Trigger: F21's security audit, and any feature that reads the terms columns.*
4. **The customer picker shows erased subjects.** `_search_where` filters on `tenant_id` and `deleted_at` only (`db/repositories/customers.py:34-46`) and `CustomerRow` carries no `erased_at` to render (`customers/schemas.py:36-39`), so an erased customer appears in the search with her scrubbed placeholder and the create 404s at the server. Correct, but the staffer learns it only from an error line. Fixing it means either a new field on a shipped list resource or a filter on a shipped query, both of which are F53's surface. *Owner: team. Trigger: the first pilot report, or F53's next revision.*
5. **A walk-in row can never be given a manage link, and that is permanent.** D2's `starts_at` puts her outside `_guard_live` forever, so if the boutique later wants to text her (a follow-up, a next-fitting link), there is no console path and no backfill path. That is the correct default for a row created without her acceptance, but it is a one-way door — the remedy is a new booking through a route that takes her consent, not a widening of `_guard_live`. *Owner: team. Trigger: a pilot request to text a walk-in customer.*
6. **`source` ships on a bulk list row, which is a widening of F15's D18 payload rule.** D18 keeps bulk PII off `OwnerBookingRow`; `source` is not PII and the widening is argued in D8, but it is the second field added to that shape in three features (F34's `checked_in_at` was the first) and the rule erodes one honest exception at a time. *Owner: team. Trigger: the third addition — at which point D18 should be restated or retired rather than exceptioned again.*
8. **`ManageLinkBackfill.run()` reads its clock once, so "never in the feed" has a race window.** `now` is captured at `backfill.py:66` and passed to every tenant as `after=now` (`:87`); a walk-in created after that capture matches `starts_at > after`. The damage is bounded to a spurious `manage_link_issued: true` and an unrecoverable token (D2 row 1), and the route is a manual operator one-shot — but D2's whole argument is that `starts_at = now` is a **property of the row** rather than a promise this feature makes, and this is the one place that property is evaluated against a stale clock rather than the real one. The fix is one line in F16's file (re-read `now` per chunk) and is deliberately not taken here: it widens the blast radius of a walk-in PR into the backfill, and it fixes nothing this feature needs. *Owner: team. Trigger: F16's next revision, or the first operator run of the backfill on a live board.*
9. **A boutique could use walk-in creation as a general booking-entry back door** — phone a customer, create a "walk-in" at `now` for an appointment next week, and mis-record both the arrival and the schedule. Nothing prevents it and nothing should: the row says `source='walk_in'`, `starts_at` is when it was typed, and the audit row names who typed it, so the record is honest even when the use is wrong. Named so that a later reading of the data knows what it might contain. *Owner: team. Trigger: the remote half, which is the correct home for that intent.*

## Findings raised and REJECTED

Recorded because a silently dropped finding is indistinguishable from an oversight to the next reader — the house convention (`plans/ppl-compliance.md` §9).

**Eleven findings were raised against this spec. Nine are applied in full. Two are applied with their prescribed fix replaced; one carries a sub-claim that is rejected outright.** Nothing was dropped.

1. **REJECTED (sub-claim of finding 9) — "D1b site 4's *unreachable at runtime* becomes reachable-in-principle."** The finding's premise is right and applied (D2 row 1, Risk 8): the backfill's once-captured clock does let a walk-in enter the feed and be minted a token hash. But site 4 is `booking/manage.py:225`, which sits behind `manage_token_matches(token, booking.manage_token_hash)` (`:218-220`) — it needs a caller **presenting the plaintext token**, not a hash in the row. Trace where that plaintext goes: `backfill.py:95` mints it as a local, `:97` computes `reminder_send_after(starts_at=booking.starts_at, now=now)`, and for a walk-in the lead is *milliseconds* — far under `REMINDER_SUPPRESS_UNDER_SECONDS` — so the function returns `None` (`comms.py:86-88`), the loop `continue`s at `:102` **before** the `scheduled_messages.insert` that is the token's only exit, and the local dies. Nobody ever holds it. Site 4 stays unreachable at runtime, its narrowing stays the right treatment for the reason already given (a later feature that *does* mint a deliverable token), and the "reachable-in-principle" framing would have justified converting D1b's `is None` branch into a runtime error path it does not need.

2. **PRESCRIBED FIX REPLACED (finding 8, terminal-arm `poll.refresh()`).** The defect is real and applied. Both suggested shapes were declined: `if (!poll.fail(error)) { … }` moves the refresh out of the `.finally()` and loses F34's reason for putting it there (a rejected create must not park the loop), and `if (terminal === null) poll.refresh()` reads a `useState` value that has not re-rendered yet inside the same handler, so it is `null` on the very tick it needs to be non-null. D9 takes a `let terminated` local set beside the existing `poll.fail` return-guard — one flag, no second classifier, and the `.finally()` shape unchanged.

3. **PRESCRIBED FIX NARROWED (finding 11, `customers/validation.py:29`).** The citation is confirmed fabricated — line 29 is blank, the `MAX_TAG_LENGTH` comment begins at `:30`, and `grep -rn erased Backend/app/customers/` returns only `schemas.py:121` and `service.py:224`, neither of which declines anything. The finding's replacement citation (`db/repositories/customers.py:34-46`) is applied. But the claim it supported — *the picker shows erased subjects* — is **true and stays**, and D3(d) and Risk 4 now cite two independent grounds for it rather than one attribution: `_search_where` filters only `deleted_at`, **and** `CustomerRow` genuinely carries four fields (`customers/schemas.py:36-39`) with no `erased_at` among them. Only the invented F53 provenance is struck.

### Post-build review, round 1 — findings raised against the CODE

**Sixteen findings across three reviewers (quality 10, security 5 with one overlap, test-vacuity 0). Eleven applied, five rejected below.** Every code claim was re-opened in the file before judging; two reviewer claims did not survive that and are recorded as such.

**Applied.** ① `create_walk_in`'s docstring licensed the deliberate non-idempotency on a remedy that does not exist — `cancel` refuses `starts_at <= now` and a walk-in's `starts_at` is its own creation instant, so the duplicate is PERMANENT. The docstring now says so, names the reachable terminals (`no_show`, `complete`) and names what making it correctable would cost. The *behaviour* change is rejected below. ② The dialog rendered `main.py`'s English "Resource not found." into an RTL `role="alert"` — `NOT_FOUND` is absent from `OWNED_ERROR_CODES` and is this route's only domain 404, with four reachable producers including the ordinary archived-type case. A local two-code map (`WALK_IN_ERROR_KEYS`, `mutate`'s precedent) owns it, rather than widening the shared set and changing F34's copy. ③ Same map owns `SLOT_UNAVAILABLE`: F15's «אפשר לבחור מועד אחר» tells the staffer to pick another time in a dialog with no time picker. ④ The walk-in copy deck used «סוגי פגישות» for the collection the catalog screen calls «סוגי תורים» — `walkin.typesEmpty` managed both words in one sentence. The two PLURAL keys now use the catalog's term; the SINGULAR label stays «סוג הפגישה», which is `booking.type`'s shipped wording verbatim, so the reviewer's "rename all three" is narrowed. ⑤ `insert()`'s docstring still named F15's reschedule as "the next caller"; that method UPDATEs in place and never inserts. ⑥ `create`'s `.finally()` guarded only the terminal state, but `refresh()` is unconditional in all THREE states `reschedule()` declines — creating on a *paused* board repainted the rows under a staffer who had frozen them. `mode === "running"` added; the button deliberately stays available. ⑦ `OwnerBookingRow.source` is a union rather than `string`: unlike `status` it has no rendering fallback and is compared against a bare literal. ⑧ `owner_router.py`'s "ten routes" is thirteen. ⑨ The §13 export gained `source` — making the terms pair nullable put into F20's payload exactly the ambiguity `source` exists to resolve, and the console was given the discriminator while the Privacy Protection Authority was not. ⑩ `list_confirmed_without_manage_token` gained `source = 'storefront'`, closing Risk 8 outright rather than leaving the "never in the feed" claim qualified by a once-captured clock. ⑪ The `IntegrityError → SlotUnavailableError` mapping carries a comment naming the day it becomes wrong.

**REJECTED, with reasons.**

4. **REJECTED (quality 1 / security 1, the BEHAVIOUR half) — "carve `source = 'walk_in'` out of `cancel`'s clock guard."** The defect report is right and its docstring half is applied. The code change is a design reversal, not a fix: D2's disarm table rules that a walk-in is refused cancel and that `no_show`/`complete` are the right verbs for someone in the building, and `test_a_walk_in_refuses_cancel_and_admits_no_show_and_complete` is one of the four disarm assertions the plan calls the highest-value tests in the feature. Reversing a recorded ruling and reddening its own proof inside a fix commit is how a spec stops governing. The residual — a mis-tapped duplicate is permanent — is now stated at the site that used to deny it and belongs to the remote half, which is where an owner-facing soft delete or an idempotency window would be designed.

5. **REJECTED (quality 4) — "`BookingDetail` should key the absent-terms sentence off `source`, not off the NULLs."** `bookings_terms_evidence_check` makes «either terms column is NULL» and «`source = 'walk_in'`» a database-enforced **biconditional**, on INSERT and on UPDATE. The two spellings are therefore not merely equal today but equal *by constraint*, and the NULL check is additionally the one TypeScript's narrowing needs to reach the version branch at all — keying on `source` does not typecheck without keeping it. The reviewer's own fix requires a THIRD branch with a second Hebrew string, its `ar.ts` mirror and a vitest fixture for a row the database refuses to accept, i.e. a test that asserts a fake. This is the same "reachable-in-principle" framing rejected as finding 1 above. A comment at the site records the biconditional so it is not re-raised.

6. **REJECTED (quality 8 / security 5) — "move `_sweep_walk_in_bookings` to `conftest.py` as a module-scoped autouse finalizer."** The ordering dependency it names is real and is now written into the fixture's docstring. The prescribed relocation is not available: an autouse fixture in `conftest.py` requests `migrated_db` for **every** module, which starts Postgres under `pytest -m "not db"` and turns a 34-second fast suite into one that cannot run without a database. Session scope is worse — the sweep would then run *after* the very downgrade tests it exists to protect. Module scope in the module that creates the rows, plus the deliberate `# noqa: F401` import in the one other module that creates them, remains the only shape that is both correct and free.

7. **REJECTED (test-vacuity, reported as a plan-staleness note) — nothing to do.** The vacuity hunt ran twenty mutations and found no vacuous test; its two corrections were both in the build's favour. Recorded here so the zero-finding result is not mistaken for a skipped review.

8. **CLAIM WITHDRAWN BY THE BUILDER, recorded because it was nearly shipped.** While arming the new `source` filter this build asserted, in a test comment, that F16's `test_the_backfill_skips_a_booking_that_has_already_happened` was vacuous — "it passes with both the clock and the hash predicates deleted". **That was false.** The probe had mutated the first of two `Booking.starts_at > after` occurrences in `bookings.py`, which belongs to a different method; deleting the feed's own line reds that test correctly. The seeded past row added on the strength of the false claim was removed with it, and the clock predicate keeps its single guardian in the feature that owns it. Named here because a fabricated citation in a review comment is exactly the defect this section exists to catch, and the reviewers caught one of those in the spec (finding 11).

## Decisions Log

- **D1 — One column, two named CHECKs, two dropped NOT NULLs; `NOT NULL DEFAULT 'storefront'` is what makes the terms CHECK true of every existing row with no backfill; the exemption is enumerated (`source = 'walk_in' OR …`) so a future third source fails loudly rather than inheriting a free pass.** The brief said the CHECK already existed; it does not, and building it is what makes dropping the NOT NULLs safe. Declined: `source <> 'storefront' OR …` (same today, opposite tomorrow), an index on `source` (no reader), touching the inline `> 0` CHECK (a CHECK over NULL is not FALSE). **And the `downgrade()` ships, spelled deliberately able to fail**: `SET NOT NULL` raises on a table holding a walk-in row, because the only two ways to make it succeed are to delete real appointments or to fabricate terms evidence, and this feature exists because the second is not allowed. F57's refusing downgrade (`test_migrations.py:352`) is both the precedent and the test idiom. Declined: a pre-clean `DELETE`, and a silent `UPDATE … SET terms_version_accepted = 1`.
- **D1b — The nullability change has six readers and two of them are a live 500 on F20's §13 export.** Enumerated from `grep`, fixed in the same commit as the migration, with a privacy regression test written first. The two unreachable readers are narrowed with an explicit `is None` branch, never a cast — an unreachable-by-construction plus `# type: ignore` is how a static guarantee becomes a runtime crash the day someone mints a token.
- **D2 — `starts_at = now`, full precision, and it is a safety mechanism before it is a timestamp.** It puts the row outside four *shipped* predicates: the F16 backfill's feed, `_guard_live`'s rotation guard, `owner.cancel`'s future-only clock split, and `reminder_send_after`'s suppression window. This — not "F50 declines to mint a token" — is what discharges the brief's claim, because the backfill is a different feature that mints tokens on any matching row. Declined: a picked time (that is the remote half, and it re-arms all four), rounding (turns a free index backstop into contention and fakes a slot claim).
- **D3 — The body is two UUIDs: `customer_id` and `appointment_type_id`. No name, no phone, no terms, no `marketing_consent`, no notes.** (a) Nothing is obtained from the subject, so there is no §11 collection point, no notice, and no counsel-gated Hebrew — which is what lets Gate 1 self-approve. A staff-facing dialog telling a staffer to recite a legal notice is unenforceable delivery dressed as compliance, and F20 already ruled the analogous case (point 4). (b) The correct `marketing_consent` value is **no field at all**: the CHECK admits only `'booking_form'`, and `MarketingConsentSource`'s docstring already refused F33's stronger case as laundering — this path has less, not more. Existing consent is untouched because no clearing statement is issued (F20 D20). (c) No notes: staff free text about a bride has a shipped home in `customers.notes`. (d) An erased subject is the same 404 as an unknown one — after a §14 erase there is no data subject to book. (e) An unknown customer is a 404 whose empty-state copy points at F33's `/checkin`, the intake that already stands behind an approved notice.
- **D4 — No advisory lock, no `offered_slot`, no capacity consumed, `seat_index = 1`, no deposit, no limiter.** The lock exists to serialise a count→pick read that this path does not perform; both partial unique indexes remain free backstops because `starts_at` is microsecond-unique, and an `IntegrityError` maps to the shipped 409 `SLOT_UNAVAILABLE`. The grid not counting her is the correct meaning of "no reservation" and is Risk 1, not a defect.
- **D5 — A separate `insert_walk_in` writer, not defaulted arguments on `insert`.** `insert`'s docstring carries a precondition about the advisory lock that this caller deliberately does not satisfy; folding a lock-free caller into it is how that docstring stops being true. And no `_transition` shape: a create has no prior state to compare, and it is deliberately not idempotent — F33 made the same call for a second queue ticket on one phone.
- **D6 — One `AuditAction` member, no migration, and no phone or name in `details`.** It is the only record of who created a booking carrying no terms evidence.
- **D7 — Zero new error codes and zero new handlers.** `SPEC_ERROR_CODES` set equality is unchanged. Declined: a code distinguishing an unknown customer from an unknown type — it discloses on an authenticated route and every invented code is a handler somebody has to remember.
- **D8 — `source` ships on `OwnerBookingRow`, not only on the detail.** A NULL terms field alone cannot say *why* it is NULL; `source` is the discriminator on the wire for the same reason it is the discriminator in the CHECK. Risk 6 records the D18 erosion.
- **D9 — The board's create uses `poll.refresh()` rather than the F15 list→patch contract, on the success and non-terminal-failure arms, with the terminal arm the one stated exception.** A walk-in belongs at `(starts_at, seat_index)` order, so patching means a second sorter for a list the server already orders and the next tick re-sorts. One extra request per walk-in buys the server's own ordering; refresh on the failure arm too, so there is one rule rather than two — F34 D4(4)'s reason for putting the re-arm in the `.finally()`. **The exception is forced by the swap itself**: F34's unguarded `.finally()` is safe only because `reschedule()` no-ops while stopped, and `refresh()` has no such guard (`usePoll.ts:345-349`), so on a 401/403 it would fire one doomed fetch against a session already known dead. A `let terminated` local set beside the existing `poll.fail` return-guard closes it. Declined: hoisting the refresh out of `.finally()`, and reading the `terminal` state value inside the same handler (it has not re-rendered yet).
- **Gate 1 — self-approved, and the reason is D3 rather than the feature's category.** F50 is absent from Interview Q1's stop-list, and — as designed — it is neither a money surface nor a legal one, because it collects nothing. **No `in_run_gates` entry is opened.** The gate reopens if the design is ever changed to let the dialog create a customer, which is the remote half's problem and is named in *Out of scope*.
