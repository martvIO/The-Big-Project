# Feature 38 — HR directory full: photos, shift-manager eligibility, offboarding + retention scrub

**Epic**: E8 · **Size**: M/L · **Deps**: F31 (merged) · F51 (merged) · F8 (merged) · F20 (merged, PR #45) · F9
**Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals (Q1).**

F38 self-approves despite touching employee PII, because Q1's stop-list is *payments, refunds,
privacy-law **text**, tenant billing* — and F38 authors none of it. The platform's Hebrew privacy
notice already shipped in F20 (`Backend/app/privacy/text.py`, `PLATFORM_NOTICE_HE`) with its
not-lawyer-reviewed disclaimer; F38 adds no new legal wording, only an operational purpose label on
the upload control (below, §Photo). The two genuine legal questions — whether an employee photo
needs written consent on top of the notice, and whether 7 years is the right clock — are **recorded
as the boutique owner's counsel questions** per the E8 Risks section and `ppl-compliance-record.md`,
not answered here. The platform enforces a clock and a purpose; it does not opine on either.

---

## Verified against the codebase (2026-08-06, `main`)

| Claim | Reality |
|---|---|
| Staff row | `Backend/app/models/staff_user.py` — `tenant_id, email, password_hash, display_name, role, break_started_at, weekly_capacity_hours` + `StandardColumns` |
| Role set | `StaffRole` (constants.py:9) — `owner, shift_manager, reception, sales_assistant, seamstress`; DB CHECK `staff_users_role_check`, widened by `0015_floor_roles.py` |
| Staff CRUD | `app/auth/staff.py` (`StaffService`) + `app/auth/staff_router.py` — owner-only at router level; `GET/POST /manage/staff`, `PATCH|DELETE /manage/staff/{staff_id}` |
| Manage UI | `Frontend/apps/manage/src/components/StaffSection.tsx` (458 lines) + `api.ts` `StaffMember`/`CreateStaffRequest`/`UpdateStaffRequest` |
| Two-phase media | `app/catalog/service.py` `presign_media` / `confirm_media` / `delete_media`; `app/catalog/keys.py`; `ACCEPTED_CONTENT_TYPES`, `MAGIC_PREFIXES`, `matches_magic_prefix`, `PRESIGN_TTL_SECONDS`, `SIGNED_GET_TTL_SECONDS` in `app/catalog/validation.py`; `MediaStorage` protocol in `app/storage/base.py` |
| Retention registry | `app/privacy/retention.py` `POLICIES` — **seven** policies today (otp_codes, sessions, queue_tickets, waitlist_entries, message_log, bookings, customers). F22 already merged its `waitlist_entries` row. F38 makes it **eight**. |
| Retention clocks | `app/core/config.py:241-269` — app `Settings`, **not** tenant settings; `retention_enabled = False` (disarmed until F21's backup row) |
| Session revoke seam | `AuthService.resolve_session` (service.py:87-95) re-reads `staff_users` through `by_id`, which filters `deleted_at IS NULL` → a soft-deleted staffer is a 401 on her **next request**. Proven on real Postgres in `tests/test_staff_role_gating_integration.py` (F31). |
| Board / cards | `app/floor/schemas.py` `StaffCard.from_row`; poll every ~5 s; `Frontend/apps/manage/src/components/FloorPanel.tsx` renders `card.display_name` |
| Migration head | `0026_waitlist_entries.py`. F24, F25, F28 are queued ahead with migrations of their own. |

---

## Conflicts recorded (the brief predates shipped reality)

**C1 — phone is NOT a login identifier.** The brief says "phone (her login identifier per Interview
Q11)". Q11 was **overridden 2026-07-30** (LOOP-STATE F31): staff sign in with **email + password**
through the unchanged `/manage/auth/login`. No staff OTP shipped and none is planned. Resolution:
`phone` is an **optional, non-unique contact field** — the number the owner rings when someone does
not show up. It is never read by any auth path, carries **no unique index** (a shared household
number and a blank are both legal, and a unique index would also collide at scrub time — the exact
trap `_erased_phone`'s docstring records for `customers`), and it is scrubbed at the retention
boundary. F39 will collect availability from a **signed-in** staffer, not from a phone.

**C2 — nothing needs relaxing on `email` / `password_hash`.** The brief's code-level constraint
("if F31 did not relax them, F38 carries that migration") **inverts** under C1. Verified: both are
`nullable=False` in `staff_user.py` and in `0003_auth.py`, and every staff member now has real
credentials because that is how she signs in. F38 ships **no nullability migration** and the code may
continue to assume `email` is present on every row.

**C3 — F20 has shipped; the registry is seven, not zero.** The brief's "F38's scrub has no runner
until F20 exists" is stale: F20 merged as PR #45 (migration 0024) and F22 already appended
`waitlist_entries`. F38 appends the **eighth** policy and must update
`test_the_registry_covers_the_seven_classes_with_the_specified_actions` (rename → eight) and add
`AuditAction.RETENTION_STAFF_USERS`.

**C4 — the retention period is an app setting, not a tenant setting.** The brief and pre-decided #34
say "tenant setting". F20 shipped the opposite, deliberately and in writing (config.py:246-248):
*"Per-tenant overrides are deliberately absent: a boutique may not choose its own retention for a
duty the platform enforces on its behalf."* F38 follows the **shipped** pattern — one
`staff_retention_days` in `Settings`, in **days** because the clock is a calendar DATE (`waitlist_
retention_days`' own precedent) — and it is still "one row to change" for counsel at F21, which is
what pre-decided #34 actually asked for.

---

## IN

1. **One photo per staff user**, uploaded through F8's presigned two-phase S3 pipeline unchanged:
   tenant-prefixed key, `pending` → `ready` confirm that verifies magic bytes, signed GET for
   display. No gallery, no crop, no thumbnails, no second storage path.
2. **`shift_manager_eligible`** — a boolean separate from `role`. F38 stores and displays it and
   **enforces nothing**; F40 is its only consumer.
3. **Profile completion** — `phone` (optional, per C1), `start_date`, nullable `last_day`.
   `display_name` already exists.
4. **Offboarding** — one owner action that sets `last_day`, soft-deletes, ends her access, deletes
   her photo object, writes an audit row, and retains every operational row she appears in.
5. **Retention scrub** — an eighth policy in F20's registry that blanks `display_name`, `email` and
   `phone` `staff_retention_days` after `last_day`.

## OUT

Contracts and document storage · pay rates · hours worked · leave balances · performance records ·
org chart · payroll export · re-hire / continuity (a returning staffer is a new row) · hard delete
(soft-delete + scrub **is** the PPL erasure path per `architecture.md`) · **staff self-service editing
of any field, including the photo** (see O3) · multiple photos · face detection or any automated
processing of the image.

---

## Data model

One migration, **head + 1 at build time** (observed head `0026`; F24/F25/F28 carry migrations queued
ahead, so this **will** shift — renumber at rebase, per the standing protocol). Columns on
`staff_users`; **no new table**, per pre-decided #24 and the brief. `0023_seamstress_capacity.py` is
the precedent for adding a column to this table (named table constraints, model updated in the same
PR because **no model↔migration parity test exists anywhere in `Backend/tests`**).

```
phone                       TEXT        NULL      -- contact only (C1); no unique index
start_date                  DATE        NULL
last_day                    DATE        NULL
shift_manager_eligible      BOOLEAN     NOT NULL DEFAULT false
scrubbed_at                 TIMESTAMPTZ NULL      -- the D22 self-falsifying guard
photo_key                   TEXT        NULL      -- the live object
photo_content_type          TEXT        NULL
photo_confirmed_at          TIMESTAMPTZ NULL
photo_pending_key           TEXT        NULL      -- the in-flight upload
photo_pending_content_type  TEXT        NULL
photo_pending_at            TIMESTAMPTZ NULL
```

Named CHECKs so `pg_get_constraintdef` has something to pin (0023's rule):
`staff_users_photo_content_type_check` and `staff_users_photo_pending_content_type_check`, each
`IS NULL OR IN ('image/jpeg','image/png','image/webp')` — the DB pins the set because it is a
security boundary (0006's own words), and `ACCEPTED_CONTENT_TYPES` is **imported** from
`app/catalog/validation.py`, never re-declared.

**Backfill in the same migration**, and it is load-bearing: every staffer deactivated before F38 has
`last_day IS NULL` and would therefore **never** be scrubbed.
`UPDATE staff_users SET last_day = (deleted_at AT TIME ZONE 'Asia/Jerusalem')::date
 WHERE deleted_at IS NOT NULL AND last_day IS NULL;`

**Six photo columns, not a `staff_photos` table** — declined because one photo per person means no
sort order, no per-parent cap, no count, no sweep loop and no list. A table would buy a repository
and an RLS policy to express "at most one". The pending/ready pair is what makes *replace* safe: the
old photo keeps rendering until the new one confirms.

## Photo pipeline

Key: `tenants/{tenant_id}/staff/{staff_user_id}/photo/{photo_id}{ext}` — a `build_staff_photo_key`
beside `build_media_key`, same rule: nothing a client sends reaches the key (`photo_id` is minted
server-side, the extension comes from the declared content type).

Reused verbatim from F8: `MediaStorage.presigned_post` / `head_object` / `read_prefix` /
`signed_get_url` / `delete_object`; `matches_magic_prefix` + `MAGIC_PREFIXES` +
`MAGIC_PREFIX_LENGTH`; `PRESIGN_TTL_SECONDS`; `SIGNED_GET_TTL_SECONDS`; the `sign_media`
degrade-to-`url=None` posture (a storage outage must never fail the board read, only the write
endpoints). Sequence is `confirm_media`'s exactly: `head_object` → content-type match →
`read_prefix` → magic match → promote in a second transaction, **every storage call outside the
session**, idempotent on retry.

Own values, not the catalog's:
- `MAX_STAFF_PHOTO_BYTES = 2_097_152` (2 MiB). A 40 px avatar on a board does not need 10 MiB, and
  this is the payload a ~5 s poll renders.
- A **dedicated** `FixedWindowRateLimiter` instance for `presign:staff:{tenant_id}`. **Not** the
  catalog's — one budget is one instance; two keys on one limiter share a single ceiling.
- Advisory lock: reuse `StaffService._STAFF_LOCK` (`staff:{tenant_id}`). A boutique has single-digit
  staff; a second `staff-photo:` key would buy nothing.

**Replace**: presign writes the pending triple (best-effort-deleting any *previous* pending object,
audited first with its key); confirm moves pending → live and best-effort-deletes the **superseded**
live object. **Delete**: nulls all six columns, audits the key, then deletes the object.

**Purpose, stated because PPL Amendment 13 requires it** (E8 Risks): the photo exists **solely to
identify a colleague on F34's shift board and F36's staff cards**. The upload control carries a
Hebrew purpose line — an operational label, not legal text (see Gate 1) — reading
«התמונה משמשת לזיהוי בלוח המשמרת ובכרטיסי הצוות בלבד.» No exclamation mark (pre-decided #5), `ar`
key added untranslated. Nothing in this feature or any later one may use the image for attendance,
monitoring or matching; that drift is named in the epic Risks and is a review-blocking rule.

## Offboarding

`DELETE /manage/staff/{staff_id}?last_day=YYYY-MM-DD` — the **existing** F51 endpoint, extended.
`last_day` optional, defaulting to `today_jerusalem()` (`app/storefront/validation.py:86`); a
missing default would silently exempt her from the clock. Rejected if `> today + 1 year` or
`< start_date`.

One `tenant_session`, `_STAFF_LOCK` taken **before any read**, F51's protocol unchanged:
1. `by_id` → `StaffNotFoundError`; self-target → `StaffSelfManageError`; last live owner →
   `LastOwnerRequiredError`. All three keep their shipped bodies and wire codes.
2. `UPDATE last_day`, null the six photo columns, `soft_delete`.
3. `AuditAction.STAFF_DEACTIVATED` — `details` gains `last_day` and `photo_storage_key`. That row is
   the **only durable record** of the orphaned object if step 4 fails.
4. **After** the transaction: best-effort `delete_object`, logged not raised.

**No session sweep, and there must not be one.** F51's `deactivate` docstring rules on this and F31
proved the seam on real Postgres: `resolve_session` re-reads `staff_users` every request and `by_id`
filters `deleted_at IS NULL`, so her live cookie is a 401 on her next request. F20's `sessions`
policy purges the dead rows on their own clock. Calling `revoke_for_staff_user` here would be a
second mechanism for a fact the first one already guarantees.

**The photo object goes at offboarding, not at the 7-year scrub** — a deliberate departure from the
brief, in the stricter direction. Her face is the most identifying datum on the row, nothing
operational reads it once she is gone (`list_live` excludes her from every board), and it keeps the
retention policy a **pure SQL statement**, which is the shipped `PolicyRun` contract — the runner
hands a policy a session and nothing else, so an S3 call inside one would require widening a tested
interface for a single caller.

**Every operational row is retained, joined by a `staff_user_id` that is never nulled**:
`fitting_room_assignments.staff_user_id` (F36 — `RoomAssignment.staff_display_name: null` is already
D11's shipped GHOST HOLDER, and it renders correctly for an offboarded holder),
`sos_alerts.target_staff_user_id` (F37), `alteration_tickets.assigned_staff_user_id` (F41/F42),
`audit_log.actor_id`, and F40's future roster rows. No CASCADE exists anywhere to undo this — the
FK-less schema makes retention the default and erasure the deliberate act.

## Retention scrub + registration

`Settings`: `staff_retention_days: int = 365 * 7` (2555), beside `waitlist_retention_days` with the
same "flagged for counsel at F21" comment, plus a floor in
`_require_retention_periods_above_their_floors` of `365 * 3` — a three-year floor is the same shape
the bookings clock already carries, and it makes a fat-fingered `7` fail at boot rather than at 03:00.

```python
async def _scrub_staff_users(session, tenant_id, *, now, settings, limit, dry_run) -> int:
    cutoff_day = now.astimezone(BOUTIQUE_TIMEZONE).date() - timedelta(days=settings.staff_retention_days)
    where = [
        StaffUser.tenant_id == tenant_id,
        StaffUser.deleted_at.is_not(None),   # only offboarded rows
        StaffUser.scrubbed_at.is_(None),     # D22 — destroyed by this policy's own UPDATE
        StaffUser.last_day.is_not(None),
        StaffUser.last_day <= cutoff_day,
    ]
    values = {
        "display_name": ERASED_NAME,
        "email": func.concat(ERASED_PHONE_PREFIX, cast(StaffUser.id, Text)),  # per-row, never a constant
        "phone": None,
        "scrubbed_at": now,
    }
    return await _scrub(session, StaffUser, where, values, limit=limit, dry_run=dry_run)
```

Registered as `RetentionPolicy("staff_users", RetentionAction.SCRUB, ("staff_users",),
_scrub_staff_users)`, **appended last** — it depends on no other policy, and only the
`bookings → customers` pair has an order that matters.

- `.astimezone(BOUTIQUE_TIMEZONE).date()` before comparing, because `last_day` is a **Jerusalem**
  calendar date and `now` is UTC. Harmless on a 7-year window; wrong as an idiom, and the file's own
  warning says so twice.
- SCRUB not PURGE: five tables hold no-FK pointers at this id.
- `email` gets a **per-row** `erased:{id}`. `idx_staff_users_tenant_email_unique` is partial on
  `deleted_at IS NULL` so a constant would technically survive — but the `customers` scrub shipped
  the per-row form after exactly this reasoning failed once, and one convention across both is
  cheaper than a footnote.
- `password_hash` is **left alone**: `verify_password` catches only `VerifyMismatchError`, so a
  non-argon2 sentinel would raise `InvalidHashError` on any path that reached it. Nothing reaches it
  (`by_email` filters `deleted_at IS NULL`), and a one-way hash is not the personal data the brief
  names. Recorded rather than silently skipped.
- Photo columns are already NULL from offboarding and stay out of this UPDATE.
- `AuditAction.RETENTION_STAFF_USERS = "retention_staff_users"` — `audit_action()` raises on a
  missing member, so its absence is a `ValueError` in `test_retention_policies.py`, not a silent
  no-op at 03:00.
- Ships **disarmed** with everything else (`retention_enabled = False`).

## API

| Route | Change |
|---|---|
| `GET /manage/staff` | `StaffMember` gains `phone`, `start_date`, `last_day`, `shift_manager_eligible`, `photo_url`, `photo_confirmed_at` |
| `POST /manage/staff` | `CreateStaffRequest` gains `phone?`, `start_date?`, `shift_manager_eligible?` (default `false`) |
| `PATCH /manage/staff/{id}` | `UpdateStaffRequest` gains the same three; F51's no-op rule and per-field audit rows extend to them |
| `DELETE /manage/staff/{id}?last_day=` | offboard (above) |
| `POST /manage/staff/{id}/photo/presign` | body `{content_type, byte_size}` → `{url, fields, expires_in, max_bytes}` |
| `POST /manage/staff/{id}/photo/confirm` | → the updated `StaffMember` |
| `DELETE /manage/staff/{id}/photo` | → the updated `StaffMember` |

All seven stay **owner-only** at router level — `staff_router.py` mounts the gate on the router, not
per route, so a route added here cannot forget it. `phone` validates through
`app/boutique/validation.py::validate_phone` (imported, not rewritten). `start_date` / `last_day` are
`datetime.date` on the wire (`YYYY-MM-DD`), never instants.

`floor/schemas.py::StaffCard` gains `photo_url: str | None` and `photo_confirmed_at: str | null`,
signed per read with the `sign_media` degrade-to-null posture.

## Manage UI (extends F51's `StaffSection.tsx` — no parallel surface)

- Each row: a photo cell (image or initial-letter fallback), an upload/replace/remove control with
  the Hebrew purpose line, a `shift_manager_eligible` checkbox, `phone` and `start_date` inputs, and
  `last_day` shown on offboarded rows.
- Dates use native `<input type="date">`; the offboard confirm dialog gains one, defaulted to today.
- The confirm dialog's Hebrew says plainly that operational history is retained and personal details
  are erased later — no exclamation marks.
- **F-W1**: every touch control here is `size="md"` (44 px). `size="sm"` is 36 px and fails the floor.
- `he.ts` + `ar.ts` keys added together, `ar` untranslated (Q3 / pre-decided #47).
- `FloorPanel.tsx` renders the photo on the staff card and **pins the URL it already rendered, keyed
  by `(id, photo_confirmed_at)`**. Without that, the ~5 s poll hands the browser a freshly signed —
  therefore different — URL every tick and re-downloads every photo, forever.

## Test plan

**Backend**
- `test_staff_management_db.py` — offboard writes `last_day` + `deleted_at` + audit in one
  transaction; default `last_day` = today Jerusalem; the three F51 guards still fire; her room
  assignment / SOS / alteration rows survive and still resolve by id; her session is a 401 on the
  next request (**no** sweep); the migration's backfill fills `last_day` on a pre-F38 deleted row.
- `test_staff_photo.py` — presign → confirm happy path; magic-byte mismatch rejects and deletes;
  content-type mismatch rejects; over-cap and bad type are 400s; confirm is idempotent; replace keeps
  the old photo visible until confirm and then deletes the superseded object; the throttle bounds
  presign and is a **separate instance** from the catalog's; unconfigured storage 503s the write and
  serves `photo_url: null` on reads.
- `test_retention_policies.py` — the registry assertion becomes **eight**; `staff_users` is not in
  `FORBIDDEN_TABLES`; `audit_action` resolves.
- `test_retention_db.py` — both boundary directions on real Postgres (`last_day` one day inside and
  one day outside the window); the D22 loop proves the predicate is falsified by its own UPDATE; a
  live (non-deleted) staffer past 7 years is **never** touched; two rows in one chunk both get
  distinct `erased:{id}` emails.
- `test_migrations.py` — the two photo CHECKs pinned by deparsed literal, 0023's rule.
- `test_staff_service.py` / `test_floor_service.py` — new fields on the wire; `StaffCard.photo_url`
  degrades to null on a storage failure without failing the board read.

**Frontend** — `StaffSection.test.tsx` (photo upload states, eligibility toggle, offboard dialog with
its date input, error mapping), `FloorPanel.test.tsx` (photo renders; URL pinned across a poll whose
signature changed), `e2e/manage.spec.ts` + `e2e/a11y.spec.ts` (axe **zero violations**, RTL, 44 px
targets — IS 5568 / WCAG 2.0 AA is a legal requirement).

## Open questions (recorded, non-blocking)

- **O1** Does an employee photo need written consent beyond F20's platform notice? → owner's counsel;
  surfaced at F21 alongside the retention list. Platform mitigation ships now: one purpose-limited
  photo, tenant-prefixed key, signed URL, deleted at offboarding.
- **O2** Is 7 years right? → counsel at F21. One `Settings` value (C4).
- **O3** Should a staffer upload her **own** photo? The brief's OUT hints yes; `staff_router.py` is
  owner-only at router level and manage has no staff self-profile screen. F38 ships **owner-only** —
  a self-service surface is a feature, not a flag. Revisit with F39, which is the first screen a
  non-owner staffer will actually open.
- **O4** May a staffer whose `role` is `shift_manager` be slotted without `shift_manager_eligible`?
  F38 stores the boolean and enforces nothing; **F40** decides.
